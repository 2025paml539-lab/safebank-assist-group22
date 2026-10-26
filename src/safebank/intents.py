"""
Intent label space helpers.

Design note
-----------
The authoritative list of the 77 BANKING77 intent names is deliberately NOT
hardcoded here. It is read from the dataset at load time via
``dataset.features["label"].names`` (see ``data_prep.py``), because that is the
only source which cannot drift from the data we actually evaluate on.

What this module does provide:

* ``INTENT_THEMES`` / ``FOCUS_INTENTS`` - a 20-intent subset used only for the
  E6 deep failure analysis. All 77 stay in the label space for every metric.
* ``CONFUSABLE_PAIRS`` - intent pairs whose dataset definitions genuinely
  overlap. These are our predicted failure modes and the backbone of E6.
* ``validate_label_space`` - a guard that fails loudly if the loaded label
  space is not what the report claims.

Owner: Kishore (solution architecture)
"""

from __future__ import annotations

from dataclasses import dataclass

from . import config

# --------------------------------------------------------------------------
# Focused subset for failure analysis (E6)
# --------------------------------------------------------------------------

#: Five service themes, used to organise the E6 analysis and tool routing.
#: Every name must exist in the dataset's own label space;
#: ``validate_label_space`` asserts that, so a typo here fails fast rather than
#: silently skewing the analysis.
INTENT_THEMES: dict[str, tuple[str, ...]] = {
    "card_delivery": (
        "card_arrival",
        "card_delivery_estimate",
        "order_physical_card",
        "getting_spare_card",
    ),
    "card_security": (
        "lost_or_stolen_card",
        "compromised_card",
        "card_swallowed",
        "pin_blocked",
    ),
    "top_up": (
        "top_up_failed",
        "pending_top_up",
        "top_up_reverted",
        "top_up_limits",
    ),
    "transfer": (
        "failed_transfer",
        "pending_transfer",
        "transfer_not_received_by_recipient",
        "transfer_timing",
    ),
    "cash_atm": (
        "atm_support",
        "cash_withdrawal_charge",
        "pending_cash_withdrawal",
        "declined_cash_withdrawal",
    ),
}

#: Flattened 20-intent focus set for E6.
FOCUS_INTENTS: tuple[str, ...] = tuple(
    intent for theme in INTENT_THEMES.values() for intent in theme
)


@dataclass(frozen=True)
class ConfusablePair:
    """A pair of intents we expect the model to mix up, and the reason why."""

    first: str
    second: str
    reason: str


#: Predicted confusions. Each gets a row in the E6 root-cause table.
CONFUSABLE_PAIRS: tuple[ConfusablePair, ...] = (
    ConfusablePair(
        "card_arrival",
        "card_delivery_estimate",
        "Both concern an undelivered card and differ only in whether the "
        "customer asks about current status or about expected timing.",
    ),
    ConfusablePair(
        "top_up_failed",
        "pending_top_up",
        "An incomplete top-up can be described as failed or as pending "
        "depending on the customer's interpretation, not on the facts.",
    ),
    ConfusablePair(
        "transfer_not_received_by_recipient",
        "transfer_timing",
        "A recipient not seeing money may be a timing question or a fault "
        "report; the surface wording is often identical.",
    ),
    ConfusablePair(
        "lost_or_stolen_card",
        "compromised_card",
        "Both trigger card blocking. The distinction is the cause, which "
        "customers rarely state explicitly.",
    ),
    ConfusablePair(
        "cash_withdrawal_charge",
        "declined_cash_withdrawal",
        "Both mention an ATM withdrawal problem; one is about a fee, the "
        "other about a refusal.",
    ),
    ConfusablePair(
        "pending_cash_withdrawal",
        "declined_cash_withdrawal",
        "Pending and declined withdrawals look identical to a customer whose "
        "balance changed but who received no cash.",
    ),
)


#: Confusions actually OBSERVED in a real model run, as opposed to the
#: predicted ones above.
#:
#: Kept separate on purpose. ``CONFUSABLE_PAIRS`` is a prediction made before
#: any results existed, and the report's claim that we anticipated those
#: failure modes is only honest if the list stays untouched by hindsight.
#: Silently appending observed confusions would convert a prediction into a
#: retrodiction and quietly overstate the analysis.
#:
#: Unlike ``CONFUSABLE_PAIRS``, members here need not be in ``FOCUS_INTENTS``:
#: a real model confuses whatever it likes across all 77 labels.
OBSERVED_CONFUSIONS: tuple[ConfusablePair, ...] = (
    ConfusablePair(
        "card_arrival",
        "card_not_working",
        "Observed on the first real Qwen2.5-1.5B query: 'my card hasn't "
        "arrived' was labelled card_not_working. An undelivered card and a "
        "faulty card are different intents, but both are phrased as the card "
        "not working for the customer. Not in the predicted set because the "
        "prediction focused on delivery-vs-timing rather than "
        "delivery-vs-fault.",
    ),
)


class LabelSpaceError(ValueError):
    """Raised when the loaded intent label space is not what we expect."""


@dataclass(frozen=True)
class LabelSpaceReport:
    """Outcome of validating a loaded label space."""

    n_intents: int
    missing_focus_intents: tuple[str, ...]
    missing_confusable_intents: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return (
            self.n_intents == config.EXPECTED_N_INTENTS
            and not self.missing_focus_intents
            and not self.missing_confusable_intents
        )


def validate_label_space(labels: list[str], *, strict: bool = True) -> LabelSpaceReport:
    """
    Check a loaded label space against what the report claims.

    Parameters
    ----------
    labels:
        Intent names as loaded from the dataset.
    strict:
        When True, raise :class:`LabelSpaceError` on mismatch. When False,
        return the report and let the caller decide.

    Why this exists
    ---------------
    The report states "all 77 intents" and names specific confusable pairs. If
    the dataset version changed, or a name in this module were misspelled, the
    analysis would describe intents that were never evaluated. This converts
    that class of silent error into an immediate, obvious failure.
    """
    known = set(labels)

    missing_focus = tuple(i for i in FOCUS_INTENTS if i not in known)
    confusable_names = {p.first for p in CONFUSABLE_PAIRS} | {
        p.second for p in CONFUSABLE_PAIRS
    }
    missing_confusable = tuple(sorted(n for n in confusable_names if n not in known))

    report = LabelSpaceReport(
        n_intents=len(labels),
        missing_focus_intents=missing_focus,
        missing_confusable_intents=missing_confusable,
    )

    if strict and not report.ok:
        problems: list[str] = []
        if report.n_intents != config.EXPECTED_N_INTENTS:
            problems.append(
                f"expected {config.EXPECTED_N_INTENTS} intents, "
                f"loaded {report.n_intents}"
            )
        if missing_focus:
            problems.append(f"focus intents absent from dataset: {missing_focus}")
        if missing_confusable:
            problems.append(
                f"confusable-pair intents absent from dataset: {missing_confusable}"
            )
        raise LabelSpaceError("; ".join(problems))

    return report


def theme_of(intent: str) -> str | None:
    """Return the service theme an intent belongs to, or None if unthemed."""
    for theme, members in INTENT_THEMES.items():
        if intent in members:
            return theme
    return None
