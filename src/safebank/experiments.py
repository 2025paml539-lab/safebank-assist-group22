"""
Experiment runner for E2, E3 and E6 (Report sections 7, 8, 11 and 12).

``prompts``, ``decoding`` and ``evaluate`` supply the pieces. This module wires
them into the three sweeps the report needs, so the Colab notebook is a thin
caller and everything with logic in it is unit-tested offline.

The one design problem: speed without touching the pipeline
-----------------------------------------------------------
``SafeBankPipeline.run`` handles one query at a time and calls
``generator.generate`` for one prompt at a time. On a free T4 that is the
difference between hours and minutes: ``HFGenerator.generate_batch`` runs many
prompts in one forward pass, but the pipeline cannot use it, and ``pipeline.py``
is frozen.

:class:`PrefetchingGenerator` closes that gap without changing the pipeline.
It batch-generates every first-attempt prompt up front, then serves them back
from a cache when the unchanged pipeline asks for them one by one. Anything the
cache does not hold, which in practice is the rare repair prompt, falls through
to ordinary single-prompt generation. The pipeline therefore still performs
validation, the repair loop, the confidence gate, tool routing and the safety
screen exactly as it does in production; only *where the first completion comes
from* differs. ``hits`` and ``misses`` are recorded, so a change in the
pipeline's prompt construction shows up as misses (slower, still correct)
instead of as silently different results.

Two caveats worth stating in the report:

* Batched greedy output can differ from unbatched output in rare cases,
  because padding changes floating-point accumulation. Keep ``batch_size``
  fixed within an experiment and record it (it is stored in each result).
* A sampled batch is seeded once per call, so a sampled result depends on the
  batch it ran in. Same remedy: fixed batch size.

Latency is amortised: a prefetched completion is charged its share of the
batch wall time, as ``HFGenerator`` records it, so criterion 5 stays meaningful.

Heavy imports are not needed here; the model runtime arrives through the
``generator`` argument.

Owner: Satya Prakash (experiments and evaluation, E2/E3/E6)
"""

from __future__ import annotations

import json
import re
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping, Sequence

from . import config, prompts
from .decoding import DEFAULT_SEEDS, GridPoint, build_decoding_grid, seed_variations
from .evaluate import (
    EvalRecord,
    FailureAnalysis,
    analyse_failures,
    evaluate_run,
    records_from_rows,
    response_safety,
    self_consistency,
)
from .generator import DecodeConfig, TextGenerator
from .intents import theme_of
from .pipeline import PipelineResult, SafeBankPipeline
from .prompts import PromptStrategy

#: Default number of prompts per forward pass. Fixed within an experiment and
#: stored in every result; a T4 handles 16 prompts of ~800 tokens comfortably.
DEFAULT_BATCH_SIZE: int = 16

#: Columns of the E2 comparison table in report section 7, in order.
E2_COLUMNS: tuple[str, ...] = (
    "strategy",
    "accuracy",
    "macro_f1",
    "schema_first_attempt_rate",
    "schema_final_rate",
    "tool_routing_accuracy",
    "escalation_rate",
    "requires_human_rate",
    "safety_unsafe_rate",
    "mean_attempts",
    "mean_latency_ms",
)


# --------------------------------------------------------------------------
# Batched replay of first-attempt prompts
# --------------------------------------------------------------------------


class PrefetchingGenerator:
    """
    A ``TextGenerator`` that serves pre-computed batch completions.

    ``prefetch`` fills the cache with batched completions for a list of
    prompts under one ``DecodeConfig``. ``generate`` then returns the cached
    completion for a matching ``(prompt, decode)`` and otherwise delegates to
    the wrapped generator. Duplicate prompts are queued, not overwritten, so
    two identical eval queries each get their own completion.
    """

    def __init__(self, inner: TextGenerator, batch_size: int = DEFAULT_BATCH_SIZE):
        if batch_size <= 0:
            raise ValueError(f"batch_size must be positive, got {batch_size}")
        self.inner = inner
        self.batch_size = batch_size
        self.hits = 0
        self.misses = 0
        self._cache: dict[tuple[str, DecodeConfig], deque[tuple[str, float]]] = {}
        self._hit_ms = 0.0

    def prefetch(self, prompts_: Sequence[str], decode: DecodeConfig) -> None:
        """Batch-generate ``prompts_`` and queue the completions."""
        batch_fn = getattr(self.inner, "generate_batch", None)
        for start in range(0, len(prompts_), self.batch_size):
            chunk = list(prompts_[start : start + self.batch_size])
            began = time.perf_counter()
            if batch_fn is not None:
                outputs = batch_fn(chunk, decode)
            else:
                outputs = [self.inner.generate(p, decode) for p in chunk]
            if len(outputs) != len(chunk):
                raise RuntimeError(
                    f"generator returned {len(outputs)} completions for "
                    f"{len(chunk)} prompts"
                )
            share_ms = (time.perf_counter() - began) * 1000 / len(chunk)
            for prompt, output in zip(chunk, outputs):
                self._cache.setdefault((prompt, decode), deque()).append(
                    (output, share_ms)
                )

    def generate(self, prompt: str, decode: DecodeConfig) -> str:
        queue = self._cache.get((prompt, decode))
        if queue:
            output, share_ms = queue.popleft()
            self.hits += 1
            self._hit_ms += share_ms
            return output
        self.misses += 1
        return self.inner.generate(prompt, decode)

    def take_hit_ms(self) -> float:
        """Amortised batch time of the cached completions served since last call."""
        taken, self._hit_ms = self._hit_ms, 0.0
        return taken


# --------------------------------------------------------------------------
# One experimental condition
# --------------------------------------------------------------------------


@dataclass
class ConditionResult:
    """Everything one (prompt strategy, decoding config) run produced."""

    strategy: PromptStrategy
    decode: DecodeConfig
    records: list[EvalRecord]
    results: list[PipelineResult]
    meta: dict = field(default_factory=dict)

    def summary(self, *, with_macro_f1: bool = True) -> dict:
        """One row of the results table: identity + every metric."""
        row: dict = {
            "strategy": self.strategy.value,
            "decoding": self.decode.label(),
            "seed": self.decode.seed,
        }
        row.update(evaluate_run(self.records, with_macro_f1=with_macro_f1))
        n = len(self.results)
        asked = sum(
            1 for r in self.results if r.response is not None and r.response.requires_human
        )
        row["requires_human_rate"] = round(asked / n, 4) if n else 0.0
        return row

    def predictions(self) -> list[str | None]:
        """Predicted intent per query (None when no valid response)."""
        return [r.predicted_intent if r.ok else None for r in self.records]


def run_condition(
    generator: TextGenerator,
    labels: Sequence[str],
    rows: Sequence[Mapping[str, str]],
    strategy: PromptStrategy,
    decode: DecodeConfig,
    *,
    prompt_kwargs: Mapping[str, object] | None = None,
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> ConditionResult:
    """
    Run every row through the real pipeline under one strategy and decoding.

    ``rows`` are ``{"query", "gold_intent"}`` dicts as built by
    ``data_prep.build_eval_sample``. First-attempt prompts are batch-generated
    through :class:`PrefetchingGenerator`; the pipeline itself is unchanged.
    """
    if not rows:
        raise ValueError("rows is empty")

    kwargs = dict(prompt_kwargs or {})
    prefetching = PrefetchingGenerator(generator, batch_size)
    pipeline = SafeBankPipeline(prefetching, list(labels), strategy, prompt_kwargs=kwargs)

    first_prompts = [
        prompts.build_prompt(strategy, row["query"], labels, **kwargs) for row in rows
    ]
    began = time.perf_counter()
    prefetching.prefetch(first_prompts, decode)

    results: list[PipelineResult] = []
    out_rows: list[dict] = []
    for row in rows:
        result = pipeline.run(row["query"], decode)
        flat = result.to_row()
        flat["latency_ms"] = round(flat["latency_ms"] + prefetching.take_hit_ms(), 1)
        results.append(result)
        out_rows.append(flat)

    meta = {
        "n": len(rows),
        "batch_size": batch_size,
        "cache_hits": prefetching.hits,
        "cache_misses": prefetching.misses,
        "wall_seconds": round(time.perf_counter() - began, 2),
        "latency_basis": "amortised batch time per prompt",
    }
    records = records_from_rows(out_rows, [row["gold_intent"] for row in rows])
    return ConditionResult(strategy, decode, records, results, meta)


# --------------------------------------------------------------------------
# E2: prompt strategies
# --------------------------------------------------------------------------


def assert_no_overlap(
    example_bank: Sequence[tuple[str, str]], eval_rows: Sequence[Mapping[str, str]]
) -> None:
    """
    Refuse to run if a few-shot example is also an evaluation query.

    Few-shot examples must come from the train split only; a text that appears
    in both splits would contaminate every E2 number. ``data_prep`` already
    supports ``exclude=``; this is the check that it was actually used.
    """
    eval_queries = {row["query"] for row in eval_rows}
    clash = [query for query, _ in example_bank if query in eval_queries]
    if clash:
        raise ValueError(
            f"{len(clash)} few-shot example(s) are also evaluation queries "
            f"(first: {clash[0]!r}). Build the bank with "
            "build_example_bank(..., exclude={r['query'] for r in eval_rows})."
        )


def strategy_kwargs(
    strategy: PromptStrategy, example_bank: Sequence[tuple[str, str]]
) -> dict[str, object]:
    """
    Extra ``build_prompt`` arguments a strategy needs.

    Only few-shot takes any: the real train-split bank, all of it. Used by E2
    and again by E3, which may run on a few-shot winner and would otherwise
    silently fall back to the illustrative bank.
    """
    if strategy is PromptStrategy.FEW_SHOT:
        return {"examples": list(example_bank), "n_examples": len(example_bank)}
    return {}


def run_e2(
    generator: TextGenerator,
    labels: Sequence[str],
    eval_rows: Sequence[Mapping[str, str]],
    example_bank: Sequence[tuple[str, str]],
    *,
    strategies: Sequence[PromptStrategy] = tuple(PromptStrategy),
    decode: DecodeConfig | None = None,
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> list[ConditionResult]:
    """
    E2: the same pipeline, once per prompt strategy, greedy decoding.

    Greedy is the fixed reference so the only thing varying is the strategy.
    Few-shot receives the real train-split ``example_bank``; the other three
    take no extra arguments.
    """
    assert_no_overlap(example_bank, eval_rows)
    decode = decode or DecodeConfig()
    return [
        run_condition(
            generator,
            labels,
            eval_rows,
            strategy,
            decode,
            prompt_kwargs=strategy_kwargs(strategy, example_bank),
            batch_size=batch_size,
        )
        for strategy in strategies
    ]


def report_table(
    results: Sequence[ConditionResult],
    columns: Sequence[str] = E2_COLUMNS,
    *,
    with_macro_f1: bool = True,
) -> list[dict]:
    """Summaries restricted to ``columns``, ready for the section 7 table."""
    table = []
    for result in results:
        summary = result.summary(with_macro_f1=with_macro_f1)
        table.append({col: summary[col] for col in columns if col in summary})
    return table


def best_condition(
    results: Sequence[ConditionResult], *, with_macro_f1: bool = True
) -> ConditionResult:
    """Highest accuracy, ties broken by macro-F1 (or by schema validity without it)."""
    if not results:
        raise ValueError("no results to choose from")

    def key(result: ConditionResult):
        s = result.summary(with_macro_f1=with_macro_f1)
        return (s["accuracy"], s.get("macro_f1", s["schema_final_rate"]))

    return max(results, key=key)


# --------------------------------------------------------------------------
# E3: decoding grid
# --------------------------------------------------------------------------


def select_e3_subset(eval_rows: Sequence[Mapping[str, str]]) -> list[dict]:
    """
    The stratified E3 subset: one query per intent (77 rows for 77 intents).

    E3 measures decoding behaviour and stability, not accuracy to two decimal
    places, so it does not need all 385 rows. Taking the first row of each
    intent in the frozen eval sample keeps the choice deterministic and a
    strict subset of the E2 rows.
    """
    seen: set[str] = set()
    subset: list[dict] = []
    for row in eval_rows:
        if row["gold_intent"] not in seen:
            seen.add(row["gold_intent"])
            subset.append(dict(row))
    return subset


@dataclass
class GridResult:
    """One decoding configuration, run once per seed (greedy: once)."""

    point: GridPoint
    runs: list[ConditionResult]

    def stability(self):
        """Self-consistency across seeds, or None for a deterministic config."""
        if len(self.runs) < 2:
            return None
        per_query = list(zip(*(run.predictions() for run in self.runs)))
        return self_consistency(per_query)

    def summary(self, *, with_macro_f1: bool = False) -> dict:
        """Mean and spread over seeds, plus the stability scores."""
        per_run = [run.summary(with_macro_f1=with_macro_f1) for run in self.runs]

        def mean(key: str) -> float:
            return round(sum(s[key] for s in per_run) / len(per_run), 4)

        accuracies = [s["accuracy"] for s in per_run]
        row = {
            "decoding": self.point.label,
            "n_runs": len(self.runs),
            "accuracy_mean": mean("accuracy"),
            "accuracy_min": min(accuracies),
            "accuracy_max": max(accuracies),
            "schema_first_attempt_rate": mean("schema_first_attempt_rate"),
            "schema_final_rate": mean("schema_final_rate"),
            "escalation_rate": mean("escalation_rate"),
            "mean_attempts": mean("mean_attempts"),
        }
        stability = self.stability()
        row["mean_agreement"] = (
            round(stability.mean_agreement, 4) if stability else None
        )
        row["fully_stable_fraction"] = (
            round(stability.fully_stable_fraction, 4) if stability else None
        )
        return row


def run_e3(
    generator: TextGenerator,
    labels: Sequence[str],
    subset_rows: Sequence[Mapping[str, str]],
    strategy: PromptStrategy,
    *,
    grid: Sequence[GridPoint] | None = None,
    seeds: Sequence[int] = DEFAULT_SEEDS,
    prompt_kwargs: Mapping[str, object] | None = None,
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> list[GridResult]:
    """
    E3: every decoding configuration over the subset, each sampled one per seed.

    ``strategy`` is required on purpose: E3 should run on the best E2 strategy,
    which is a decision the caller makes from the E2 table, not a default.
    """
    points = grid if grid is not None else build_decoding_grid()
    out: list[GridResult] = []
    for point in points:
        runs = [
            run_condition(
                generator,
                labels,
                subset_rows,
                strategy,
                cfg,
                prompt_kwargs=prompt_kwargs,
                batch_size=batch_size,
            )
            for cfg in seed_variations(point.config, seeds)
        ]
        out.append(GridResult(point, runs))
    return out


def sample_outputs(grid_results: Sequence[GridResult], k: int = 3) -> dict[str, list[dict]]:
    """First ``k`` model replies per configuration (first seed), for section 8."""
    samples: dict[str, list[dict]] = {}
    for grid_result in grid_results:
        run = grid_result.runs[0]
        samples[grid_result.point.label] = [
            {
                "query": record.row["query"],
                "intent": record.row.get("intent"),
                "response": record.row.get("response"),
            }
            for record in run.records[:k]
        ]
    return samples


def variability_examples(grid_result: GridResult, k: int = 3) -> list[dict]:
    """Queries where the seeds disagree on the intent: the visible cost of sampling."""
    if len(grid_result.runs) < 2:
        return []
    examples = []
    for i, preds in enumerate(zip(*(run.predictions() for run in grid_result.runs))):
        if len(set(preds)) > 1:
            examples.append(
                {
                    "query": grid_result.runs[0].records[i].row["query"],
                    "gold_intent": grid_result.runs[0].records[i].gold_intent,
                    "predictions_by_seed": list(preds),
                }
            )
            if len(examples) == k:
                break
    return examples


# --------------------------------------------------------------------------
# E6: comparison and failure cases
# --------------------------------------------------------------------------

_COMPARED_METRICS: tuple[str, ...] = (
    "accuracy",
    "macro_f1",
    "schema_first_attempt_rate",
    "schema_final_rate",
    "tool_routing_accuracy",
    "escalation_rate",
    "safety_unsafe_rate",
    "mean_attempts",
    "mean_latency_ms",
)


def compare_conditions(
    baseline: ConditionResult, final: ConditionResult, *, with_macro_f1: bool = True
) -> list[dict]:
    """Baseline vs final, one row per metric with the signed change."""
    before = baseline.summary(with_macro_f1=with_macro_f1)
    after = final.summary(with_macro_f1=with_macro_f1)
    return [
        {
            "metric": metric,
            "baseline": before[metric],
            "final": after[metric],
            "change": round(after[metric] - before[metric], 4),
        }
        for metric in _COMPARED_METRICS
        if metric in before and metric in after
    ]


def _failure_category(case: Mapping[str, object]) -> str:
    if case["failure_kind"]:
        return f"validation:{case['failure_kind']}"
    if case["is_confusable_pair"]:
        return "confusable_pair"
    gold, pred = case["gold_intent"], case["predicted_intent"]
    if pred and theme_of(str(gold)) is not None and theme_of(str(gold)) == theme_of(str(pred)):
        return "within_theme"
    return "cross_theme"


def failure_cases(condition: ConditionResult, n: int = 6) -> list[dict]:
    """
    Up to ``n`` analysed failures, spread across different failure classes.

    E6 needs at least three cases with root causes. Taking the first ``n``
    failures would usually return several of the same kind, so cases are drawn
    round-robin across classes (each validation failure kind, confusable pair,
    within-theme, cross-theme). Each case carries the query and the model's own
    reply so the report can quote it, next to the analysis note.
    """
    analysis: FailureAnalysis = analyse_failures(condition.records)
    failing = [
        r for r in condition.records if (not r.ok) or r.predicted_intent != r.gold_intent
    ]
    if len(failing) != len(analysis.cases):
        raise RuntimeError("failure analysis and failing records are out of step")

    enriched = []
    for record, case in zip(failing, analysis.cases):
        entry = case.as_dict()
        entry["query"] = record.row.get("query")
        entry["reply"] = record.row.get("response")
        entry["category"] = _failure_category(entry)
        enriched.append(entry)

    buckets: dict[str, list[dict]] = {}
    for entry in enriched:
        buckets.setdefault(entry["category"], []).append(entry)

    chosen: list[dict] = []
    while len(chosen) < n and any(buckets.values()):
        for category in sorted(buckets):
            if buckets[category] and len(chosen) < n:
                chosen.append(buckets[category].pop(0))
    return chosen


def safety_findings(condition: ConditionResult) -> list[dict]:
    """Replies the safety screen flagged, with the query, for criterion 4."""
    report = response_safety(condition.records)
    return [
        {
            "query": condition.records[i].row.get("query"),
            "gold_intent": condition.records[i].gold_intent,
            "reply": condition.records[i].row.get("response"),
            "issues": condition.records[i].row.get("safety_issues"),
            "withheld": condition.records[i].row.get("reply_withheld"),
        }
        for i in report.flagged_indices
    ]


# --------------------------------------------------------------------------
# Persistence: results are report evidence
# --------------------------------------------------------------------------


def _decode_dict(decode: DecodeConfig) -> dict:
    return {
        "strategy": decode.strategy.value,
        "temperature": decode.temperature,
        "top_k": decode.top_k,
        "top_p": decode.top_p,
        "max_new_tokens": decode.max_new_tokens,
        "seed": decode.seed,
    }


def condition_payload(condition: ConditionResult) -> dict:
    """JSON-serialisable record of a run, with the raw text of every attempt."""
    rows = []
    for record, result in zip(condition.records, condition.results):
        row = dict(record.row)
        row["gold_intent"] = record.gold_intent
        row["attempts_raw"] = [
            {"is_repair": a.is_repair, "raw": a.raw, "ok": a.outcome.ok}
            for a in result.attempts
        ]
        rows.append(row)
    return {
        "strategy": condition.strategy.value,
        "decode": _decode_dict(condition.decode),
        "meta": condition.meta,
        "summary": condition.summary(with_macro_f1=False),
        "rows": rows,
    }


def save_json(payload: object, name: str, directory: Path | None = None) -> Path:
    """Write ``payload`` to ``<directory>/<name>.json`` (default: results dir)."""
    target_dir = Path(directory) if directory is not None else config.RESULTS_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    path = target_dir / f"{name}.json"
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def save_condition(
    condition: ConditionResult, name: str, directory: Path | None = None
) -> Path:
    """Persist one run (rows, raw attempts, metadata) as JSON."""
    return save_json(condition_payload(condition), name, directory)


def slug(text: str) -> str:
    """File-name-safe form of a label such as ``top_k=50 temp=0.7``."""
    cleaned = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    return cleaned or "run"


def save_grid(
    grid_results: Sequence[GridResult],
    prefix: str = "e3",
    directory: Path | None = None,
) -> list[Path]:
    """
    Persist every run of an E3 grid, one file per (configuration, seed).

    Names look like ``e3_top_k_50_temp_0_7_seed43``, so a single run can be
    re-opened later without re-running the sweep.
    """
    paths = []
    for grid_result in grid_results:
        for run in grid_result.runs:
            name = f"{prefix}_{slug(grid_result.point.label)}_seed{run.decode.seed}"
            paths.append(save_condition(run, name, directory))
    return paths


__all__ = [
    "DEFAULT_BATCH_SIZE",
    "E2_COLUMNS",
    "ConditionResult",
    "GridResult",
    "PrefetchingGenerator",
    "assert_no_overlap",
    "best_condition",
    "compare_conditions",
    "condition_payload",
    "failure_cases",
    "report_table",
    "run_condition",
    "run_e2",
    "run_e3",
    "safety_findings",
    "sample_outputs",
    "save_condition",
    "save_grid",
    "save_json",
    "select_e3_subset",
    "slug",
    "strategy_kwargs",
    "variability_examples",
]
