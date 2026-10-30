"""
Build the SafeBank Assist technical report (PDF) from the Markdown sections.

    python report/build_report.py               # draft PDF; lists pending items, stamps DRAFT
    python report/build_report.py --final       # refuses to finish while anything is pending
    python report/build_report.py --offline     # reuse report/generated/ instead of re-reading the data
    python report/build_report.py --assets-only # regenerate figures and generated/ blocks, no PDF
    python report/build_report.py --preview     # also render page images to report/build/preview/

Pipeline: dataset facts and figures -> appendix blocks generated from the code
-> Markdown -> HTML -> PDF (Microsoft Edge, headless) -> footer, page numbers
and checks (PyMuPDF).

Read-only with respect to the application: it imports ``safebank`` from src/
and never writes there. Downloaded dataset files are cached in artifacts/data/,
which is git-ignored. Needs nothing beyond what is already used by the project
plus markdown-it-py, matplotlib, PyMuPDF and Microsoft Edge.
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import random
import re
import shutil
import statistics
import subprocess
import sys
import unittest
from collections import Counter
from pathlib import Path
from types import SimpleNamespace

REPORT = Path(__file__).resolve().parent
PROJECT = REPORT.parent
SECTIONS = REPORT / "sections"
GENERATED = REPORT / "generated"
ASSETS = REPORT / "assets"
BUILD = REPORT / "build"
PDF_NAME = "SafeBank_Assist_Group22_Report.pdf"
REPO_URL = "https://github.com/2025paml539-lab/safebank-assist-group22"

sys.path.insert(0, str(PROJECT / "src"))

#: Section headings the brief's suggested structure requires, in order.
REQUIRED_HEADINGS = (
    "1. Abstract",
    "2. Problem statement and motivation",
    "3. Dataset description and preparation",
    "4. Generative-model and LLM architecture analysis",
    "5. Proposed application architecture",
    "6. Baseline LLM implementation",
    "7. Prompt-engineering experiments",
    "8. Decoding experiments",
    "9. Adaptation strategy: prompting vs RAG vs PEFT",
    "10. Structured output and tool/function calling",
    "11. Evaluation and results",
    "12. Failure analysis and responsible-use considerations",
    "13. Limitations",
    "14. Conclusion and future work",
    "References",
    "Appendix",
)

#: Generic text that must never appear in a published document. The current
#: login name is added at run time, and further private phrases can be listed one
#: per line in report/build/forbidden_phrases.txt, which is git-ignored, so the
#: check never has to publish the very words it guards against.
FORBIDDEN = ("company laptop", "work laptop", "this machine", "development machine", "appdata", "c:\\users\\")


def forbidden_phrases() -> list[str]:
    phrases = list(FORBIDDEN)
    user = os.environ.get("USERNAME") or os.environ.get("USER") or ""
    if len(user) >= 4:
        phrases.append(user.lower())
    extra = BUILD / "forbidden_phrases.txt"
    if extra.exists():
        phrases += [l.strip().lower() for l in extra.read_text(encoding="utf-8").splitlines() if l.strip()]
    return phrases

MARKER = re.compile(r"\[\[(.+?)\]\]", re.S)
INCLUDE = re.compile(r"<!--\s*include:\s*(\S+)\s*-->")


# ==========================================================================
# Small helpers
# ==========================================================================


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def md_escape(text: str, keep_emphasis: bool = False) -> str:
    """Escape a value for a Markdown table cell.

    ``keep_emphasis`` leaves ``*`` and ``_`` alone, for prose taken from the code
    whose author used ``*word*`` for emphasis.
    """
    chars = ("\\", "|", "`", "<", ">", "[", "]") if keep_emphasis else ("\\", "|", "*", "_", "`", "<", ">", "[", "]")
    for ch in chars:
        text = text.replace(ch, "\\" + ch)
    return text


def fence(text: str, lang: str = "") -> str:
    """Wrap text in a code fence longer than any backtick run inside it."""
    longest = max((len(m) for m in re.findall(r"`+", text)), default=0)
    ticks = "`" * max(3, longest + 1)
    return f"{ticks}{lang}\n{text.rstrip()}\n{ticks}"


def table(header: list[str], rows: list[list[str]]) -> str:
    out = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    out += ["| " + " | ".join(r) + " |" for r in rows]
    return "\n".join(out)


def plt_module():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update({"svg.fonttype": "path", "font.family": "DejaVu Sans"})
    return plt


# ==========================================================================
# Stage 1: dataset facts, examples and figures
# ==========================================================================


class Split:
    """Minimal stand-in for ``datasets.Dataset``: column access plus label names."""

    def __init__(self, texts: list[str], labels: list[int], names: list[str]):
        self._cols = {"text": texts, "label": labels}
        self.features = {"label": SimpleNamespace(names=list(names))}

    def __getitem__(self, key: str) -> list:
        return self._cols[key]

    def __len__(self) -> int:
        return len(self._cols["text"])


def load_splits() -> tuple[list[str], Split, Split]:
    """Read the official BANKING77 files the way ``data_prep`` does, minus ``datasets``.

    Uses its own cache under report/build/data so the application's cache is untouched.
    """
    from safebank import data_prep

    root = BUILD / "data"
    names = data_prep._read_label_names(data_prep._download(data_prep.DATASET_CARD_URL, root / "README.md"))
    if len(names) != 77:
        raise SystemExit(f"expected 77 label names, got {len(names)}")
    index = {n: i for i, n in enumerate(names)}
    splits = {}
    for split, url in (("train", data_prep.TRAIN_CSV_URL), ("test", data_prep.TEST_CSV_URL)):
        texts, cats = data_prep._read_csv(data_prep._download(url, root / f"{split}.csv"))
        expected = data_prep.EXPECTED_SPLIT_SIZES[split]
        if len(texts) != expected:
            raise SystemExit(f"{split} has {len(texts)} rows, expected {expected}")
        splits[split] = Split(texts, [index[c] for c in cats], names)
    return names, splits["train"], splits["test"]


def stage_dataset() -> dict:
    from safebank import config, data_prep, intents, tools

    names, train, test = load_splits()
    report = intents.validate_label_space(names)
    train_counts = data_prep.class_distribution(train, names)
    test_counts = data_prep.class_distribution(test, names)
    words = [len(t.split()) for t in train["text"]]
    chars = [len(t) for t in train["text"]]
    both = set(train["text"]) & set(test["text"])
    within_train_dupes = sum(1 for _, c in Counter(train["text"]).items() if c > 1)
    eval_rows = data_prep.build_eval_sample(test, names)
    eval_queries = {r["query"] for r in eval_rows}
    bank = data_prep.build_example_bank(train, names, exclude=eval_queries)
    record = data_prep.preprocessing_record(train, test, eval_rows)
    n_tool = sum(1 for n in names if tools.route_intent(n) is not None)
    lo = min(train_counts, key=train_counts.get)
    hi = max(train_counts, key=train_counts.get)

    facts = {
        "train": len(train),
        "test": len(test),
        "intents": len(names),
        "label_check": report.ok,
        "train_min": (lo, train_counts[lo]),
        "train_max": (hi, train_counts[hi]),
        "train_mean": statistics.mean(train_counts.values()),
        "train_median": statistics.median(train_counts.values()),
        "test_min": min(test_counts.values()),
        "test_max": max(test_counts.values()),
        "words_mean": statistics.mean(words),
        "words_median": statistics.median(words),
        "words_p95": sorted(words)[int(0.95 * len(words)) - 1],
        "words_max": max(words),
        "chars_median": statistics.median(chars),
        "cross_split": len(both),
        "within_train_dupes": within_train_dupes,
        "eval_rows": len(eval_rows),
        "eval_intents": len({r["gold_intent"] for r in eval_rows}),
        "tool_intents": n_tool,
    }

    rows = [
        ["Splits", f"train {facts['train']:,} · test {facts['test']:,} (published sizes, checked on load)"],
        ["Fields", "`text` (customer query, English) · `label` (intent id 0–76)"],
        ["Label space", f"{facts['intents']} intents; `validate_label_space()` passes: {facts['label_check']}"],
        ["Train rows per intent", f"min {facts['train_min'][1]} (`{facts['train_min'][0]}`) · "
                                  f"max {facts['train_max'][1]} (`{facts['train_max'][0]}`) · "
                                  f"mean {facts['train_mean']:.1f} · median {facts['train_median']:.0f}"],
        ["Test rows per intent", f"min {facts['test_min']} · max {facts['test_max']}"],
        ["Query length (train)", f"median {facts['words_median']:.0f} words ({facts['chars_median']:.0f} characters) · "
                                 f"mean {facts['words_mean']:.1f} · 95th percentile {facts['words_p95']} · max {facts['words_max']}"],
        ["Duplicate texts", f"{facts['cross_split']} appear in both train and test · "
                            f"{facts['within_train_dupes']} repeated within train"],
        ["Evaluation sample", f"{facts['eval_rows']} rows from the test split, {config.EVAL_EXAMPLES_PER_INTENT} per intent, "
                              f"{facts['eval_intents']} intents, seed {config.SEED}"],
        ["Intents that route to a tool", f"{facts['tool_intents']} of {facts['intents']}; the rest are answered with text only"],
    ]
    write(GENERATED / "dataset_facts.md", table(["Property", "Value"], rows))

    # Representative examples: two intents per service theme, one train query each.
    rng = random.Random(config.SEED)
    by_intent: dict[str, list[str]] = {}
    for text, label in zip(train["text"], train["label"]):
        by_intent.setdefault(names[label], []).append(text)
    ex_rows = []
    for theme, members in intents.INTENT_THEMES.items():
        for intent in members[:2]:
            pool = [t for t in by_intent[intent] if 5 <= len(t.split()) <= 16 and t not in eval_queries]
            query = rng.choice(sorted(pool))
            tool = tools.route_intent(intent)
            route = "—" if tool is None else f"`{tool.value}`"
            ex_rows.append([theme.replace("_", " "), f"`{intent}`", md_escape(query), route])
    write(GENERATED / "dataset_examples.md",
          table(["Theme", "Intent", "Example query (train split)", "Routes to"], ex_rows))

    theme_rows = [[t.replace("_", " "), ", ".join(f"`{i}`" for i in m)] for t, m in intents.INTENT_THEMES.items()]
    write(GENERATED / "focus_themes.md", table(["Theme", "Focus intents"], theme_rows))

    bank_rows = []
    for query, payload in bank:
        p = json.loads(payload)
        if p["tool_call"]:
            outcome = f"tool `{p['tool_call']['name']}`"
        elif p["requires_human"]:
            outcome = "escalate (destructive tool)"
        else:
            outcome = "text only"
        bank_rows.append([f"`{p['intent']}`", outcome, md_escape(query)])
    write(GENERATED / "fewshot_bank.md", table(["Intent", "Routing outcome taught", "Train query"], bank_rows))

    steps = "\n".join(f"{i}. {md_escape(s)}" for i, s in enumerate(data_prep.PREPROCESSING_STEPS, 1))
    write(GENERATED / "preprocessing_steps.md", steps)
    write(GENERATED / "preprocessing_record.md", fence(json.dumps(record, indent=2), "json"))

    draw_class_distribution(names, train_counts, words, ASSETS / "class_distribution.svg")
    write(GENERATED / "_dataset_facts.json", json.dumps(
        {k: (list(v) if isinstance(v, tuple) else v) for k, v in facts.items()}, indent=2))

    return {"eval_rows": eval_rows, "bank": bank, "names": names}


def draw_class_distribution(names, counts, words, path: Path) -> None:
    from safebank.intents import FOCUS_INTENTS

    plt = plt_module()
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(7.0, 2.45), gridspec_kw={"width_ratios": [2.3, 1]})
    ordered = sorted(names, key=lambda n: counts[n], reverse=True)
    values = [counts[n] for n in ordered]
    colors = ["#1f5fa8" if n in FOCUS_INTENTS else "#b8c4d6" for n in ordered]
    ax1.bar(range(len(ordered)), values, color=colors, width=0.85)
    mean = sum(values) / len(values)
    ax1.axhline(mean, color="#a11d1d", lw=0.8, ls="--")
    ax1.text(len(values) - 1, mean + 3, f"mean {mean:.0f}", ha="right", va="bottom", fontsize=7, color="#a11d1d")
    ax1.set_xticks([])
    ax1.set_xlabel("77 intents, sorted by training rows", fontsize=7.5)
    ax1.set_ylabel("train rows", fontsize=7.5)
    ax1.tick_params(labelsize=7)
    ax1.text(0, values[0] + 2, ordered[0], fontsize=6.3, ha="left", va="bottom")
    ax1.annotate(ordered[-1], xy=(len(values) - 1, values[-1]), xytext=(len(values) - 1, values[0] * 0.86),
                 fontsize=6.3, ha="right", va="bottom",
                 arrowprops=dict(arrowstyle="-", color="#555555", lw=0.5))
    ax1.bar([0], [0], color="#1f5fa8", label="20 focus intents")
    ax1.bar([0], [0], color="#b8c4d6", label="other intents")
    ax1.legend(fontsize=6.5, frameon=False, loc="upper center")
    for side in ("top", "right"):
        ax1.spines[side].set_visible(False)
    ax2.hist(words, bins=range(0, min(max(words), 60) + 2, 2), color="#1f5fa8", edgecolor="white", lw=0.4)
    med = statistics.median(words)
    ax2.axvline(med, color="#a11d1d", lw=0.8, ls="--")
    ax2.text(med + 1, ax2.get_ylim()[1] * 0.9, f"median {med:.0f}", fontsize=7, color="#a11d1d")
    ax2.set_xlabel("words per query (train)", fontsize=7.5)
    ax2.tick_params(labelsize=7)
    for side in ("top", "right"):
        ax2.spines[side].set_visible(False)
    fig.tight_layout(pad=0.4)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, transparent=True)
    plt.close(fig)


# ==========================================================================
# Stage 2: diagram and equations
# ==========================================================================


def stage_figures() -> None:
    draw_pipeline(ASSETS / "pipeline.svg")
    equations = {
        "eq_factorisation": r"p(x_1,\ldots,x_T)\;=\;\prod_{t=1}^{T}\, p\left(x_t \mid x_{<t}\right)",
        "eq_attention": r"\mathrm{Attention}(Q,K,V)\;=\;\mathrm{softmax}\left(\dfrac{QK^{T}}{\sqrt{d_k}}+M\right)V",
        "eq_lmhead": r"z = W h_t,\qquad p\left(x_{t+1}=i \mid x_{\leq t}\right) = \dfrac{e^{z_i}}{\sum_{j} e^{z_j}}",
    }
    plt = plt_module()
    for name, tex in equations.items():
        fig = plt.figure(figsize=(0.1, 0.1))
        fig.text(0, 0, f"${tex}$", fontsize=11.5)
        fig.savefig(ASSETS / f"{name}.svg", bbox_inches="tight", pad_inches=0.03, transparent=True)
        plt.close(fig)


def draw_pipeline(path: Path) -> None:
    from matplotlib.patches import FancyBboxPatch

    plt = plt_module()
    fig, ax = plt.subplots(figsize=(6.9, 5.5))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 10.4)
    ax.axis("off")

    navy, red, grey = "#12325e", "#a11d1d", "#333333"
    stages = [
        ("Customer message", "free text · minimal, documented preprocessing"),
        ("Prompt template", "prompts.build_prompt · 4 strategies, shared blocks"),
        ("Tokenizer → causal LM → decoding", "Qwen2.5-1.5B-Instruct · DecodeConfig"),
        ("JSON extraction + schema validation", "schema.parse_response · 4 failure kinds"),
        ("Safety screen", "safety.scan_reply · credential requests"),
        ("Confidence gate", "self-reported confidence ≥ 0.55"),
        ("Intent → tool router", "tools.route_intent · destructive check"),
        ("Simulated tool execution", "tools.execute_tool · validated arguments"),
        ("Final response", "reply + lookup result + disclaimer"),
    ]
    x0, w, h, gap, top = 1.05, 4.85, 0.8, 1.11, 10.2
    boxes = []
    for i, (title, detail) in enumerate(stages):
        y = top - i * gap - h
        ax.add_patch(FancyBboxPatch((x0, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.12",
                                    fc="#e8eef7", ec=navy, lw=0.9))
        ax.text(x0 + 0.16, y + h * 0.64, title, fontsize=8.4, weight="bold", color=navy, va="center")
        ax.text(x0 + 0.16, y + h * 0.27, detail, fontsize=6.9, color=grey, va="center")
        boxes.append((y, y + h))
        if i:
            ax.annotate("", xy=(x0 + w / 2, y + h), xytext=(x0 + w / 2, boxes[i - 1][0]),
                        arrowprops=dict(arrowstyle="-|>", color=navy, lw=0.9))

    # Repair-retry loop: validation back to generation.
    y_val = sum(boxes[3]) / 2
    y_gen = sum(boxes[2]) / 2
    ax.annotate("", xy=(x0, y_gen), xytext=(x0, y_val),
                arrowprops=dict(arrowstyle="-|>", color=navy, lw=0.8, connectionstyle="arc3,rad=-0.9"))
    ax.text(x0 - 0.62, (y_val + y_gen) / 2, "repair\n(≤ 2)", fontsize=6.4, color=navy, ha="center", va="center")

    # Escalation sink on the right.
    ex, ew = 7.55, 2.3
    e_top, e_bot = boxes[3][1], boxes[6][0]
    ax.add_patch(FancyBboxPatch((ex, e_bot), ew, e_top - e_bot, boxstyle="round,pad=0.02,rounding_size=0.15",
                                fc="#fde8e8", ec=red, lw=0.9))
    ax.text(ex + ew / 2, (e_top + e_bot) / 2 + 0.35, "Escalate to a\nhuman agent", ha="center", va="center",
            fontsize=8.4, weight="bold", color=red)
    ax.text(ex + ew / 2, (e_top + e_bot) / 2 - 0.55, "reason recorded,\nno tool runs", ha="center", va="center",
            fontsize=6.9, color=grey)
    for i, label in ((3, "still invalid"), (4, "asks for a secret"), (5, "low confidence"), (6, "destructive")):
        ym = sum(boxes[i]) / 2
        ax.annotate("", xy=(ex, ym), xytext=(x0 + w, ym),
                    arrowprops=dict(arrowstyle="-|>", color=red, lw=0.8, linestyle=(0, (3, 2))))
        ax.text((x0 + w + ex) / 2, ym + 0.08, label, ha="center", va="bottom", fontsize=6.4, color=red)

    # Evaluation harness reading the final record.
    yb, yt = boxes[8]
    ax.add_patch(FancyBboxPatch((ex, yb), ew, yt - yb, boxstyle="round,pad=0.02,rounding_size=0.12",
                                fc="white", ec=grey, lw=0.8, ls="--"))
    ax.text(ex + ew / 2, (yb + yt) / 2 + 0.12, "Evaluation", ha="center", va="center", fontsize=8.0,
            weight="bold", color=grey)
    ax.text(ex + ew / 2, (yb + yt) / 2 - 0.2, "evaluate.py · 6 criteria", ha="center", va="center",
            fontsize=6.6, color=grey)
    ax.annotate("", xy=(ex, (yb + yt) / 2), xytext=(x0 + w, (yb + yt) / 2),
                arrowprops=dict(arrowstyle="-|>", color=grey, lw=0.8, linestyle=(0, (3, 2))))
    ax.text((x0 + w + ex) / 2, (yb + yt) / 2 + 0.08, "to_row()", ha="center", va="bottom", fontsize=6.4, color=grey)

    fig.tight_layout(pad=0.1)
    fig.savefig(path, transparent=True)
    plt.close(fig)


# ==========================================================================
# Stage 3: appendix blocks generated from the code
# ==========================================================================


def stage_appendix(data: dict | None) -> None:
    from safebank import config
    from safebank.decoding import DEFAULT_SEEDS, build_decoding_grid
    from safebank.prompts import STRATEGY_RATIONALE, PromptStrategy, build_prompt
    from safebank.schema import response_json_schema
    from safebank.tools import ToolName, execute_tool, tool_specs_json
    from safebank.intents import CONFUSABLE_PAIRS, OBSERVED_CONFUSIONS

    # E1 baseline cell, verbatim from the notebook.
    nb = json.loads((PROJECT / "notebooks" / "safebank_colab.ipynb").read_text(encoding="utf-8"))
    cell = next("".join(c["source"]) for c in nb["cells"]
                if c["cell_type"] == "code" and "E1_PROMPT" in "".join(c["source"]))
    line = next(l for l in cell.splitlines() if l.strip().startswith("E1_PROMPT"))
    e1_prompt = ast.literal_eval(line.split("=", 1)[1].strip())
    write(GENERATED / "appendix_e1.md",
          "Prompt template (`{query}` is replaced by the customer message):\n\n"
          + fence(e1_prompt) + "\n\nThe E1 cell, verbatim from `notebooks/safebank_colab.ipynb`:\n\n"
          + fence(cell, "python"))

    # The four strategies rendered for one real evaluation query.
    rat_rows = [[f"`{s.value}`", md_escape(r, keep_emphasis=True)] for s, r in STRATEGY_RATIONALE.items()]
    parts = [table(["Strategy", "Design rationale (from `prompts.STRATEGY_RATIONALE`)"], rat_rows)]
    if data is not None:
        labels = data["names"]
        query = next(r["query"] for r in data["eval_rows"] if r["gold_intent"] == "card_arrival")
        parts.append(
            "Every prompt below is produced by the same reusable entry point, "
            "`prompts.build_prompt(strategy, query, allowed_intents, **kwargs)`, "
            f"for the evaluation query *\"{md_escape(query)}\"* (gold intent `card_arrival`) "
            "and the dataset's own 77 labels. The few-shot variant receives the "
            "train-split example bank from §3."
        )
        parts.append(
            "The 77-label intent catalogue is byte-identical in all four prompts, by design, so that an "
            "accuracy difference between strategies cannot come from wording drift. It is printed in "
            "full in the zero-shot prompt and replaced by a one-line marker in the other three; "
            "everything else is verbatim."
        )
        from safebank.prompts import format_intent_catalogue

        catalogue = format_intent_catalogue(labels)
        for strategy in PromptStrategy:
            kwargs = {"examples": data["bank"]} if strategy is PromptStrategy.FEW_SHOT else {}
            text = build_prompt(strategy, query, labels, **kwargs)
            shown = text
            if strategy is not PromptStrategy.ZERO_SHOT and catalogue in text:
                shown = text.replace(catalogue, "  <77-label intent catalogue, identical to the zero-shot prompt>")
            parts.append(f"**`{strategy.value}`** — {len(text):,} characters in full\n\n" + fence(shown))
        write(GENERATED / "appendix_prompts.md", "\n\n".join(parts))
    elif not (GENERATED / "appendix_prompts.md").exists():
        write(GENERATED / "appendix_prompts.md", "\n\n".join(parts))

    # Decoding grid.
    grid_rows = []
    for point in build_decoding_grid():
        kw = ", ".join(f"{k}={v}" for k, v in point.config.to_generate_kwargs().items())
        grid_rows.append([f"`{point.label}`", f"`{kw}`", md_escape(point.rationale, keep_emphasis=True)])
    write(GENERATED / "appendix_decoding.md",
          table(["Configuration", "generate() arguments", "Rationale"], grid_rows)
          + f"\n\nSeeds for the self-consistency study: {', '.join(map(str, DEFAULT_SEEDS))}. "
          "Greedy decoding is deterministic, so it contributes a single run.")

    write(GENERATED / "appendix_schema.md", fence(json.dumps(response_json_schema(), indent=2), "json"))

    calls = [
        (ToolName.CHECK_CARD_DELIVERY_STATUS, {"card_id": "CARD_SIM_0001"}),
        (ToolName.FIND_BRANCH, {"pincode": "560001", "service": "atm"}),
        (ToolName.BLOCK_CARD, {"account_id": "ACC_SIM_0001", "reason": "lost"}),
        (ToolName.FIND_BRANCH, {"pincode": "56", "service": "atm"}),
    ]
    trace = []
    for tool, args in calls:
        result = execute_tool(tool, args)
        trace.append({"tool": tool.value, "args": args, "result": result.as_dict()})
    write(GENERATED / "appendix_tools.md",
          fence(tool_specs_json(), "json")
          + "\n\nDirect invocations of the simulated tools with synthetic arguments. "
          "The last call shows argument validation rejecting a malformed pincode. "
          "`block_card` works when called directly, but the pipeline never calls it "
          "automatically; it escalates for customer confirmation instead (§10).\n\n"
          + fence(json.dumps(trace, indent=2), "json"))

    pair_rows = [[f"`{p.first}`", f"`{p.second}`", md_escape(p.reason)] for p in CONFUSABLE_PAIRS]
    obs_rows = [[f"`{p.first}`", f"`{p.second}`", md_escape(p.reason)] for p in OBSERVED_CONFUSIONS]
    write(GENERATED / "appendix_focus.md",
          "Predicted before any results existed (`intents.CONFUSABLE_PAIRS`):\n\n"
          + table(["Intent", "Confused with", "Why"], pair_rows)
          + "\n\nObserved in real model runs (`intents.OBSERVED_CONFUSIONS`), kept separate so the "
          "prediction is not rewritten by hindsight:\n\n"
          + table(["Gold intent", "Predicted", "Note"], obs_rows))

    # Reproducibility facts.
    def pins(name: str) -> list[str]:
        path = PROJECT / name
        if not path.exists():
            return []
        return [l.strip() for l in path.read_text(encoding="utf-8").splitlines()
                if l.strip() and not l.lstrip().startswith(("#", "-r"))]

    commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=PROJECT,
                            capture_output=True, text=True).stdout.strip() or "unknown"
    suite = unittest.TestLoader().discover(str(PROJECT / "tests"), top_level_dir=str(PROJECT))
    repro = [
        ["Code", f"{REPO_URL} (built from commit `{commit}`)"],
        ["Seed", f"`{config.SEED}` for sampling, data selection and decoding"],
        ["Final model", f"`{config.MODEL_ID}`"],
        ["Baseline model", f"`{config.BASELINE_MODEL_ID}`"],
        ["Dataset", f"`{config.DATASET_ID}`, official CSVs (Appendix G)"],
        ["Evaluation sample", f"{config.EVAL_EXAMPLES_PER_INTENT} per intent × {config.EXPECTED_N_INTENTS} = "
                              f"{config.EVAL_EXAMPLES_PER_INTENT * config.EXPECTED_N_INTENTS} rows"],
        ["Generation", f"max {config.MAX_NEW_TOKENS} new tokens; up to {config.REPAIR_MAX_ATTEMPTS} repair attempts; "
                       f"escalation below confidence {config.ESCALATION_CONFIDENCE_THRESHOLD}"],
        ["Application and evaluation layer", ", ".join(f"`{p}`" for p in pins("requirements.txt"))],
        ["Model stack (Colab)", ", ".join(f"`{p}`" for p in pins("requirements-colab.txt"))
                                + "; torch is Colab's preinstalled build"],
        ["Automated tests", f"{suite.countTestCases()} (stdlib `unittest`; 6 need real GPT-2 weights and run only "
                            "with `SAFEBANK_MODEL_TESTS=1`)"],
    ]
    write(GENERATED / "appendix_repro.md", table(["Item", "Value"], repro))


# ==========================================================================
# Stage 4: Markdown -> HTML -> PDF
# ==========================================================================


def assemble_markdown() -> tuple[str, list[tuple[str, str]]]:
    """Concatenate sections with includes resolved. Returns (markdown, markers)."""
    chunks, markers = [], []
    for path in sorted(SECTIONS.glob("*.md")):
        text = path.read_text(encoding="utf-8")

        def include(m: re.Match) -> str:
            target = (REPORT / m.group(1)).resolve()
            if not target.exists():
                return f"[[MISSING include: {m.group(1)}]]"
            return target.read_text(encoding="utf-8")

        for _ in range(3):  # allow nested includes
            text = INCLUDE.sub(include, text)
        for m in MARKER.finditer(text):
            markers.append((path.name, " ".join(m.group(1).split())))
        chunks.append(text)
    return "\n\n".join(chunks), markers


def render_html(markdown: str) -> str:
    from markdown_it import MarkdownIt

    marked = MARKER.sub(lambda m: f'<span class="pending">[[{m.group(1)}]]</span>', markdown)
    body = MarkdownIt("commonmark").enable("table").render(marked)
    return (
        "<!doctype html>\n<html lang=\"en\"><head><meta charset=\"utf-8\">"
        "<title>SafeBank Assist — PCAM ZG516 Group 22</title>"
        "<link rel=\"stylesheet\" href=\"../report.css\"></head>\n<body>\n"
        f"{body}\n</body></html>\n"
    )


def find_edge() -> str:
    for p in (r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
              r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"):
        if Path(p).exists():
            return p
    found = shutil.which("msedge")
    if found:
        return found
    raise SystemExit("Microsoft Edge not found. Open report/build/report.html in a browser and print it to PDF.")


def print_pdf(html_path: Path, pdf_path: Path) -> None:
    profile = BUILD / "edge-profile"
    cmd = [
        find_edge(), "--headless=new", "--disable-gpu", "--no-first-run", "--no-default-browser-check",
        "--disable-extensions", "--no-pdf-header-footer", "--print-to-pdf-no-header",
        "--run-all-compositor-stages-before-draw", "--virtual-time-budget=8000",
        f"--user-data-dir={profile}", f"--print-to-pdf={pdf_path}", html_path.as_uri(),
    ]
    if pdf_path.exists():
        pdf_path.unlink()
    subprocess.run(cmd, capture_output=True, text=True, timeout=240)
    shutil.rmtree(profile, ignore_errors=True)
    if not pdf_path.exists():
        raise SystemExit("Edge did not produce a PDF. Open report/build/report.html and print it to PDF.")


def finish_pdf(raw: Path, out: Path, n_pending: int, draft: bool) -> dict:
    import pymupdf

    doc = pymupdf.open(raw)
    n = doc.page_count
    starts = {}
    for i, page in enumerate(doc):
        blocks = sorted(page.get_text("blocks"), key=lambda b: (b[1], b[0]))
        first = blocks[0][4].strip() if blocks else ""
        for heading in ("References", "Appendix"):
            if first.startswith(heading) and heading not in starts:
                starts[heading] = i
    for i, page in enumerate(doc):
        if i == 0:
            continue
        w, h = page.rect.width, page.rect.height
        page.insert_text((48, h - 26), "SafeBank Assist  |  PCAM ZG516 Group 22", fontsize=7.5, color=(0.35, 0.35, 0.35))
        label = f"Page {i} of {n - 1}"
        page.insert_text((w - 48 - pymupdf.get_text_length(label, fontsize=7.5), h - 26), label,
                         fontsize=7.5, color=(0.35, 0.35, 0.35))
        if draft:
            note = f"DRAFT - {n_pending} item(s) pending"
            page.insert_text((w / 2 - pymupdf.get_text_length(note, fontsize=8) / 2, 22), note,
                             fontsize=8, color=(0.7, 0.0, 0.0))
    doc.save(out, garbage=3, deflate=True)
    doc.close()
    body_end = starts.get("References", n)
    return {"pages": n, "body_pages": body_end - 1, "references_page": starts.get("References"),
            "appendix_page": starts.get("Appendix")}


def render_preview(pdf: Path) -> None:
    import pymupdf

    out = BUILD / "preview"
    shutil.rmtree(out, ignore_errors=True)
    out.mkdir(parents=True)
    doc = pymupdf.open(pdf)
    for i, page in enumerate(doc):
        page.get_pixmap(dpi=70).save(out / f"page-{i:02d}.png")
    doc.close()


# ==========================================================================
# Checks
# ==========================================================================


def run_checks(markdown: str) -> dict:
    lowered = markdown.lower()
    forbidden = [f for f in forbidden_phrases() if f in lowered]
    headings = [l[2:].strip() for l in markdown.splitlines() if l.startswith("# ")]
    missing = [h for h in REQUIRED_HEADINGS if h not in headings]
    body, _, refs = markdown.partition("\n# References")
    refs = refs.split("\n# Appendix")[0]
    listed = set(re.findall(r"^\[(\d+)\]", refs, re.M))
    cited = set()
    for group in re.findall(r"\[(\d+(?:\s*[,–-]\s*\d+)*)\]", body):
        for part in re.split(r"\s*,\s*", group):
            if re.fullmatch(r"\d+\s*[–-]\s*\d+", part):
                a, b = map(int, re.split(r"\s*[–-]\s*", part))
                cited.update(str(x) for x in range(a, b + 1))
            elif part.strip().isdigit():
                cited.add(part.strip())
    return {"forbidden": forbidden, "missing_headings": missing,
            "uncited": sorted(listed - cited, key=int), "unknown_citations": sorted(cited - listed, key=int)}


# ==========================================================================
# Main
# ==========================================================================


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--final", action="store_true", help="fail while anything is pending")
    ap.add_argument("--offline", action="store_true", help="reuse report/generated/ dataset blocks")
    ap.add_argument("--assets-only", action="store_true", help="regenerate figures and generated/ blocks only")
    ap.add_argument("--preview", action="store_true", help="render page images to report/build/preview/")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    data = None
    if not args.offline:
        print("[1/4] dataset facts, examples and figures")
        data = stage_dataset()
    else:
        print("[1/4] dataset: reusing report/generated/ (offline)")
    print("[2/4] diagram and equations")
    stage_figures()
    print("[3/4] appendix blocks from the code")
    stage_appendix(data)
    if args.assets_only:
        print("assets written to report/assets/ and report/generated/")
        return 0

    print("[4/4] Markdown -> HTML -> PDF")
    markdown, markers = assemble_markdown()
    BUILD.mkdir(exist_ok=True)
    html_path = BUILD / "report.html"
    html_path.write_text(render_html(markdown), encoding="utf-8")
    raw = BUILD / "_raw.pdf"
    print_pdf(html_path, raw)
    pages = finish_pdf(raw, BUILD / PDF_NAME, len(markers), draft=not args.final)
    raw.unlink(missing_ok=True)
    if args.preview:
        render_preview(BUILD / PDF_NAME)
    checks = run_checks(markdown)

    print(f"\nPDF: report/build/{PDF_NAME}")
    print(f"pages: {pages['pages']} total = 1 title + {pages['body_pages']} body (sections 1-14) "
          f"+ {pages['pages'] - 1 - pages['body_pages']} references/appendix")
    print(f"body page budget 10-15: {'OK' if 10 <= pages['body_pages'] <= 15 else 'OUTSIDE'}")
    print(f"pending items: {len(markers)}")
    for name, text in markers:
        print(f"  - {name}: {text[:110]}{'...' if len(text) > 110 else ''}")
    print(f"missing headings: {checks['missing_headings'] or 'none'}")
    print(f"forbidden phrases: {checks['forbidden'] or 'none'}")
    print(f"references never cited: {checks['uncited'] or 'none'}")
    print(f"citations with no reference: {checks['unknown_citations'] or 'none'}")

    problems = []
    if checks["missing_headings"]:
        problems.append("missing headings")
    if checks["forbidden"]:
        problems.append("forbidden phrases")
    if checks["unknown_citations"]:
        problems.append("citations with no reference")
    if args.final:
        if markers:
            problems.append("pending items")
        if not 10 <= pages["body_pages"] <= 15:
            problems.append("body outside 10-15 pages")
    if problems:
        print("\nNOT READY: " + ", ".join(problems))
        return 1
    print("\nREADY" if args.final else "\ndraft built")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
