"""
Decoding configuration grid (Experiment E3, Report section 8).

E3 compares how the *same* model and the *same* prompt behave under different
decoding strategies: greedy, temperature sampling, top-k and top-p. This
module builds that grid. It does NOT redefine ``DecodeConfig`` or
``DecodeStrategy`` - those live in ``generator.py`` and are the frozen seam the
pipeline already depends on. This module only *assembles* configurations on top
of them, so an E3 run is a data change, never a code change in the pipeline.

Two things E3 measures:

* **Quality / behaviour across strategies.** One config per strategy, run over
  the evaluation sample, compared on the metrics in ``evaluate.py``.
* **Output stability (self-consistency, evaluation criterion 6).** The same
  sampled config run under several seeds; a strategy that returns a different
  intent each time is less reliable even if its single-run accuracy is high.
  Greedy is deterministic and is the fixed reference point for that study.

Every configuration is a frozen ``DecodeConfig``, so each row logged in the E3
table is traceable to an exact, printable setting.

Owner: Satya Prakash (experiments and evaluation, E3)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from . import config
from .generator import DecodeConfig, DecodeStrategy

# --------------------------------------------------------------------------
# Default grid parameters
# --------------------------------------------------------------------------

#: Sampling temperature applied to every non-greedy config in the default
#: grid. A single shared value keeps the comparison honest: temperature is held
#: constant so a difference between top-k and top-p is attributable to the
#: truncation scheme, not to a different temperature.
DEFAULT_TEMPERATURE: float = 0.7

#: A second, hotter temperature so the grid shows the effect of temperature
#: itself, not only of the truncation strategy.
DEFAULT_HOT_TEMPERATURE: float = 1.2

#: top-k cutoff for the top-k config.
DEFAULT_TOP_K: int = 50

#: nucleus mass for the top-p config.
DEFAULT_TOP_P: float = 0.9

#: Seeds used for the self-consistency study. Derived from the project seed so
#: the variability measurement is reproducible. Five seeds is enough to see
#: whether a sampled strategy is stable without exploding the inference budget.
DEFAULT_SEEDS: tuple[int, ...] = tuple(config.SEED + offset for offset in range(5))


# --------------------------------------------------------------------------
# A labelled point in the grid
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class GridPoint:
    """One decoding configuration plus a stable label and a short rationale.

    The label is what appears in the E3 results table; the rationale is quoted
    in the report so no decoding setting is unexplained (Section 8 of the
    brief forbids unexplained choices).
    """

    config: DecodeConfig
    label: str
    rationale: str

    @property
    def strategy(self) -> DecodeStrategy:
        return self.config.strategy


# --------------------------------------------------------------------------
# The default E3 grid
# --------------------------------------------------------------------------


def build_decoding_grid(
    *,
    temperature: float = DEFAULT_TEMPERATURE,
    hot_temperature: float = DEFAULT_HOT_TEMPERATURE,
    top_k: int = DEFAULT_TOP_K,
    top_p: float = DEFAULT_TOP_P,
    max_new_tokens: int | None = None,
    seed: int | None = None,
) -> tuple[GridPoint, ...]:
    """
    Build the six-configuration E3 decoding grid.

    The grid covers every strategy required by Requirement 7 and Experiment E3
    (greedy, temperature, top-k, top-p), with temperature represented at two
    settings so the effect of temperature is separable from the effect of the
    truncation scheme.

    Parameters
    ----------
    temperature:
        Baseline sampling temperature shared by the sampled configs.
    hot_temperature:
        A higher temperature, to show temperature's own effect.
    top_k:
        Cutoff for the top-k config.
    top_p:
        Nucleus mass for the top-p config.
    max_new_tokens:
        Override the generation length. Defaults to ``config.MAX_NEW_TOKENS``
        via ``DecodeConfig``.
    seed:
        Override the base seed. Defaults to ``config.SEED`` via ``DecodeConfig``.

    Returns
    -------
    tuple[GridPoint, ...]
        Six configurations, each labelled and with a written rationale.
    """
    extra: dict = {}
    if max_new_tokens is not None:
        extra["max_new_tokens"] = max_new_tokens
    if seed is not None:
        extra["seed"] = seed

    points = (
        GridPoint(
            config=DecodeConfig(strategy=DecodeStrategy.GREEDY, **extra),
            label="greedy",
            rationale=(
                "Deterministic argmax decoding. The reproducible reference "
                "point for E3 and the fixed baseline for the self-consistency "
                "study, since its output cannot vary across seeds."
            ),
        ),
        GridPoint(
            config=DecodeConfig(
                strategy=DecodeStrategy.TEMPERATURE,
                temperature=temperature,
                **extra,
            ),
            label=f"temperature={temperature}",
            rationale=(
                "Moderate-temperature sampling. Introduces controlled variety "
                "while keeping the distribution close to the model's argmax; "
                "the honest middle ground between greedy and hot sampling."
            ),
        ),
        GridPoint(
            config=DecodeConfig(
                strategy=DecodeStrategy.TEMPERATURE,
                temperature=hot_temperature,
                **extra,
            ),
            label=f"temperature={hot_temperature}",
            rationale=(
                "High-temperature sampling. Flattens the distribution to expose "
                "the reliability cost of sampling: expected to raise output "
                "variability and lower intent accuracy versus the moderate "
                "setting, isolating temperature's own effect."
            ),
        ),
        GridPoint(
            config=DecodeConfig(
                strategy=DecodeStrategy.TOP_K,
                temperature=temperature,
                top_k=top_k,
                **extra,
            ),
            label=f"top_k={top_k} temp={temperature}",
            rationale=(
                "Top-k truncation: sample only from the k most probable tokens. "
                "Caps the long tail with a fixed-size candidate set; compared "
                "against top-p at the same temperature so the difference is the "
                "truncation scheme, not the temperature."
            ),
        ),
        GridPoint(
            config=DecodeConfig(
                strategy=DecodeStrategy.TOP_P,
                temperature=temperature,
                top_p=top_p,
                **extra,
            ),
            label=f"top_p={top_p} temp={temperature}",
            rationale=(
                "Nucleus (top-p) truncation: sample from the smallest set whose "
                "cumulative probability reaches p. Adapts the candidate-set size "
                "to the model's certainty, unlike the fixed k of top-k."
            ),
        ),
        GridPoint(
            config=DecodeConfig(
                strategy=DecodeStrategy.TOP_P,
                temperature=temperature,
                top_p=0.95,
                **extra,
            ),
            label=f"top_p=0.95 temp={temperature}",
            rationale=(
                "A looser nucleus than the 0.9 config, admitting more of the "
                "tail. Shows how sensitive top-p behaviour is to the p cutoff "
                "while holding the strategy and temperature fixed."
            ),
        ),
    )
    return points


def grid_configs(
    grid: Sequence[GridPoint] | None = None,
) -> tuple[DecodeConfig, ...]:
    """Return just the ``DecodeConfig`` objects from a grid (default grid if None)."""
    points = grid if grid is not None else build_decoding_grid()
    return tuple(point.config for point in points)


# --------------------------------------------------------------------------
# Self-consistency (evaluation criterion 6)
# --------------------------------------------------------------------------


def seed_variations(
    base: DecodeConfig,
    seeds: Sequence[int] = DEFAULT_SEEDS,
) -> tuple[DecodeConfig, ...]:
    """
    Produce copies of ``base`` under several seeds for the stability study.

    Greedy decoding is deterministic, so varying its seed cannot change the
    output; this returns a single greedy config in that case rather than
    pretending to measure variability that cannot exist.

    Parameters
    ----------
    base:
        The configuration whose stability is being measured.
    seeds:
        The seeds to apply. Defaults to :data:`DEFAULT_SEEDS`.

    Returns
    -------
    tuple[DecodeConfig, ...]
        One config per seed for a sampled strategy; exactly one config for
        greedy.
    """
    if not base.do_sample:
        return (base,)
    if not seeds:
        raise ValueError("seeds must be non-empty for a sampled configuration")
    return tuple(base.with_seed(seed) for seed in seeds)


def self_consistency_configs(
    grid: Sequence[GridPoint] | None = None,
    seeds: Sequence[int] = DEFAULT_SEEDS,
) -> dict[str, tuple[DecodeConfig, ...]]:
    """
    Map each grid point's label to its seed-varied configurations.

    This is the exact set of runs the self-consistency metric in
    ``evaluate.py`` consumes: for each sampled strategy, the same prompt is
    decoded under every seed and the agreement of the predicted intents is the
    stability score. Greedy contributes one run and is the deterministic
    anchor.
    """
    points = grid if grid is not None else build_decoding_grid()
    return {point.label: seed_variations(point.config, seeds) for point in points}


__all__ = [
    "DEFAULT_HOT_TEMPERATURE",
    "DEFAULT_SEEDS",
    "DEFAULT_TEMPERATURE",
    "DEFAULT_TOP_K",
    "DEFAULT_TOP_P",
    "GridPoint",
    "build_decoding_grid",
    "grid_configs",
    "seed_variations",
    "self_consistency_configs",
]
