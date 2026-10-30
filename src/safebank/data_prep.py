"""
BANKING77 loading, the frozen evaluation sample and the few-shot example bank.

Everything that touches the dataset lives here, so every number in the report
traces back to one seeded, documented procedure.

Loading note
------------
``PolyAI/banking77`` on the Hugging Face Hub is still a *loading-script*
dataset (``banking77.py``), and ``datasets`` 4.x and later refuse to run
dataset scripts. ``load_banking77`` therefore reads the two official CSV files
that script itself downloads (PolyAI-LDN/task-specific-datasets), and takes the
canonical 77-name ``ClassLabel`` order from the ``dataset_info`` front matter
of the Hub's ``README.md`` (the Hub repo dropped ``dataset_infos.json`` when it
was converted to Parquet). The rows and the label ids are identical to ``load_dataset(DATASET_ID)``; only
the loader differs. This is recorded in :func:`preprocessing_record`.

Dependency rule
---------------
``datasets`` is imported inside :func:`load_banking77` only. Every other
function is duck-typed against the split (``split["text"]``,
``split["label"]``, ``split.features["label"].names``), so the sampling logic
is unit-tested offline with a tiny stand-in split.

Owner: Vishruth (data)
"""

from __future__ import annotations

import csv
import json
import random
import re
import urllib.request
from collections import Counter
from pathlib import Path

from . import config, tools
from .intents import validate_label_space
from .schema import ToolName

#: Official raw files, exactly as referenced by the Hub's ``banking77.py``.
TRAIN_CSV_URL: str = (
    "https://raw.githubusercontent.com/PolyAI-LDN/task-specific-datasets/"
    "master/banking_data/train.csv"
)
TEST_CSV_URL: str = (
    "https://raw.githubusercontent.com/PolyAI-LDN/task-specific-datasets/"
    "master/banking_data/test.csv"
)
#: Source of the canonical label-id order: the dataset card's YAML front
#: matter (``dataset_info.features[label].dtype.class_label.names``).
DATASET_CARD_URL: str = (
    f"https://huggingface.co/datasets/{config.DATASET_ID}/resolve/main/README.md"
)

#: Published split sizes, checked after loading so a truncated download fails
#: loudly instead of producing a smaller, silently different eval sample.
EXPECTED_SPLIT_SIZES: dict[str, int] = {"train": 10003, "test": 3080}

#: Exactly what is done to the text before it is used. Kept as data so the
#: report quotes the code, not a paraphrase of it.
PREPROCESSING_STEPS: tuple[str, ...] = (
    "Strip leading/trailing whitespace from each query (CSV reader output).",
    "No lowercasing, spelling correction or deduplication: queries are kept "
    "as the customer wrote them, because noisy phrasing is part of the task.",
    "Evaluation sample drawn from the TEST split only; few-shot examples drawn "
    "from the TRAIN split only, excluding any text that also appears in the "
    "evaluation sample.",
    "Prompt-time normalisation (whitespace collapse, length cap) is applied "
    "later by prompts._clean_query, identically for every prompt variant.",
)


# --------------------------------------------------------------------------
# Loading
# --------------------------------------------------------------------------


def _download(url: str, dest: Path) -> Path:
    """Fetch ``url`` to ``dest`` once; later calls reuse the cached file."""
    if not dest.exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = dest.with_suffix(dest.suffix + ".part")
        with urllib.request.urlopen(url, timeout=60) as resp:
            tmp.write_bytes(resp.read())
        tmp.replace(dest)
    return dest


#: One ``'<id>': <name>`` entry of the card's ``class_label.names`` mapping.
_CLASS_LABEL_LINE = re.compile(r"^\s*'(\d+)':\s*(.+?)\s*$")


def _read_label_names(card_path: Path) -> list[str]:
    """Label names in id order, from the dataset card's YAML front matter."""
    text = card_path.read_text(encoding="utf-8")
    front_matter = text.split("---", 2)[1] if text.startswith("---") else ""
    by_id: dict[int, str] = {}
    for line in front_matter.splitlines():
        m = _CLASS_LABEL_LINE.match(line)
        if m:
            by_id[int(m.group(1))] = m.group(2)
    if sorted(by_id) != list(range(len(by_id))):
        raise ValueError(f"{card_path} has non-contiguous class_label ids")
    return [by_id[i] for i in range(len(by_id))]


def _read_csv(path: Path) -> tuple[list[str], list[str]]:
    """Read one BANKING77 CSV with the same dialect ``banking77.py`` uses."""
    texts: list[str] = []
    categories: list[str] = []
    with path.open(encoding="utf-8", newline="") as f:
        reader = csv.reader(
            f, quotechar='"', delimiter=",", quoting=csv.QUOTE_ALL, skipinitialspace=True
        )
        next(reader)  # header: text,category
        for text, category in reader:
            texts.append(text.strip())
            categories.append(category.strip())
    return texts, categories


def load_banking77(cache_dir: str | None = None) -> tuple[object, object]:
    """
    Return ``(train_split, test_split)`` as ``datasets.Dataset`` objects.

    Each split has a ``text`` column and a ``label`` ``ClassLabel`` column
    whose names are the 77 canonical intents, in the Hub's id order. Raw files
    are cached under ``cache_dir`` (default ``config.DATA_DIR``, git-ignored).

    The mandatory label-space check runs here, so no caller can obtain a split
    whose intent names disagree with ``intents.py``.
    """
    from datasets import ClassLabel, Dataset, Features, Value

    root = Path(cache_dir) if cache_dir else config.DATA_DIR
    names = _read_label_names(_download(DATASET_CARD_URL, root / "README.md"))
    features = Features({"text": Value("string"), "label": ClassLabel(names=names)})
    label_id = {name: i for i, name in enumerate(names)}

    splits = []
    for split_name, url in (("train", TRAIN_CSV_URL), ("test", TEST_CSV_URL)):
        texts, categories = _read_csv(_download(url, root / f"{split_name}.csv"))
        unknown = sorted(set(categories) - set(label_id))
        if unknown:
            raise ValueError(f"{split_name}.csv has labels not in the dataset card: {unknown}")
        if len(texts) != EXPECTED_SPLIT_SIZES[split_name]:
            raise ValueError(
                f"{split_name} split has {len(texts)} rows, expected "
                f"{EXPECTED_SPLIT_SIZES[split_name]}; delete {root} and re-download"
            )
        splits.append(
            Dataset.from_dict(
                {"text": texts, "label": [label_id[c] for c in categories]},
                features=features,
            )
        )

    train, test = splits
    validate_label_space(dataset_label_space(train))  # raises LabelSpaceError
    return train, test


def dataset_label_space(split) -> list[str]:
    """
    Authoritative intent names, read from the dataset itself.

    Never hardcoded. Index ``i`` of the returned list is label id ``i``.
    """
    names = list(split.features["label"].names)
    if len(names) != config.EXPECTED_N_INTENTS:
        raise ValueError(
            f"expected {config.EXPECTED_N_INTENTS} intents, dataset has {len(names)}"
        )
    return names


def class_distribution(split, labels: list[str]) -> dict[str, int]:
    """Rows per intent, in label-id order. Feeds the report's distribution plot."""
    counts = Counter(split["label"])
    return {name: counts.get(i, 0) for i, name in enumerate(labels)}


# --------------------------------------------------------------------------
# Evaluation sample
# --------------------------------------------------------------------------


def build_eval_sample(split, labels: list[str], seed: int = config.SEED) -> list[dict]:
    """
    Stratified sample of ``config.EVAL_EXAMPLES_PER_INTENT`` rows per intent.

    5 x 77 = 385 rows from the split passed in (the TEST split for every
    reported number). Deterministic under ``seed``: the same seed always
    yields the same rows in the same order (grouped by label id, then by
    original row index), so runs can be compared row by row.

    Each row: ``{"query": str, "gold_intent": str}``.
    """
    k = config.EVAL_EXAMPLES_PER_INTENT
    texts = split["text"]
    by_label: dict[int, list[int]] = {}
    for idx, label in enumerate(split["label"]):
        by_label.setdefault(label, []).append(idx)

    rng = random.Random(seed)
    rows: list[dict] = []
    for label_id, name in enumerate(labels):
        pool = by_label.get(label_id, [])
        if len(pool) < k:
            raise ValueError(f"intent {name!r} has {len(pool)} rows, need {k}")
        for idx in sorted(rng.sample(pool, k)):
            rows.append({"query": texts[idx], "gold_intent": name})
    return rows


# --------------------------------------------------------------------------
# Few-shot example bank
# --------------------------------------------------------------------------

#: Generic, fact-free replies per routing outcome. They never state an account
#: fact, so the examples do not teach the model to invent one (criterion 4).
_REPLY_BY_TOOL: dict[ToolName | None, str] = {
    ToolName.CHECK_CARD_DELIVERY_STATUS: (
        "Thanks for getting in touch. Let me check the delivery status of your card."
    ),
    ToolName.FIND_BRANCH: (
        "I can help with that. Let me find the nearest branch or ATM for you."
    ),
    ToolName.BLOCK_CARD: (
        "Thanks for telling us. Blocking a card changes your account, so a "
        "colleague will confirm this with you before anything is done."
    ),
    None: (
        "Thanks for your message. I can help with that and will explain the "
        "next steps for your request."
    ),
}

#: Synthetic placeholder args, matching pipeline._fill_missing_args.
_ARGS_BY_TOOL: dict[ToolName, dict] = {
    ToolName.CHECK_CARD_DELIVERY_STATUS: {"card_id": "CARD_SIM_0001"},
    ToolName.FIND_BRANCH: {"pincode": "560001", "service": "atm"},
}

#: Round-robin order of routing outcomes, so even n=4 covers every behaviour:
#: tool call, a second tool, destructive escalation, and text-only.
_ROUTE_ORDER: tuple[ToolName | None, ...] = (
    ToolName.CHECK_CARD_DELIVERY_STATUS,
    ToolName.FIND_BRANCH,
    ToolName.BLOCK_CARD,
    None,
)


def expected_json(intent: str, confidence: float = 0.9) -> str:
    """
    The reference ``AssistantResponse`` JSON for a labelled training query.

    Follows the application's own rules: the tool comes from
    ``tools.route_intent``, and a destructive tool is never requested, the
    example escalates instead, exactly as the pipeline does.
    """
    tool = tools.route_intent(intent)
    destructive = tool is not None and tools.TOOL_REGISTRY[tool].destructive
    tool_call = (
        {"name": tool.value, "args": _ARGS_BY_TOOL[tool]}
        if tool is not None and not destructive
        else None
    )
    payload = {
        "intent": intent,
        "confidence": confidence,
        "response": _REPLY_BY_TOOL[tool],
        "tool_call": tool_call,
        "requires_human": destructive,
    }
    return json.dumps(payload)


def build_example_bank(
    train_split,
    labels: list[str],
    n: int = 4,
    seed: int = config.SEED,
    *,
    exclude: set[str] | frozenset[str] = frozenset(),
) -> list[tuple[str, str]]:
    """
    ``(customer_message, expected_json_string)`` pairs for few-shot prompting.

    MUST be given the TRAIN split. Pass the eval queries as ``exclude`` so a
    text duplicated across splits can never appear as a worked example.

    Intents are picked round-robin over routing outcomes (delivery tool,
    branch tool, destructive escalation, text-only), one distinct intent each,
    then one query per intent, all under ``seed``. Feeds
    ``prompts.build_few_shot_prompt(examples=...)``.
    """
    if n <= 0:
        raise ValueError(f"n must be positive, got {n}")

    groups: dict[ToolName | None, list[int]] = {route: [] for route in _ROUTE_ORDER}
    for label_id, name in enumerate(labels):
        groups[tools.route_intent(name)].append(label_id)

    rng = random.Random(seed)
    for ids in groups.values():
        rng.shuffle(ids)

    chosen_ids: list[int] = []
    step = 0
    while len(chosen_ids) < n and any(groups.values()):
        ids = groups[_ROUTE_ORDER[step % len(_ROUTE_ORDER)]]
        if ids:
            chosen_ids.append(ids.pop())
        step += 1

    texts = train_split["text"]
    by_label: dict[int, list[int]] = {}
    for idx, label in enumerate(train_split["label"]):
        if texts[idx] not in exclude:
            by_label.setdefault(label, []).append(idx)

    bank: list[tuple[str, str]] = []
    for label_id in chosen_ids:
        pool = by_label.get(label_id)
        if not pool:
            raise ValueError(f"no usable train rows for intent {labels[label_id]!r}")
        idx = rng.choice(pool)
        bank.append((texts[idx], expected_json(labels[label_id])))
    return bank


# --------------------------------------------------------------------------
# Deliverable 3: dataset description + preprocessing record
# --------------------------------------------------------------------------


def preprocessing_record(
    train_split=None, test_split=None, eval_rows: list[dict] | None = None
) -> dict:
    """
    Written record for the report (Deliverable 3).

    Always includes the fixed procedure. Pass the loaded splits and the eval
    sample to add the measured facts: split sizes, intent count, per-intent
    min/max, cross-split duplicate texts, and the eval sample's size.
    """
    record: dict = {
        "dataset_id": config.DATASET_ID,
        "loader": "official PolyAI CSVs + Hub dataset card (README.md) label order",
        "source_urls": [TRAIN_CSV_URL, TEST_CSV_URL, DATASET_CARD_URL],
        "n_intents_expected": config.EXPECTED_N_INTENTS,
        "seed": config.SEED,
        "eval_rows_per_intent": config.EVAL_EXAMPLES_PER_INTENT,
        "eval_rows_total": config.EVAL_EXAMPLES_PER_INTENT * config.EXPECTED_N_INTENTS,
        "eval_source_split": "test",
        "few_shot_source_split": "train",
        "preprocessing": list(PREPROCESSING_STEPS),
    }
    if train_split is not None and test_split is not None:
        labels = dataset_label_space(train_split)
        train_counts = class_distribution(train_split, labels)
        test_counts = class_distribution(test_split, labels)
        record.update(
            n_intents=len(labels),
            split_sizes={"train": len(train_split["text"]), "test": len(test_split["text"])},
            train_rows_per_intent={
                "min": min(train_counts.values()),
                "max": max(train_counts.values()),
            },
            test_rows_per_intent={
                "min": min(test_counts.values()),
                "max": max(test_counts.values()),
            },
            texts_in_both_splits=len(set(train_split["text"]) & set(test_split["text"])),
        )
    if eval_rows is not None:
        record["eval_rows_actual"] = len(eval_rows)
        record["eval_intents_covered"] = len({r["gold_intent"] for r in eval_rows})
    return record
