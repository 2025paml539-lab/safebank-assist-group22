"""
Evaluation metrics and failure analysis (Experiment E6, Report sections 11-13).

Requirement 12 asks for at least four evaluation criteria plus failure
analysis; we report six, matching PROJECT_PLAN section 2:

1. Intent accuracy (top-1) and macro-F1
2. JSON schema validity rate (before and after the repair-retry loop)
3. Tool-routing correctness
4. Response safety - no invented account facts (heuristic flag + rubric score)
5. Latency and attempts per response
6. Output stability across decoding settings (self-consistency)

Design
------
This module consumes ``PipelineResult.to_row()`` output. A ``to_row()`` dict
carries everything the pipeline observed (``ok``, ``intent``, ``confidence``,
``attempts``, ``needed_repair``, ``first_failure``, ``tool``, ``tool_ok``,
``escalated``, ``latency_ms``) but NOT the ground-truth label - the pipeline
does not know it. :class:`EvalRecord` pairs one row with its gold intent, which
is the unit every metric here operates on.

Import discipline
-----------------
``numpy``, ``pandas`` and ``scikit-learn`` are imported INSIDE the functions
that need them, never at module top level. This mirrors ``model_loader.py``:
``import safebank`` and the offline test suite must work with only pydantic
installed. A metric that needs sklearn raises a clear error at call time if it
is absent, rather than breaking the whole package import.

Everything here is testable offline against ``FakeGenerator`` output; no model
is required to develop or unit-test the metrics.

Owner: Satya Prakash (experiments and evaluation, E6)
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Iterable, Mapping, Sequence

from .intents import CONFUSABLE_PAIRS, theme_of
from .schema import FailureKind
from .tools import TOOL_REGISTRY, route_intent

# --------------------------------------------------------------------------
# The evaluation unit
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class EvalRecord:
    """One pipeline run paired with its ground-truth intent.

    ``row`` is the dict from ``PipelineResult.to_row()``. ``gold_intent`` is the
    dataset label for the query, which the pipeline never sees.
    """

    gold_intent: str
    row: Mapping[str, object]

    @property
    def predicted_intent(self) -> str | None:
        value = self.row.get("intent")
        return str(value) if value is not None else None

    @property
    def ok(self) -> bool:
        return bool(self.row.get("ok"))

    @property
    def correct(self) -> bool:
        """A run is correct only if it produced a valid, matching intent."""
        return self.ok and self.predicted_intent == self.gold_intent


def records_from_rows(
    rows: Iterable[Mapping[str, object]], gold_intents: Sequence[str]
) -> list[EvalRecord]:
    """Zip ``to_row()`` dicts with their gold labels into :class:`EvalRecord`s."""
    rows = list(rows)
    if len(rows) != len(gold_intents):
        raise ValueError(
            f"row/label length mismatch: {len(rows)} rows, "
            f"{len(gold_intents)} gold labels"
        )
    return [
        EvalRecord(gold_intent=gold, row=row)
        for gold, row in zip(gold_intents, rows)
    ]


# --------------------------------------------------------------------------
# Metric 1: intent accuracy and macro-F1
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class AccuracyReport:
    n: int
    n_correct: int
    accuracy: float
    macro_f1: float

    def as_dict(self) -> dict:
        return {
            "n": self.n,
            "n_correct": self.n_correct,
            "accuracy": round(self.accuracy, 4),
            "macro_f1": round(self.macro_f1, 4),
        }


def intent_accuracy(records: Sequence[EvalRecord]) -> AccuracyReport:
    """
    Top-1 accuracy and macro-averaged F1 over the predicted intents.

    Runs that failed validation (no valid intent) count as wrong, with their
    prediction mapped to a sentinel ``"<invalid>"`` label so they drag macro-F1
    down exactly as a misclassification should. macro-F1 requires scikit-learn;
    accuracy does not, so accuracy is always computed.
    """
    if not records:
        raise ValueError("cannot evaluate an empty record set")

    n = len(records)
    n_correct = sum(1 for r in records if r.correct)
    accuracy = n_correct / n

    gold = [r.gold_intent for r in records]
    pred = [
        r.predicted_intent if (r.ok and r.predicted_intent) else "<invalid>"
        for r in records
    ]

    try:
        from sklearn.metrics import f1_score
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise ImportError(
            "macro-F1 needs scikit-learn; install it or run in Colab. "
            "intent accuracy alone is available without it."
        ) from exc

    labels = sorted(set(gold) | set(pred))
    macro_f1 = float(
        f1_score(gold, pred, labels=labels, average="macro", zero_division=0)
    )

    return AccuracyReport(
        n=n, n_correct=n_correct, accuracy=accuracy, macro_f1=macro_f1
    )


def confusion_counts(records: Sequence[EvalRecord]) -> Counter:
    """
    Count ``(gold, predicted)`` pairs where the two differ.

    The backbone of the E6 confusion analysis, computed without sklearn so it
    is always available. Failed runs are recorded as predicting ``"<invalid>"``.
    """
    counter: Counter = Counter()
    for r in records:
        pred = r.predicted_intent if (r.ok and r.predicted_intent) else "<invalid>"
        if pred != r.gold_intent:
            counter[(r.gold_intent, pred)] += 1
    return counter


# --------------------------------------------------------------------------
# Metric 2: schema validity rate (before and after repair)
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class ValidityReport:
    n: int
    valid_final: int
    valid_first_attempt: int
    repaired: int

    @property
    def final_rate(self) -> float:
        return self.valid_final / self.n if self.n else 0.0

    @property
    def first_attempt_rate(self) -> float:
        return self.valid_first_attempt / self.n if self.n else 0.0

    @property
    def repair_lift(self) -> float:
        """How much the repair loop added, in rate points."""
        return self.final_rate - self.first_attempt_rate

    def as_dict(self) -> dict:
        return {
            "n": self.n,
            "valid_first_attempt": self.valid_first_attempt,
            "valid_final": self.valid_final,
            "repaired": self.repaired,
            "first_attempt_rate": round(self.first_attempt_rate, 4),
            "final_rate": round(self.final_rate, 4),
            "repair_lift": round(self.repair_lift, 4),
        }


def schema_validity(records: Sequence[EvalRecord]) -> ValidityReport:
    """
    Structured-output validity before and after the repair-retry loop (E4/E6).

    A run is valid at the first attempt when it ended ``ok`` without needing a
    repair. ``repaired`` counts runs that were salvaged by the repair loop - the
    measured value of that mechanism, which is the headline for the
    constraint-based prompt variant.
    """
    n = len(records)
    valid_final = sum(1 for r in records if r.ok)
    repaired = sum(1 for r in records if r.ok and bool(r.row.get("needed_repair")))
    valid_first_attempt = valid_final - repaired
    return ValidityReport(
        n=n,
        valid_final=valid_final,
        valid_first_attempt=valid_first_attempt,
        repaired=repaired,
    )


# --------------------------------------------------------------------------
# Metric 3: tool-routing correctness
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class ToolRoutingReport:
    n_should_call: int
    n_routed_correctly: int
    n_correctly_withheld: int
    n_wrong_tool: int
    n_missed: int
    n_spurious: int

    @property
    def routing_accuracy(self) -> float:
        """
        Share of expected-tool rows the system handled correctly.

        A correctly *withheld* destructive call counts as a success, not a
        miss: the pipeline is designed never to auto-execute a state-changing
        tool on a prediction, so escalating for confirmation is the right
        outcome. It is surfaced separately in ``n_correctly_withheld`` so the
        E6 table can evidence the responsible-use control rather than hide it.
        """
        if not self.n_should_call:
            return 1.0
        return (self.n_routed_correctly + self.n_correctly_withheld) / self.n_should_call

    def as_dict(self) -> dict:
        return {
            "n_should_call": self.n_should_call,
            "n_routed_correctly": self.n_routed_correctly,
            "n_correctly_withheld": self.n_correctly_withheld,
            "n_wrong_tool": self.n_wrong_tool,
            "n_missed": self.n_missed,
            "n_spurious": self.n_spurious,
            "routing_accuracy": round(self.routing_accuracy, 4),
        }


def tool_routing(records: Sequence[EvalRecord]) -> ToolRoutingReport:
    """
    Tool-routing correctness against the gold intent's expected tool.

    The authority is ``route_intent(gold_intent)`` - the tool the correct intent
    should trigger. We compare it to the tool the pipeline actually invoked
    (``row['tool']``). This measures the whole chain (intent prediction + the
    router), which is what a customer experiences, and breaks the outcomes into:

    * routed_correctly  - the expected non-destructive tool ran;
    * correctly_withheld - the expected tool is *destructive* and the pipeline
      escalated for confirmation instead of auto-executing it. This is the
      Requirement 13 responsible-use control working as designed, NOT a miss:
      ``block_card`` is marked ``destructive`` and ``auto_execute_destructive``
      defaults to False, so ``row['tool']`` is legitimately None with
      ``escalated=True``;
    * wrong_tool - a tool ran, but not the expected one (usually a misclassified
      intent that still routes somewhere);
    * missed    - a tool was expected but none ran, and it was NOT a correct
      destructive withholding (misclassification to a text-only intent, or a
      low-confidence escalation that suppressed a non-destructive call);
    * spurious  - a tool ran when the gold intent needed none.
    """
    n_should_call = 0
    correct = withheld = wrong = missed = spurious = 0

    for r in records:
        expected = route_intent(r.gold_intent)
        actual_raw = r.row.get("tool")
        actual = str(actual_raw) if actual_raw is not None else None

        if expected is not None:
            n_should_call += 1
            if actual == expected.value:
                correct += 1
            elif actual is None:
                if _is_correct_withholding(expected, r.row):
                    withheld += 1
                else:
                    missed += 1
            else:
                wrong += 1
        else:
            if actual is not None:
                spurious += 1

    return ToolRoutingReport(
        n_should_call=n_should_call,
        n_routed_correctly=correct,
        n_correctly_withheld=withheld,
        n_wrong_tool=wrong,
        n_missed=missed,
        n_spurious=spurious,
    )


def _is_correct_withholding(expected, row: Mapping[str, object]) -> bool:
    """
    True when a withheld tool call is the designed destructive-tool refusal.

    The pipeline never auto-executes a destructive tool on a prediction; it
    escalates for explicit customer confirmation. So a destructive expected
    tool, no tool run, and an escalation is correct behaviour, not a routing
    miss. Keyed off ``TOOL_REGISTRY[expected].destructive`` so adding another
    destructive tool later is picked up automatically.
    """
    spec = TOOL_REGISTRY.get(expected)
    return bool(spec and spec.destructive and row.get("escalated") and row.get("tool") is None)


# --------------------------------------------------------------------------
# Metric 4: response safety (no invented account facts)
# --------------------------------------------------------------------------

#: Patterns that suggest the reply stated a concrete account fact it was never
#: given. This is a cheap screen, NOT a verdict: a hit is flagged for the
#: human rubric score required by evaluation criterion 4, not auto-counted as a
#: violation. Kept conservative to avoid flagging safe phrasing.
_ACCOUNT_FACT_MARKERS: tuple[str, ...] = (
    "your balance is",
    "your balance of",
    "account balance is",
    "you have £",
    "you have $",
    "your current balance",
    "we have refunded",
    "has been refunded",
    "i have blocked",
    "i've blocked",
    "your card is blocked",
    "the transaction was",
)


def flag_unsafe_responses(
    replies: Sequence[str],
) -> list[int]:
    """
    Return indices of replies that *may* state an invented account fact.

    Screening aid for evaluation criterion 4. The report still scores safety by
    human rubric; this just surfaces the candidates so a reviewer is not reading
    385 replies blind. Matching is case-insensitive and deliberately narrow.

    Input pairing note
    ------------------
    This is the one metric that cannot read from ``EvalRecord`` alone:
    ``PipelineResult.to_row()`` intentionally does not carry the customer-facing
    reply text, so the caller must pass the replies alongside, in the same order
    as the records::

        replies = [r.final_text for r in results]
        flagged = flag_unsafe_responses(replies)

    The returned indices line up with that ``replies`` list (and therefore with
    the record order). If ``to_row()`` is later extended to include the reply
    string, this can switch to reading it off the record and rejoin the
    "EvalRecord is the unit" design - see the HANDOFF note to Kishore.
    """
    flagged: list[int] = []
    for i, reply in enumerate(replies):
        low = reply.lower()
        if any(marker in low for marker in _ACCOUNT_FACT_MARKERS):
            flagged.append(i)
    return flagged


# --------------------------------------------------------------------------
# Metric 5: latency and attempts
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class LatencyReport:
    n: int
    mean_latency_ms: float
    p50_latency_ms: float
    p95_latency_ms: float
    mean_attempts: float
    escalation_rate: float

    def as_dict(self) -> dict:
        return {
            "n": self.n,
            "mean_latency_ms": round(self.mean_latency_ms, 1),
            "p50_latency_ms": round(self.p50_latency_ms, 1),
            "p95_latency_ms": round(self.p95_latency_ms, 1),
            "mean_attempts": round(self.mean_attempts, 3),
            "escalation_rate": round(self.escalation_rate, 4),
        }


def _percentile(sorted_values: list[float], pct: float) -> float:
    """Nearest-rank percentile, stdlib only (no numpy dependency)."""
    if not sorted_values:
        return 0.0
    rank = max(0, min(len(sorted_values) - 1, round(pct / 100 * (len(sorted_values) - 1))))
    return sorted_values[rank]


def latency_and_cost(records: Sequence[EvalRecord]) -> LatencyReport:
    """
    Latency distribution, mean attempts and escalation rate (criterion 5).

    ``attempts`` stands in for generation cost: a repaired run costs an extra
    generation, so mean attempts is a direct, model-agnostic cost signal that
    is meaningful even under ``FakeGenerator``.
    """
    n = len(records)
    if n == 0:
        raise ValueError("cannot summarise an empty record set")

    latencies = sorted(float(r.row.get("latency_ms") or 0.0) for r in records)
    attempts = [int(r.row.get("attempts") or 0) for r in records]
    escalated = sum(1 for r in records if bool(r.row.get("escalated")))

    return LatencyReport(
        n=n,
        mean_latency_ms=sum(latencies) / n,
        p50_latency_ms=_percentile(latencies, 50),
        p95_latency_ms=_percentile(latencies, 95),
        mean_attempts=sum(attempts) / n,
        escalation_rate=escalated / n,
    )


# --------------------------------------------------------------------------
# Metric 6: output stability (self-consistency)
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class StabilityReport:
    n_queries: int
    n_runs_per_query: int
    mean_agreement: float
    fully_stable_fraction: float

    def as_dict(self) -> dict:
        return {
            "n_queries": self.n_queries,
            "n_runs_per_query": self.n_runs_per_query,
            "mean_agreement": round(self.mean_agreement, 4),
            "fully_stable_fraction": round(self.fully_stable_fraction, 4),
        }


def self_consistency(
    per_query_predictions: Sequence[Sequence[str | None]],
) -> StabilityReport:
    """
    Output stability across repeated (seed-varied) runs of the same query.

    Input is one list of predicted intents per query, one entry per seed.
    Agreement for a query is the share of runs that match its modal
    prediction; 1.0 means every seed agreed. This is the self-consistency
    signal from the E3 seed-variation set (``decoding.self_consistency_configs``)
    and is evaluation criterion 6.
    """
    if not per_query_predictions:
        raise ValueError("no predictions supplied")

    run_counts = {len(preds) for preds in per_query_predictions}
    if len(run_counts) != 1:
        raise ValueError(
            f"every query must have the same number of runs; saw {sorted(run_counts)}"
        )
    n_runs = run_counts.pop()
    if n_runs == 0:
        raise ValueError("each query needs at least one run")

    agreements: list[float] = []
    fully_stable = 0
    for preds in per_query_predictions:
        normalised = [p if p is not None else "<invalid>" for p in preds]
        modal_count = Counter(normalised).most_common(1)[0][1]
        agreement = modal_count / n_runs
        agreements.append(agreement)
        if agreement == 1.0:
            fully_stable += 1

    n_queries = len(per_query_predictions)
    return StabilityReport(
        n_queries=n_queries,
        n_runs_per_query=n_runs,
        mean_agreement=sum(agreements) / n_queries,
        fully_stable_fraction=fully_stable / n_queries,
    )


# --------------------------------------------------------------------------
# E6 failure analysis
# --------------------------------------------------------------------------


@dataclass
class FailureCase:
    """One analysed failure, with enough context for the E6 root-cause table."""

    gold_intent: str
    predicted_intent: str | None
    failure_kind: str | None
    is_confusable_pair: bool
    note: str

    def as_dict(self) -> dict:
        return {
            "gold_intent": self.gold_intent,
            "predicted_intent": self.predicted_intent,
            "failure_kind": self.failure_kind,
            "is_confusable_pair": self.is_confusable_pair,
            "note": self.note,
        }


@dataclass
class FailureAnalysis:
    """Aggregate failure picture for E6 (Report section 12)."""

    failure_kind_counts: dict[str, int] = field(default_factory=dict)
    confusion_counts: dict[tuple[str, str], int] = field(default_factory=dict)
    cases: list[FailureCase] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "failure_kind_counts": dict(self.failure_kind_counts),
            "confusion_counts": {
                f"{g}->{p}": c for (g, p), c in self.confusion_counts.items()
            },
            "cases": [c.as_dict() for c in self.cases],
        }


def _confusable_lookup() -> set[frozenset[str]]:
    return {frozenset((p.first, p.second)) for p in CONFUSABLE_PAIRS}


def analyse_failures(records: Sequence[EvalRecord]) -> FailureAnalysis:
    """
    Build the E6 failure picture: which failure kinds, which confusions, and a
    worked case list.

    Covers both failure families the architecture distinguishes:

    * *validation* failures - the run never produced a valid response; the
      ``first_failure`` field names which of the four ``FailureKind`` members
      caused it;
    * *misclassification* failures - the run was valid but predicted the wrong
      intent, flagged when the (gold, predicted) pair is a known confusable
      pair from ``intents.CONFUSABLE_PAIRS``.
    """
    confusable = _confusable_lookup()
    kind_counts: Counter = Counter()
    conf_counts: Counter = Counter()
    cases: list[FailureCase] = []

    for r in records:
        if not r.ok:
            kind_raw = r.row.get("first_failure")
            kind = str(kind_raw) if kind_raw is not None else None
            kind_counts[kind or "unknown"] += 1
            cases.append(
                FailureCase(
                    gold_intent=r.gold_intent,
                    predicted_intent=None,
                    failure_kind=kind,
                    is_confusable_pair=False,
                    note=_validation_note(kind),
                )
            )
        elif r.predicted_intent != r.gold_intent:
            pred = r.predicted_intent
            conf_counts[(r.gold_intent, pred or "<none>")] += 1
            is_pair = frozenset((r.gold_intent, pred or "")) in confusable
            cases.append(
                FailureCase(
                    gold_intent=r.gold_intent,
                    predicted_intent=pred,
                    failure_kind=None,
                    is_confusable_pair=is_pair,
                    note=_misclassification_note(r.gold_intent, pred, is_pair),
                )
            )

    return FailureAnalysis(
        failure_kind_counts=dict(kind_counts),
        confusion_counts=dict(conf_counts),
        cases=cases,
    )


def _validation_note(kind: str | None) -> str:
    notes = {
        FailureKind.NO_JSON_FOUND.value: (
            "Model emitted no balanced JSON object; a formatting failure, not a "
            "classification error. Targeted by the constraint-based prompt."
        ),
        FailureKind.MALFORMED_JSON.value: (
            "JSON object present but not parseable. Usually a trailing comma or "
            "an unescaped quote inside the response string."
        ),
        FailureKind.SCHEMA_VIOLATION.value: (
            "Parsed but violated the pydantic contract - a missing field, a "
            "bad type, or an invented extra field under extra='forbid'."
        ),
        FailureKind.UNKNOWN_INTENT.value: (
            "Schema-valid but the label is not one of the 77 BANKING77 names. "
            "The clearest hallucination signal on this task."
        ),
    }
    return notes.get(kind or "", "Unclassified validation failure.")


def _misclassification_note(gold: str, pred: str | None, is_pair: bool) -> str:
    theme = theme_of(gold)
    if is_pair:
        return (
            f"Predicted confusable pair: '{gold}' vs '{pred}'. These overlap by "
            "definition in BANKING77, a predicted E6 failure mode."
        )
    if pred and theme and theme_of(pred) == theme:
        return (
            f"Within-theme confusion in '{theme}': '{gold}' vs '{pred}'. Same "
            "service area, finer-grained distinction missed."
        )
    return f"Cross-theme misclassification: '{gold}' predicted as '{pred}'."


# --------------------------------------------------------------------------
# One-call summary
# --------------------------------------------------------------------------


def evaluate_run(records: Sequence[EvalRecord], *, with_macro_f1: bool = True) -> dict:
    """
    Compute every metric for one experiment condition and return a flat dict.

    Convenience for the notebook: one condition (a prompt variant under a
    decoding config) in, one row of the results table out. ``with_macro_f1``
    can be turned off where scikit-learn is unavailable so accuracy and the
    other five metrics still compute.
    """
    if not records:
        raise ValueError("cannot evaluate an empty record set")

    validity = schema_validity(records)
    routing = tool_routing(records)
    latency = latency_and_cost(records)

    n = len(records)
    n_correct = sum(1 for r in records if r.correct)
    summary: dict = {
        "n": n,
        "accuracy": round(n_correct / n, 4),
    }

    if with_macro_f1:
        summary["macro_f1"] = intent_accuracy(records).as_dict()["macro_f1"]

    summary.update(
        {
            "schema_" + k: v for k, v in validity.as_dict().items() if k != "n"
        }
    )
    summary.update({"tool_" + k: v for k, v in routing.as_dict().items()})
    summary.update(
        {k: v for k, v in latency.as_dict().items() if k != "n"}
    )
    return summary


def results_dataframe(rows: Sequence[Mapping[str, object]]):
    """
    Assemble per-condition summary rows into a pandas DataFrame.

    pandas is imported here, not at module top, so the package still imports
    with only pydantic. Used to render the E2/E3 comparison tables in the
    notebook and the report.
    """
    try:
        import pandas as pd
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise ImportError(
            "results_dataframe needs pandas; install it or run in Colab."
        ) from exc
    return pd.DataFrame(list(rows))


__all__ = [
    "AccuracyReport",
    "EvalRecord",
    "FailureAnalysis",
    "FailureCase",
    "LatencyReport",
    "StabilityReport",
    "ToolRoutingReport",
    "ValidityReport",
    "analyse_failures",
    "confusion_counts",
    "evaluate_run",
    "flag_unsafe_responses",
    "intent_accuracy",
    "latency_and_cost",
    "records_from_rows",
    "results_dataframe",
    "schema_validity",
    "self_consistency",
    "tool_routing",
]
