# Work Log — SafeBank Assist

**PCAM ZG516 Applied Generative AI · Group Major Project / Assignment-1 · Group 22**
**Deadline: 31 October 2026** (extended from 25 Oct) · Log updated: **28 October 2026**

This is the single source of truth for project status. If this file and `PROJECT_PLAN.md` disagree, **this file wins** — the plan was written before the code existed.

> **Picking this up in your own AI IDE?** Read sections 1, 5, 6 and 7. Section 5 contains complete specifications for every unwritten file: exact paths, signatures, contracts, gotchas and verification commands. You should not need to ask anyone a question to start.

---

## 1. Where we are

| | |
|---|---|
| **Overall completion** | **~60–65%** |
| **Marks — what is in git today** | **~8.5 / 20** |
| **Marks — achievable by 31 Oct** | **~16 / 20** (range 15–17) if the Colab run, E2/E3/E6 and the report all land |
| Application + experiment code | **100% — all 13 modules merged** |
| **Experiment results** | **0% — no E1/E2/E3/E6 output in git.** Vishruth's smoke runs verified the stack on real GPT-2 and Qwen but produced no reported numbers |
| Report | ~10% — drafts for §1, §2, §4b, §5, §9, §10, §12 exist in `ARCHITECTURE.md`; nothing assembled in the template |
| Demo | 0% |
| **Tests passing on `main`** | **353** (6 skipped — real-model, gated on `SAFEBANK_MODEL_TESTS=1`) |
| **All 13 modules** | ✅ implemented |

**One-line summary:** **all 13 modules are now written, reviewed and merged.** Zero experiment results exist. The project has stopped being a coding problem and is now two things: one Colab run, and a report nobody has started.

### Completion by workstream

| Member | Area | Status |
|---|---|---|
| **Kishore** | Architecture + application code | ✅ **100% — merged** |
| **Satya** | Prompts, decoding, evaluation code | ✅ **100% code — merged (PR #1).** Experiment *runs* still pending the environment |
| **Vishruth** | Data, model loading, environment, E1 | ✅ **Code 100% — merged (PR #2).** Notebook must be re-run with stored outputs |
| **Bhavani** | Report assembly, submission | 🔴 **~5% — NOT STARTED. Now the longest pole in the project.** See §2.1 |

### Rubric estimate (20 marks)

| # | Component | Marks | In git today | By 31 Oct | What closes the gap |
|---|---|---|---|---|---|
| 1 | Problem + dataset analysis | 2 | 0.7 | 1.7 | §3 write-up from `preprocessing_record()` and the class-distribution plot (notebook run) |
| 2 | LLM / generative-model understanding | 3 | 1.1 | 2.4 | §4b drafted (`ARCHITECTURE.md` §12) — paste in the notebook's tokenizer output. §4a model-family comparison unwritten |
| 3 | Prompt engineering | 3 | 1.2 | 2.4 | 4 variants merged with written rationale; **E2 accuracy table** |
| 4 | Adaptation strategy | 2 | 0.9 | 1.5 | Argued in `ARCHITECTURE.md` §7; needs measured E2 numbers to argue from |
| 5 | Structured output + tool calling | 3 | 2.2 | 2.7 | Complete and tested; E4 validity rate before/after repair from a real run |
| 6 | Implementation | 3 | 2.1 | 2.7 | 353 tests, pinned requirements, reviewed PRs; **notebook with stored outputs** |
| 7 | Evaluation + failure analysis | 2 | 0.3 | 1.5 | Metrics merged, 2 real failures recorded; **E6 run + ≥3 analysed failure cases** |
| 8 | Report + demo + contribution | 2 | 0.0 | 1.4 | Assembled report, 8–10 min demo, signed contribution statement |
| | | **20** | **~8.5** | **~16** | |

"In git today" is what a grader could award for what is committed now. "By 31 Oct" assumes the plan lands. The gap is almost entirely results and writing — no component is still blocked on code. The earlier single figure of ~12.6 counted finished work as if it were already written up; these two columns replace it.

---

## 2.1 🔴 BHAVANI — START TODAY, NOTHING BLOCKS YOU

**This is now the single largest piece of remaining work in the project, and it has not started.** The report is worth 2 marks directly, but it is also *how components 1, 2, 3, 4 and 7 get assessed — around 8 further marks*. Good results in a badly assembled report score poorly.

**You do not need to wait for experiment results.** About half of the report can be written right now, because the source material is already written and merged.

### Write these six sections today — source material already exists

| Report section | Source | What to do |
|---|---|---|
| **§1 Abstract** | `ARCHITECTURE.md` §1 | Condense "The application" + "Why a generative LM" into ~200 words |
| **§2 Problem statement** | `ARCHITECTURE.md` §1 | Problem, target user, input/output and why an LLM — all written |
| **§4b LLM architecture** | `ARCHITECTURE.md` §12 | Drafted with equations and a two-model comparison table, every figure verified. Leave the §12.8 tokenizer example for the notebook output |
| **§5 Proposed architecture** | `ARCHITECTURE.md` §2 + §3 + §4 | The pipeline diagram is already drawn in §2 — redraw it in the template. §4 explains the `TextGenerator` seam |
| **§10 Structured output + tool calling** | `ARCHITECTURE.md` §5 + §6 | Schema table, the JSON example, the failure taxonomy, the 3 tool I/O schemas. All written, needs formatting |
| **§12 Responsible-use controls** | `ARCHITECTURE.md` §8 | A 10-row control table, each row implemented and test-backed. One of the strongest parts of the project — give it room |

### Then these, as inputs arrive

| Section | Waiting on | From |
|---|---|---|
| §3 Dataset description | `data_prep.preprocessing_record()` + class-distribution plot | Vishruth's notebook run |
| §6 Baseline implementation | E1 output | Vishruth |
| §4a Model families · §7 Prompts · §8 Decoding · §11 Results · §13 Limitations | Experiment results | Satya (on leave — may fall to Kishore) |
| §9 Adaptation strategy | Argued in `ARCHITECTURE.md` §7; quote the E2 numbers once they exist | Kishore |
| §14 Conclusion + future work | Everything else | You, last |

### Also yours, and none of it needs results

- **Appendix** — prompts, schemas, output samples. `tools.tool_specs_json()` and `schema.response_json_schema()` both emit report-ready JSON today.
- **References.**
- **Individual contribution statement, signed by all four.** Start collecting now, don't leave it to the 31st. The git history is usable as supporting evidence — every commit is attributed.
- **BITS IDs for all four members** for the title page. Still missing. Chase them today.
- **Section 8 compliance proofread** — no ChatGPT screenshots, no unexplained prompts, no accuracy claims without procedure, no real financial data.
- **Keep it inside 10–15 pages** excluding appendix.

### Why the urgency is real

Three days left (Wed 28 → Sat 31), and no buffer any more. If the report waits for results it gets written in one day and it will show. Six sections are sitting there ready to be formatted. **Starting them today is the difference between a report that reads as considered and one that reads as rushed.**

---

## 2. Day-by-day plan to 31 Oct

**No buffer left** — the Tuesday and Wednesday items have slipped.

| Day | Must land | Owner | State |
|---|---|---|---|
| **Sun 25** | PR #1 reviewed and merged · `to_row()` extended for criterion 4 · `PROJECT_PLAN.md` corrected · work log published | Kishore | ✅ **done** |
| **Sun 25** | `data_prep.py` + `model_loader.py` + notebook + requirements | Vishruth | ✅ **merged (PR #2), verified against real data, GPT-2 and Qwen** |
| **Sun 25** | Review fixes: `examples=` passthrough · credential-solicitation control | Kishore | ✅ **done, 353 tests** |
| **Sun 25** | Report §1/§5/§10/§12 drafted from `ARCHITECTURE.md` | Bhavani | 🔴 **OUTSTANDING — see §2.1** |
| **Mon 26** | **Notebook re-run on Colab T4 with stored outputs** → delivers E1, Colab packaging, reproducibility appendix | Vishruth | 🔴 **not in git as of Wed 28 — still the most time-critical item** |
| **Mon 26** | `data_prep.py` working · **`validate_label_space()` passes** · `model_loader` running on Colab · E1 baseline captured | Vishruth | ✅ first three verified 25 Oct · 🔴 E1 output not in git |
| **Tue 27** | E2 full run (4 variants × 385 rows) · real E7 integrated run | Satya, Kishore | 🔴 **overdue** — nothing in git |
| **Wed 28** | E3 decoding grid (reduced scope) · E6 evaluation + failure analysis | Satya | 🔴 **due today** — waits on the notebook run |
| **Wed 28** | Report §4b drafted, figures verified against the published model configs · docs swept for stale counts | Kishore | ✅ **done** |
| **Thu 29** | All report sections drafted · figures generated | all | pending |
| **Fri 30** | Report assembled + formatted + proofread · demo rehearsal | Bhavani + all | pending |
| **Sat 31** | Contribution statement signed · **submit** | Bhavani | pending |

### Escalation triggers

~~**If `data_prep.py` and `model_loader.py` are not running by Monday 26 Oct evening, Kishore takes them over.**~~ ✅ **Not needed — Vishruth delivered both on 25 Oct, verified against real data and models.**

🔴 **New trigger: Satya is on leave.** E2, E3 and E6 are his and they are the largest remaining technical block. **If he is not back by Tuesday 27 Oct, Kishore runs them.** All three are code-complete and merged, so this is execution and write-up, not development — but it cannot wait, because §7, §8, §11 and §13 of the report all depend on the output. ⚠️ **Tuesday has passed with no E2/E3/E6 output in git, so this trigger has fired.** Kishore decides today whether he runs them.

---

## 3. DONE — merged to `main`

**353 tests — 347 run offline and pass, 6 real-GPT-2 tests are gated — with only pydantic installed.** No torch, no GPU, no network. The whole application and evaluation stack is verifiable offline.

### Kishore — architecture and application

| File | Lines | What it does | Experiment |
|---|---|---|---|
| `src/safebank/config.py` | 85 | Seeds, model ids, dataset id, thresholds, artifact paths | — |
| `src/safebank/intents.py` | 228 | `INTENT_THEMES` (5×4), `FOCUS_INTENTS` (20), `CONFUSABLE_PAIRS` (6 predicted), `OBSERVED_CONFUSIONS` (1 observed), `validate_label_space()` | E6 input |
| `src/safebank/schema.py` | 264 | `AssistantResponse`, `ToolCall`, `extract_json_block()`, `FailureKind` (4 kinds), `parse_response()`, `build_repair_prompt()` | **E4** |
| `src/safebank/tools.py` | 302 | 3 simulated tools + I/O schemas, deterministic handlers, `TOOL_REGISTRY`, `INTENT_TO_TOOL` (10 intents), `tool_specs_json()` | **E5** |
| `src/safebank/generator.py` | 131 | `TextGenerator` Protocol, `DecodeConfig`, `DecodeStrategy`, `FakeGenerator` | E1/E3 seam |
| `src/safebank/pipeline.py` | 405 | `SafeBankPipeline`, repair-retry, safety screen, confidence gate, intent-authoritative routing, destructive-tool refusal, `prompt_kwargs`, `to_row()` | **E7** |
| `src/safebank/safety.py` | 265 | `scan_reply()`: credential solicitation (blocking) and invented account facts (flagged), `WITHHELD_REPLY` | **R13** |
| `src/safebank/__init__.py` | 143 | Public API, 44 exports | — |

### Satya — prompts, decoding, evaluation (PR #1, merged)

| File | Lines | What it does | Experiment |
|---|---|---|---|
| `src/safebank/prompts.py` | 786 | All 4 strategies — `ZERO_SHOT`, `FEW_SHOT`, `ROLE_CONTEXT`, `CONSTRAINT_BASED` — plus shared formatters and `STRATEGY_RATIONALE` | **E2** |
| `src/safebank/decoding.py` | 288 | 6-config E3 grid on the existing `DecodeConfig`, `seed_variations()`, `self_consistency_configs()` | **E3** |
| `src/safebank/evaluate.py` | 792 | All 6 evaluation criteria, `EvalRecord`, `response_safety()`, `analyse_failures()`, `evaluate_run()`, `results_dataframe()` | **E6** |

### Vishruth — data, model loading, environment (PR #2, merged)

| File | Lines | What it does | Experiment |
|---|---|---|---|
| `src/safebank/data_prep.py` | 368 | BANKING77 from the official CSVs, split-size check, `validate_label_space()`, 385-row stratified eval sample, train-split example bank, preprocessing record | E1–E6 input |
| `src/safebank/model_loader.py` | 345 | `device_report()`, cached `load_model_and_tokenizer()`, `HFGenerator` with a neutral generation config, `generate_batch()`, token and latency log | **E1** |
| `requirements.txt`, `requirements-colab.txt` | — | Pinned versions; Colab installs only transformers, tokenizers and datasets on top of its own torch | — |
| `notebooks/safebank_colab.ipynb` | 18 cells | Setup + device report, class distribution, E1, tokenizer walkthrough, E7 smoke run. **No stored outputs yet** | E1, E7 |

### Test suite — 353 tests

| Module | Tests | Covers |
|---|---|---|
| `tests/test_prompts.py` | 59 | All 4 variants, shared blocks, dispatch, preprocessing |
| `tests/test_pipeline.py` | 55 | E7: repair-retry, safety screen, confidence gate, destructive refusal, hallucination guards, `prompt_kwargs`, `to_row()` |
| `tests/test_evaluate.py` | 39 | All 6 metrics, failure analysis, routing regression tests |
| `tests/test_tools.py` | 38 | 3 tools, arg validation, determinism, routing, spec export |
| `tests/test_schema.py` | 35 | E4: extraction edge cases, all 4 `FailureKind` paths, repair prompt |
| `tests/test_data_prep.py` | 24 | Label space, 385-row stratified sample, example bank, preprocessing record |
| `tests/test_safety.py` | 24 | Credential solicitation incl. the observed PIN reply, negations, word boundaries |
| `tests/test_decoding.py` | 23 | E3 grid shape, labels, seed variation |
| `tests/test_generator.py` | 22 | Per-strategy decode kwargs, protocol conformance |
| `tests/test_intents.py` | 21 | Label-space structure, confusable pairs, validation guard |
| `tests/test_model_loader.py` | 13 | `HFGenerator` contract offline (7); real GPT-2 behaviour (6, gated on `SAFEBANK_MODEL_TESTS=1`) |

### Verification evidence captured

- Full suite: `Ran 353 tests ... OK (skipped=6)`
- `compileall` clean on all modules
- Real E7 trace: prompt built → JSON validated → `card_arrival` → `check_card_delivery_status` → `{'status': 'in_transit', 'dispatched_on': '2026-10-12', 'eta_days': 5}` → disclaimer attached
- **Mutation check:** flipping `block_card.destructive` to `False` in memory fails 4 tests — the safety control is genuinely guarded, not merely asserted
- **Routing-metric check:** an all-correct run scores `routing_accuracy 1.0` with `n_correctly_withheld 3`; four anti-regression cases confirm the destructive exemption cannot hide a genuine dropped call
- **Real data and models (Vishruth, 25 Oct):** `validate_label_space()` passes on the real 77 labels (splits 10,003 / 3,080); GPT-2 shows no prompt echo, deterministic greedy and reproducible seeded sampling; Qwen2.5-1.5B through the pipeline returns valid JSON first time (~750 prompt tokens) and `block_card` escalates
- **Safety control:** the observed reply asking for an account number and PIN is withheld and escalated; the customer sees a warning instead

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

### ✅ 5.1 Vishruth — `src/safebank/data_prep.py` (MERGED, PR #2)

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

✅ **Passed on 25 Oct** against the real label space (77 intents, splits 10,003 / 3,080), so all 20 `FOCUS_INTENTS` names are real labels. The call stays in `load_banking77` as the guard if the dataset source ever changes.

**Signature as merged** adds `*, exclude=frozenset()` to `build_example_bank`. **Pass the eval queries as `exclude`** — the default is empty, so the train/test-overlap protection is opt-in and forgetting it contaminates E2 silently.

**For E2:** `build_example_bank()` is what makes E2's few-shot numbers defensible. `prompts.build_few_shot_prompt` has an offline fallback bank so the code is testable, but reported E2 results need real train-split examples.

**Facts you need:** `config.DATASET_ID = "PolyAI/banking77"` · `config.EXPECTED_N_INTENTS = 77` · `config.EVAL_EXAMPLES_PER_INTENT = 5` · `config.SEED = 42`

---

### ✅ 5.2 Vishruth — `src/safebank/model_loader.py` (MERGED, PR #2)

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

✅ **All six are implemented, plus a seventh:** every sampling knob in Qwen's shipped `generation_config.json` is reset to neutral before a `DecodeConfig` is applied.

**Models:** `config.MODEL_ID = "Qwen/Qwen2.5-1.5B-Instruct"` · `config.BASELINE_MODEL_ID = "gpt2"` · `config.MAX_NEW_TOKENS = 192`

**Self-check once written:**

```python
from safebank.generator import TextGenerator
assert isinstance(HFGenerator(model, tok), TextGenerator)   # runtime_checkable Protocol
```

---

### 🔴 5.3 Vishruth — `requirements.txt` + Colab notebook + E1 (files merged; **Colab run with stored outputs PENDING**)

**Dependency split.** The application layer and the whole test suite depend only on **pydantic**. The evaluation code additionally uses `numpy`, `pandas` and `scikit-learn`. The model stack — `torch`, `transformers`, `datasets`, `tokenizers` — is **not** part of the local development environment and is installed in **Colab only**; `requirements.txt` should make that split explicit with comments so a reader knows what runs where.

- **`requirements.txt`** at the project root, pinned versions.
- **Colab notebook** — pip-install cell, clean top-to-bottom run on a free T4, `%cd` into the repo, `sys.path.insert(0, "src")`.
- **E1 baseline** — one simple prompt, **≥3 outputs** (plan says 5), GPT-2 vs Qwen side by side. This is what makes the E1→E2 improvement visible.
- **Reproducibility appendix** — versions, seeds, hardware from `device_report()`.

---

### 🟡 5.4 Satya — experiment runs (code merged, runs pending)

Code is done and merged. These are the *runs*. They no longer wait on any code, only on a Colab session. ⚠️ Satya is on leave and the Tuesday trigger has passed — see §2.

1. ~~Switch `flag_unsafe_responses` to read `record.row["response"]`~~ ✅ done by Kishore: use `evaluate.response_safety(records)`.
2. **E2** — 4 variants × 385 rows → accuracy comparison table. Rationale per variant is already in `STRATEGY_RATIONALE`. For FEW_SHOT pass real examples: `SafeBankPipeline(gen, labels, strategy=PromptStrategy.FEW_SHOT, prompt_kwargs={"examples": build_example_bank(train, labels, exclude={r["query"] for r in eval_rows})})`. Qwen's chat template adds a default system prompt to every variant — note it in report §7 (see §8).
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

1. Real **E7** run on Colab — `model_loader` has landed, so swap `FakeGenerator` for `HFGenerator(*load_model_and_tokenizer())`; nothing else changes.
2. Report text. Drafts in `ARCHITECTURE.md`: §2 ← §1 · **§4b ← §12** (drafted 28 Oct; figures verified against the published model configs; the §12.8 tokenizer example waits on the notebook run) · §5 ← §2–§4 · §9 ← §7 · §10 ← §5–§6 · §12 ← §8. Hand final text to Bhavani. *Correction: until 28 Oct this item said §4b was already drafted. It was not — the document only had a one-line pipeline mention.*
3. ⚠️ The Satya trigger has fired (§2): decide today whether to run E2/E3/E6.

### 🔴 5.6 Bhavani — start now, do not wait for results

**§1 abstract, §5 architecture, §10 structured output and §12 responsible use are already written in `ARCHITECTURE.md`.** Formatting those into the BITS WILP template is a real chunk of the report that needs zero experiment results. Start today.

Then: §3 dataset description (from Vishruth's `preprocessing_record()`), §14 conclusion, references, appendix (prompts/schemas/output samples), assembly into 10–15 pages, **individual contribution statement signed by all 4**, Section 8 compliance proofread, portal upload.

Git history is usable as supporting evidence for the contribution statement — commits are attributed per member.

---

## 6. FROZEN INTERFACES — do not change without telling Kishore

353 tests and `pipeline.py` depend on these.

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
response_safety(records) -> SafetyReport

# orchestration (E7)
SafeBankPipeline(generator, allowed_intents, strategy=..., prompt_kwargs=...).run(query, decode) -> PipelineResult
PipelineResult.to_row() -> dict
```

`PipelineResult.to_row()` keys: `query`, `ok`, `intent`, `confidence`, `response`, `attempts`, `needed_repair`, `first_failure`, `tool`, `tool_ok`, `escalated`, `safety_issues`, `reply_withheld`, `latency_ms`.

`response` is the **model's own reply**, not the composed `final_text`. Evaluation criterion 4 asks whether the model invented an account fact, so the screen must read what the model wrote; `final_text` also carries the `[system lookup: ...]` trace and the mandatory disclaimer, which the application adds and which would be false positives. Use `PipelineResult.final_text` directly for appendix samples.

**Nobody edits `schema.py`, `tools.py`, `pipeline.py`, `generator.py`, `config.py`, `intents.py` or `__init__.py` without telling Kishore first.**

---

## 7. How to verify your work

```powershell
# from the GenAI_Project1 directory. No install step, no PYTHONPATH needed.
python -m unittest discover -s tests -t . -v
```

Expected: `Ran 353 tests ... OK (skipped=6)`, a few seconds warm. Runs on **pydantic alone**; `scikit-learn` is needed only for the macro-F1 assertions.

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
| ~~`FOCUS_INTENTS` unverified against real BANKING77~~ | — | ✅ **CLOSED 25 Oct.** `validate_label_space()` passes: 77 intents, splits 10,003 / 3,080, all 20 focus names correct |
| **Qwen ships its own sampling defaults** — published `generation_config.json`: `do_sample=True, temperature=0.7, top_k=20, top_p=0.8, repetition_penalty=1.1` | Sampling is on by default, and a "temperature only" E3 run would silently apply all of them — the decoding comparison becomes meaningless | `model_loader` resets every one to neutral (checked in code, 28 Oct). Its docstring and the PR #2 notes quote `1.05`; the published file says `1.1` |
| **Qwen's chat template injects a system prompt** | Every Qwen prompt carries *"You are Qwen, created by Alibaba Cloud. You are a helpful assistant."*, because `HFGenerator` sends only a user message | Identical across the E2 variants, so comparisons stay fair. State it in report §7: the role-context persona sits in the user turn under a generic system persona |
| Reporting `confidence` as a probability | It is generated digits, not a calibrated score | Call it a self-reported escalation signal; see `ARCHITECTURE.md` §12.7 |
| **GPT-2's 1024-token context < few-shot prompt (~1,600 tokens)** | A GPT-2 few-shot number measures truncation, not capability; reported as a clean comparison it is a confound | Truncation keeps the customer query and is recorded. State the limitation in report §13 |
| **6 texts appear in both train and test** | Few-shot examples could leak eval text | Pass the eval queries as `build_example_bank(..., exclude=...)`. **It defaults to empty**, so the protection is opt-in |
| Model reply asks the customer for credentials | Phishing-shaped output reaching a customer; invisible to accuracy, validity and routing | `safety.scan_reply` blocks it, `pipeline` withholds the reply and escalates |
| `HFGenerator` returning prompt + completion | Every metric silently wrong | Strip the prompt; see §5.2 gotcha 1 |
| Model left in training mode | Greedy becomes non-deterministic, E3 stability meaningless | `model.eval()` |
| Few-shot examples drawn from the eval sample | **Contaminates every E2 number** | Train split only; `build_example_bank` reads `train_split` |
| Screening `final_text` for invented account facts | False positives from the legitimate system-lookup trace | Screen `to_row()['response']`, the model's own reply |
| Top-level `torch` import | Breaks `import safebank` and all 353 tests | Imports inside function bodies |
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
| 25 Oct | Kishore: **PR #1 approved and merged.** 276 tests on `main` |
| 25 Oct | Vishruth: PR #2 — `data_prep.py`, `model_loader.py`, requirements, Colab notebook. 313 tests |
| 25 Oct | Vishruth: ran it for real. **`validate_label_space()` passes** against the real 77 labels (splits 10,003 / 3,080) — closes the project's longest-standing verification gap. GPT-2 and Qwen2.5-1.5B both verified through the pipeline |
| 25 Oct | Vishruth found 4 problems, all real. Most valuable: **Qwen ships `top_k=20, top_p=0.8, repetition_penalty=1.05`**, so a "temperature only" E3 run would silently have been all four knobs. That would have invalidated the entire decoding comparison and nothing in the output would have shown it |
| 25 Oct | Kishore: fixed his own bug from that review — `SafeBankPipeline` never forwarded `examples=`, so every few-shot run used the illustrative fallback bank. Added `prompt_kwargs` plus a warning on the silent case |
| 25 Oct | Kishore: **PR #2 approved and merged.** All 13 modules now implemented |
| 25 Oct | Kishore: new `safety.py` — blocks credential solicitation after the real Qwen run asked a customer for their account number and PIN. Taken over from Satya, who is on leave. Also fixed a latent bug where three escalation sites overwrote each other's reason, which was erasing the safety failure from the E6 table. 353 tests |
| 25 Oct | Vishruth: `data_prep.py`, `model_loader.py`, `requirements*.txt`, `notebooks/safebank_colab.ipynb` on `vishruth/data-prep-model-loader`. 313 tests (+37; 6 real-GPT-2 tests gated by `SAFEBANK_MODEL_TESTS=1`, all pass). `validate_label_space()` **passes on the real 77 labels**. Findings: Hub dataset is script-based so `datasets` ≥4 cannot load it (loader reads the official CSVs instead); Qwen's shipped `top_k=20/top_p=0.8/rep_penalty=1.05` neutralised so E3 configs are clean; GPT-2's 1024-token window needs left-truncation for few-shot; 6 texts appear in both splits (excluded from the few-shot bank); **`SafeBankPipeline` does not forward `examples=` to `build_prompt`**, so few-shot via the pipeline uses the fallback bank (Kishore to fix) |
| 28 Oct | Kishore: full git audit — every branch of the repo and of both forks, all PRs, comments and events since 25 Oct. **No experiment output, no `artifacts/`, no stored notebook outputs and no report work from anyone since 26 Oct** |
| 28 Oct | Kishore: **report §4b drafted** as `ARCHITECTURE.md` §12. Every figure checked against the published `config.json` / `generation_config.json` / `tokenizer_config.json` of both models; Qwen's parameter counts match its model card (1.54 B, 1.31 B non-embedding). Corrects this log's earlier claim that §4b was already drafted |
| 28 Oct | Kishore: found while verifying — Qwen's published `repetition_penalty` is **1.1**, not the 1.05 quoted on 25 Oct (the neutral reset covers it either way); Qwen's chat template injects a default system prompt into every prompt; `ARCHITECTURE.md` §7 claimed "constrained decoding", which we do not implement — corrected to post-generation validation |
| 28 Oct | Kishore: stale figures swept across all four docs — 276 → 353 tests, Vishruth's modules marked merged, marks estimate split into "in git today" (~8.5) and "by 31 Oct" (~16) |

### Still open for the group
1. 🔴 **The Colab run.** The environment question is settled (model work in Colab, everything else local). What is missing is the run itself: E1, E2, E3, E6 and the real E7 all wait on it.
2. 🔴 **Satya's experiments** — the trigger has fired (§2); who runs E2/E3/E6 is to be decided today.
3. 🟡 **BITS IDs for all 4 members** — needed for the report title page.

The repo is **public on purpose**: the professor reviews and validates the project from GitHub.
