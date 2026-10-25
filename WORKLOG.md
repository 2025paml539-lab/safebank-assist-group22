# Work Log — SafeBank Assist

**PCAM ZG516 Applied Generative AI · Group Major Project / Assignment-1 · Group 22**
**Deadline: 31 October 2026** (extended from 25 Oct) · Log updated: **25 October 2026**

This is the single source of truth for project status. If this file and `PROJECT_PLAN.md` disagree, **this file wins** — the plan was written before the code existed.

> **Picking this up in your own AI IDE?** Read sections 1, 5, 6 and 7. Section 5 contains complete specifications for every unwritten file: exact paths, signatures, contracts, gotchas and verification commands. You should not need to ask anyone a question to start.

---

## 1. Where we are

| | |
|---|---|
| **Overall completion** | **~50–55%** |
| Estimated marks secured | ~10.7 / 20 |
| Application + experiment code | **~95% done** |
| **Experiment results** | **0% — nothing has run on a real model yet** |
| Report | ~5% (raw material written, nothing assembled) |
| Demo | 0% |
| **Tests passing on `main`** | **276** |

**One-line summary:** all the code except the data and model-loading layer is written, reviewed and merged. Nothing that produces a *number* has run yet, because the model environment was never set up. That is the critical path and it is the only thing standing between us and a finishable report.

### Completion by workstream

| Member | Area | Status |
|---|---|---|
| **Kishore** | Architecture + application code | ✅ **100% — merged** |
| **Satya** | Prompts, decoding, evaluation code | ✅ **100% code — merged (PR #1).** Experiment *runs* still pending the environment |
| **Vishruth** | Data, model loading, environment, E1 | 🔴 **0% — not started. BLOCKS EVERYTHING.** |
| **Bhavani** | Report assembly, submission | 🔴 **~5% — not started** |

### Rubric estimate (20 marks)

| # | Component | Marks | Est. | Why not full |
|---|---|---|---|---|
| 1 | Problem + dataset analysis | 2 | 0.8 | Problem done; no dataset analysis, no class distribution, no preprocessing log |
| 2 | LLM / generative-model understanding | 3 | 0.9 | Architecture prose drafted; model-family comparison unwritten; needs real tokenizer output |
| 3 | Prompt engineering | 3 | 1.8 | All 4 variants merged, tested, each with written rationale; **no accuracy comparison table** |
| 4 | Adaptation strategy | 2 | 1.2 | Written in `ARCHITECTURE.md` §7; must be argued from measured numbers we don't have |
| 5 | Structured output + tool calling | 3 | 2.5 | Complete, tested, all six metrics wired; validity rate needs a real run |
| 6 | Implementation | 3 | 2.3 | Modular, 276 tests, seeds frozen, reviewed; **no Colab notebook, no `requirements.txt`** |
| 7 | Evaluation + failure analysis | 2 | 0.9 | All 6 metrics merged and verified; **zero results, zero analysed failure cases** |
| 8 | Report + demo + contribution | 2 | 0.3 | Nothing assembled, no rehearsal, no signatures |
| | | **20** | **~10.7** | |

**The pattern is clear:** every component is capped by the same missing thing — measured results. Components 3, 5, 6 and 7 are all code-complete and lose marks only for the absent numbers.

---

## 2. Day-by-day plan to 31 Oct

Only **one** buffer day. This is thin.

| Day | Must land | Owner | State |
|---|---|---|---|
| **Sun 25** | PR #1 reviewed and merged · `to_row()` extended for criterion 4 · `PROJECT_PLAN.md` corrected · work log published | Kishore | ✅ **done** |
| **Sun 25** | Colab decision locked · `data_prep.py` + `model_loader.py` started | Vishruth | 🔴 **outstanding** |
| **Sun 25** | Report §1/§5 drafted from `ARCHITECTURE.md` | Bhavani | 🔴 **outstanding** |
| **Mon 26** | `data_prep.py` working · **`validate_label_space()` passes** · `model_loader` running on Colab · E1 baseline captured | Vishruth | pending |
| **Tue 27** | E2 full run (4 variants × 385 rows) · real E7 integrated run | Satya, Kishore | pending |
| **Wed 28** | E3 decoding grid (reduced scope) · E6 evaluation + failure analysis | Satya | pending |
| **Thu 29** | All report sections drafted · figures generated | all | pending |
| **Fri 30** | Report assembled + formatted + proofread · demo rehearsal | Bhavani + all | pending |
| **Sat 31** | Contribution statement signed · **submit** | Bhavani | pending |

### 🔴 Escalation trigger — agreed safeguard

**If `data_prep.py` and `model_loader.py` are not running by Monday 26 Oct evening, Kishore takes them over.** They are ~150 lines each, both contracts are fully specified in section 5 below, and Tue–Wed collapse without them. The contribution statement will record who actually did what.

---

## 3. DONE — merged to `main`

**276 tests pass with only pydantic installed** — no torch, no GPU, no network. The whole application and evaluation stack is verifiable offline.

### Kishore — architecture and application

| File | Lines | What it does | Experiment |
|---|---|---|---|
| `src/safebank/config.py` | 85 | Seeds, model ids, dataset id, thresholds, artifact paths | — |
| `src/safebank/intents.py` | 203 | `INTENT_THEMES` (5×4), `FOCUS_INTENTS` (20), `CONFUSABLE_PAIRS` (6), `validate_label_space()` | E6 input |
| `src/safebank/schema.py` | 264 | `AssistantResponse`, `ToolCall`, `extract_json_block()`, `FailureKind` (4 kinds), `parse_response()`, `build_repair_prompt()` | **E4** |
| `src/safebank/tools.py` | 302 | 3 simulated tools + I/O schemas, deterministic handlers, `TOOL_REGISTRY`, `INTENT_TO_TOOL` (10 intents), `tool_specs_json()` | **E5** |
| `src/safebank/generator.py` | 131 | `TextGenerator` Protocol, `DecodeConfig`, `DecodeStrategy`, `FakeGenerator` | E1/E3 seam |
| `src/safebank/pipeline.py` | 308 | `SafeBankPipeline`, repair-retry, confidence gate, intent-authoritative routing, destructive-tool refusal, `to_row()` | **E7** |
| `src/safebank/__init__.py` | 143 | Public API, 44 exports | — |

### Satya — prompts, decoding, evaluation (PR #1, merged)

| File | Lines | What it does | Experiment |
|---|---|---|---|
| `src/safebank/prompts.py` | 786 | All 4 strategies — `ZERO_SHOT`, `FEW_SHOT`, `ROLE_CONTEXT`, `CONSTRAINT_BASED` — plus shared formatters and `STRATEGY_RATIONALE` | **E2** |
| `src/safebank/decoding.py` | 288 | 6-config E3 grid on the existing `DecodeConfig`, `seed_variations()`, `self_consistency_configs()` | **E3** |
| `src/safebank/evaluate.py` | 737 | All 6 evaluation criteria, `EvalRecord`, `analyse_failures()`, `evaluate_run()`, `results_dataframe()` | **E6** |

### Test suite — 276 tests

| Module | Tests | Covers |
|---|---|---|
| `tests/test_prompts.py` | 59 | All 4 variants, shared blocks, dispatch, preprocessing |
| `tests/test_pipeline.py` | 39 | E7: repair-retry, confidence gate, destructive refusal, hallucination guards, `to_row()` |
| `tests/test_evaluate.py` | 39 | All 6 metrics, failure analysis, routing regression tests |
| `tests/test_tools.py` | 38 | 3 tools, arg validation, determinism, routing, spec export |
| `tests/test_schema.py` | 35 | E4: extraction edge cases, all 4 `FailureKind` paths, repair prompt |
| `tests/test_decoding.py` | 23 | E3 grid shape, labels, seed variation |
| `tests/test_generator.py` | 22 | Per-strategy decode kwargs, protocol conformance |
| `tests/test_intents.py` | 21 | Label-space structure, confusable pairs, validation guard |

### Verification evidence captured

- Full suite: `Ran 276 tests ... OK` (~3s warm)
- `compileall` clean on all modules
- Real E7 trace: prompt built → JSON validated → `card_arrival` → `check_card_delivery_status` → `{'status': 'in_transit', 'dispatched_on': '2026-10-12', 'eta_days': 5}` → disclaimer attached
- **Mutation check:** flipping `block_card.destructive` to `False` in memory fails 4 tests — the safety control is genuinely guarded, not merely asserted
- **Routing-metric check:** an all-correct run scores `routing_accuracy 1.0` with `n_correctly_withheld 3`; four anti-regression cases confirm the destructive exemption cannot hide a genuine dropped call

---

## 4. Review history — PR #1 (merged)

**PR:** https://github.com/2025paml539-lab/safebank-assist-group22/pull/1 · branch `2025paml561/e2-e3-e6` · merged 25 Oct

Kept as a record because the bug it caught is worth writing up in the report's limitations section.

**First revision** scored the pipeline's destructive-tool refusal as a routing miss. `evaluate.tool_routing()` compared `route_intent(gold)` against the tool actually invoked, but the pipeline deliberately refuses to auto-execute `block_card` and escalates instead, so `row['tool']` was `None` and the metric recorded `missed`. Measured impact: a run with **100% intent accuracy reported 25% routing accuracy**, and on the 385-row set 15 of 50 tool-expected rows were permanently wrong, capping routing accuracy at **70%**. A working Requirement 13 control was being reported as a defect.

**Fixed** with an `n_correctly_withheld` category keyed off `TOOL_REGISTRY[tool].destructive`, so a future destructive tool is picked up automatically, and surfaced as its own column rather than folded into "correct" — the E6 table now actively evidences the control. Five regression tests confirm a withheld call is not a miss, an all-correct run scores 1.0, and both destructive-without-escalation and non-destructive-withheld still count as genuine misses.

**Also resolved:** `to_row()` now carries `response`, the model's own reply, so evaluation criterion 4 can be computed from an `EvalRecord` like every other metric.

**Outstanding follow-up (Satya, small, non-blocking):** switch `flag_unsafe_responses` to read `record.row["response"]` and drop the manual caller-side pairing.

---

## 5. PENDING — full specifications

### 🔴 5.1 Vishruth — `src/safebank/data_prep.py` (NOT STARTED, blocks everything)

Load BANKING77, freeze a reproducible stratified evaluation sample, and supply a train-split example bank for few-shot.

```python
# Required public functions. Keep datasets/pandas imports INSIDE the bodies.

def load_banking77(cache_dir: str | None = None) -> tuple[object, object]:
    """Return (train_split, test_split) from config.DATASET_ID."""

def dataset_label_space(split) -> list[str]:
    """
    Authoritative intent names, read from the dataset itself:
        split.features["label"].names
    NEVER hardcode these. Must return exactly 77 names.
    """

def build_eval_sample(split, labels, seed: int = config.SEED) -> list[dict]:
    """
    Stratified sample: config.EVAL_EXAMPLES_PER_INTENT (=5) rows per intent.
    5 x 77 = 385 rows. Deterministic under `seed`.
    Each row: {"query": str, "gold_intent": str}
    """

def build_example_bank(train_split, labels, n: int = 4, seed: int = config.SEED) -> list[tuple[str, str]]:
    """
    (customer_message, expected_json_string) pairs for few-shot prompting.
    MUST come from the TRAIN split only. Feeds prompts.build_few_shot_prompt(examples=...).
    """

def preprocessing_record() -> dict:
    """
    Written record for the report: dataset id, split sizes, n_intents, seed,
    rows per intent, total eval rows, and what preprocessing was applied.
    Deliverable 3 ("dataset description + preprocessing record").
    """
```

**Mandatory — do not skip:**

```python
from .intents import validate_label_space
validate_label_space(dataset_label_space(train_split))   # raises LabelSpaceError on mismatch
```

The 20 `FOCUS_INTENTS` names in `intents.py` have **never been checked against the real dataset**, because `datasets` is not part of the local environment. This call is the check. If it raises, a name is misspelled: fix `intents.py` and tell Kishore. **Nothing may be reported until this passes.**

**Also blocking Satya:** `build_example_bank()` is what makes E2's few-shot numbers defensible. `prompts.build_few_shot_prompt` has an offline fallback bank so the code is testable, but reported E2 results need real train-split examples.

**Facts you need:** `config.DATASET_ID = "PolyAI/banking77"` · `config.EXPECTED_N_INTENTS = 77` · `config.EVAL_EXAMPLES_PER_INTENT = 5` · `config.SEED = 42`

---

### 🔴 5.2 Vishruth — `src/safebank/model_loader.py` (NOT STARTED, blocks everything)

```python
def device_report() -> DeviceReport:
    """
    Hardware + version facts for the reproducibility appendix:
    device, device_name, torch.cuda.get_device_capability(), VRAM,
    torch/transformers versions, dtype.
    """

def load_model_and_tokenizer(
    model_id: str = config.MODEL_ID,
    *, device: str | None = None, dtype: str = "float16", cache_dir: str | None = None,
) -> tuple[object, object]:
    """Load a pretrained causal LM + tokenizer. Returns (model, tokenizer)."""

class HFGenerator:
    """Real TextGenerator. Must satisfy generator.TextGenerator structurally."""
    def __init__(self, model, tokenizer, *, device: str | None = None): ...
    def generate(self, prompt: str, decode: DecodeConfig) -> str: ...
```

**Six gotchas that will cost you hours if missed:**

1. **Return the completion ONLY**, with the prompt stripped. The pipeline feeds your return value straight into `schema.parse_response`. A prompt echo is scored as a model failure and silently ruins every metric.
2. **Set `tokenizer.pad_token = tokenizer.eos_token` when it is `None`.** GPT-2 has no pad token and batched generation fails without it.
3. **Call `model.eval()`.** Training mode leaves dropout on, which makes greedy decoding non-deterministic and corrupts the E3 stability measurement.
4. **Pass `**decode.to_generate_kwargs()`.** Do not hand-build sampling arguments — that method already emits only the knobs relevant to each strategy, so a greedy run cannot leak a temperature.
5. **Seed with `transformers.set_seed(decode.seed)` immediately before every sampled generation**, or the E3 self-consistency study is not reproducible.
6. **Use `tokenizer.apply_chat_template` for Qwen2.5-Instruct.** It is markedly worse at instruction-following without it. GPT-2 has no chat template, so branch on `tokenizer.chat_template is None`. That asymmetry is part of why GPT-2 is the weak E1 baseline.

Also: cache the loaded pair at module level (reloading 3 GB per experiment makes the notebook unusable on a T4), and record prompt/completion token counts for evaluation criterion 5.

**Models:** `config.MODEL_ID = "Qwen/Qwen2.5-1.5B-Instruct"` · `config.BASELINE_MODEL_ID = "gpt2"` · `config.MAX_NEW_TOKENS = 192`

**Self-check once written:**

```python
from safebank.generator import TextGenerator
assert isinstance(HFGenerator(model, tok), TextGenerator)   # runtime_checkable Protocol
```

---

### 🔴 5.3 Vishruth — `requirements.txt` + Colab notebook + E1

**Dependency split.** The application layer and the whole test suite depend only on **pydantic**. The evaluation code additionally uses `numpy`, `pandas` and `scikit-learn`. The model stack — `torch`, `transformers`, `datasets`, `tokenizers` — is **not** part of the local development environment and is installed in **Colab only**; `requirements.txt` should make that split explicit with comments so a reader knows what runs where.

- **`requirements.txt`** at the project root, pinned versions.
- **Colab notebook** — pip-install cell, clean top-to-bottom run on a free T4, `%cd` into the repo, `sys.path.insert(0, "src")`.
- **E1 baseline** — one simple prompt, **≥3 outputs** (plan says 5), GPT-2 vs Qwen side by side. This is what makes the E1→E2 improvement visible.
- **Reproducibility appendix** — versions, seeds, hardware from `device_report()`.

---

### 🟡 5.4 Satya — experiment runs (code merged, runs pending)

Code is done and merged. These are the *runs*, all blocked on 5.1 and 5.2.

1. Small follow-up: switch `flag_unsafe_responses` to read `record.row["response"]`.
2. **E2** — 4 variants × 385 rows → accuracy comparison table. Rationale per variant is already in `STRATEGY_RATIONALE`. Needs `data_prep.build_example_bank()` for defensible few-shot numbers.
3. **E3** — 6-config grid, 3 sample outputs each, variability analysis via `self_consistency_configs()`.
4. **E6** — 6 metrics, baseline vs final comparison, **≥3 analysed failure cases** (plan targets 6) with root causes. `CONFUSABLE_PAIRS` gives you the predicted failure modes to test against.
5. Report §4a (model families), §7 (prompts), §8 (decoding), §11 (results), §13 (limitations). The PR #1 routing bug is worth a paragraph in §13 — it is a genuine example of a metric that penalised a correct safety behaviour.

#### Inference budget — size this before you start

The prompt carries all 77 intent labels, so it is ~800 tokens (few-shot ~1,600). On a free Colab T4 with Qwen2.5-1.5B in fp16:

| Run | Generations | Unbatched | Batched |
|---|---|---|---|
| E2 — 4 variants × 385 rows | 1,540 | ~1.5 h | ~25 min |
| E3 — 6 configs × 385 rows | 2,310 | ~2.2 h | ~40 min |
| E1 + repair retries | ~400 | ~0.5 h | ~10 min |
| **Total** | | **~4–6 h** | **~1.5 h** |

**Two agreed scope cuts, both defensible in the report:**
1. **Run E3 on a stratified subset — 77 rows, 1 per intent.** E3 measures decoding behaviour and stability, not accuracy precision. It does not need 385 rows. Saves ~1.8 h.
2. **Batch the generation.** This is the difference between 6 hours and 90 minutes on a T4.

Keep E2 on the full 385 rows — that is the headline accuracy table.

### 🟡 5.5 Kishore — remaining

1. Real **E7** run on Colab once `model_loader` lands — swap `FakeGenerator` for `HFGenerator`, nothing else changes.
2. Report §2, §4b, §5, §9, §10, §12 — **already drafted in `ARCHITECTURE.md`**, needs formatting into the template.
3. Monday escalation trigger: take over 5.1 and 5.2 if they have not started.

### 🔴 5.6 Bhavani — start now, do not wait for results

**§1 abstract, §5 architecture, §10 structured output and §12 responsible use are already written in `ARCHITECTURE.md`.** Formatting those into the BITS WILP template is a real chunk of the report that needs zero experiment results. Start today.

Then: §3 dataset description (from Vishruth's `preprocessing_record()`), §14 conclusion, references, appendix (prompts/schemas/output samples), assembly into 10–15 pages, **individual contribution statement signed by all 4**, Section 8 compliance proofread, portal upload.

Git history is usable as supporting evidence for the contribution statement — commits are attributed per member.

---

## 6. FROZEN INTERFACES — do not change without telling Kishore

276 tests and `pipeline.py` depend on these.

```python
# structured output (E4)
parse_response(raw, allowed_intents) -> ValidationOutcome
build_repair_prompt(raw, outcome) -> str

# tools (E5)
route_intent(intent) -> ToolName | None
execute_tool(name, args) -> ToolResult

# generation seam (E1, E3)
class TextGenerator(Protocol):
    def generate(self, prompt: str, decode: DecodeConfig) -> str: ...

# prompts (E2)
build_prompt(strategy, query, allowed_intents, **kwargs) -> str

# decoding grid (E3)
build_decoding_grid() -> tuple[GridPoint, ...]
self_consistency_configs() -> dict[str, tuple[DecodeConfig, ...]]

# evaluation (E6)
records_from_rows(rows, gold_intents) -> list[EvalRecord]
evaluate_run(records) -> dict

# orchestration (E7)
SafeBankPipeline(generator, allowed_intents, strategy=...).run(query, decode) -> PipelineResult
PipelineResult.to_row() -> dict
```

`PipelineResult.to_row()` keys: `query`, `ok`, `intent`, `confidence`, `response`, `attempts`, `needed_repair`, `first_failure`, `tool`, `tool_ok`, `escalated`, `latency_ms`.

`response` is the **model's own reply**, not the composed `final_text`. Evaluation criterion 4 asks whether the model invented an account fact, so the screen must read what the model wrote; `final_text` also carries the `[system lookup: ...]` trace and the mandatory disclaimer, which the application adds and which would be false positives. Use `PipelineResult.final_text` directly for appendix samples.

**Nobody edits `schema.py`, `tools.py`, `pipeline.py`, `generator.py`, `config.py`, `intents.py` or `__init__.py` without telling Kishore first.**

---

## 7. How to verify your work

```powershell
# from the GenAI_Project1 directory. No install step, no PYTHONPATH needed.
python -m unittest discover -s tests -t . -v
```

Expected: `Ran 276 tests ... OK`, about 3 seconds warm. Runs on **pydantic alone**; `scikit-learn` is needed only for the macro-F1 assertions.

See the whole application run with no model:

```powershell
python -c "import sys; sys.path.insert(0,'src'); from safebank import *; p=SafeBankPipeline(FakeGenerator(), list(FOCUS_INTENTS)); r=p.run('my card has not arrived'); print(r.final_text)"
```

Byte-compile check: `python -m compileall -q src\safebank`

### Ground rules
- **Branch per person**, PR into `main`. Don't commit straight to `main`.
- Run the suite before every push. It takes 3 seconds.
- **Tests use stdlib `unittest`, not pytest.**
- **Keep `torch` / `transformers` / `datasets` imports inside function bodies**, never at module top level, so `import safebank` and the offline suite keep working.
- No real customer or financial data, ever. IDs stay synthetic (`CARD_SIM_0001`, `ACC_SIM_0001`) — Section 8 of the brief.
- Every prompt and decoding choice needs a written rationale. Section 8 forbids unexplained choices.

---

## 8. Known traps

| Trap | Consequence | Mitigation |
|---|---|---|
| `FOCUS_INTENTS` names unverified against real BANKING77 | E6 analysis describes intents never evaluated | `validate_label_space()` in `data_prep.py` — **mandatory** |
| `HFGenerator` returning prompt + completion | Every metric silently wrong | Strip the prompt; see §5.2 gotcha 1 |
| Model left in training mode | Greedy becomes non-deterministic, E3 stability meaningless | `model.eval()` |
| Few-shot examples drawn from the eval sample | **Contaminates every E2 number** | Train split only; `build_example_bank` reads `train_split` |
| Screening `final_text` for invented account facts | False positives from the legitimate system-lookup trace | Screen `to_row()['response']`, the model's own reply |
| Top-level `torch` import | Breaks `import safebank` and all 276 tests | Imports inside function bodies |
| Quoting `PROJECT_PLAN.md`'s old numbers in the report | Report contradicts the code | Use this file; plan corrected 25 Oct |
| A metric penalising correct safety behaviour | Reports a working control as a defect | The PR #1 routing bug. Check any new metric against the destructive-refusal path |

---

## 9. Change log

| Date | Entry |
|---|---|
| 23 Oct | Kishore: `config`, `intents`, `schema`, `tools`, `generator`, `pipeline` written |
| 23 Oct | Kishore: `__init__.py` + `prompts.py` seam with `ZERO_SHOT`; package imports for the first time |
| 23 Oct | Kishore: 195-test suite; E7 verified end-to-end; mutation check confirms safety tests have teeth |
| 23 Oct | Kishore: `ARCHITECTURE.md`, `HANDOFF.md`; repo initialised and pushed (`c921e0d`) |
| 25 Oct | Kishore: work log published; `PROJECT_PLAN.md` corrected (5 stale items); machine-specific detail removed from all docs |
| 25 Oct | Satya: PR #1 opened — E2 prompts (4/4), E3 grid, E6 metrics. 269 tests |
| 25 Oct | Kishore: PR #1 reviewed → `CHANGES_REQUESTED`. Blocking bug: `tool_routing` scored the destructive-tool refusal as a miss |
| 25 Oct | Satya: blocker fixed — `n_correctly_withheld` category + 5 regression tests. 274 tests |
| 25 Oct | Kishore: `to_row()` extended with the model reply for evaluation criterion 4 |
| 25 Oct | Kishore: **PR #1 approved and merged.** 276 tests on `main`. All code complete except `data_prep.py` and `model_loader.py` |

### Still open for the group
1. 🔴 **Colab environment decision** — blocks E1/E2/E3 and the real E7. Proposal: Colab for all model work, local for the application layer and tests.
2. 🟡 **BITS IDs for all 4 members** — needed for the report title page.
3. 🟡 **Repo is currently public** — recommend making it private until after submission.
