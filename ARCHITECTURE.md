# SafeBank Assist — Solution Architecture

**PCAM ZG516 Applied Generative AI · Group Major Project / Assignment-1 · Group 22**

Author: Nandhaluru Kishore (Solution Architect & Application Lead)
Source material for report §2, §4b, §5, §9, §10 and §12 (§4b is section 12 of this document).
Status as of 28 October 2026.

---

## 1. The application

**SafeBank Assist** is a first-line banking support triage assistant.

A tier-1 support agent at a retail bank receives free-text customer messages. For each one a human must work out what the customer actually wants out of 77 possible request types, decide whether a system lookup is needed, and reply without inventing account facts. That is slow and inconsistent between agents.

| | |
|---|---|
| **Input** | One free-text customer message |
| **Output** | A pydantic-validated JSON object: intent, confidence, customer-safe reply, optional tool call, escalation flag, provenance disclaimer |
| **Dataset** | BANKING77 (`PolyAI/banking77`), full 77-intent label space |
| **Model** | `Qwen/Qwen2.5-1.5B-Instruct` (instruction-tuned causal LM) |
| **Weak baseline** | `gpt2`, to make the E1 → E2 improvement visible |

### Why a generative LM rather than a classifier

A plain 77-way classifier returns a label and nothing else. This task needs four things at once: the label, a natural-language reply, a routing decision about whether to call a system, and structured output a downstream system can act on. A prompted causal LM does all four in a single pass, and absorbs a new intent without retraining. The cost is that its output is unconstrained text, which is precisely the problem §4 and §5 below are designed to contain.

---

## 2. Pipeline

```
customer query
  │
  ├─► preprocessing                    prompts._clean_query
  │     whitespace collapse, quote strip. Deliberately minimal: BANKING77
  │     queries are short and informal, and lowercasing or stripping
  │     punctuation would destroy cues the model uses.
  │
  ├─► prompt construction              prompts.build_prompt(strategy, …)
  │     intent catalogue + tool catalogue + schema contract + rules
  │
  ├─► generation                       generator.TextGenerator.generate
  │     tokenize → embed → transformer stack → LM head → autoregressive
  │     decode under a DecodeConfig
  │
  ├─► decoding control                 generator.DecodeConfig
  │     greedy | temperature | top-k | top-p
  │
  ├─► raw completion  (unconstrained text — the containment boundary)
  │
  ├─► JSON extraction                  schema.extract_json_block
  │     brace-balanced, string-literal aware
  │
  ├─► schema validation                schema.parse_response
  │     ├── ok ──────────────────────────────────────────┐
  │     └── fail → build_repair_prompt → regenerate ─────┤  (≤ 2 attempts)
  │                                                      │
  ├─► safety screen                    pipeline._apply_safety_screen
  │     reply asks for a PIN, password or card number → withhold it, escalate
  │
  ├─► confidence gate                  pipeline._apply_confidence_gate
  │     confidence < 0.55 or requires_human → escalate
  │
  ├─► tool routing                     tools.route_intent
  │     authority is the VALIDATED INTENT, never the model's tool_call
  │     destructive tool → refuse, escalate for human confirmation
  │
  ├─► tool execution                   tools.execute_tool
  │     argument validation, then deterministic simulated handler
  │
  └─► response composition             pipeline._compose
        reply + system-lookup trace + escalation note + disclaimer
```

Every stage is captured in a `PipelineResult`, and `PipelineResult.to_row()` flattens one run into a single record. Nothing is printed, so the notebook tabulates runs instead of parsing logs.

---

## 3. Module map

| Module | Responsibility | Experiment | Owner | Status |
|---|---|---|---|---|
| `config.py` | Every tunable constant: seeds, model ids, thresholds, paths | — | Kishore | **Done** |
| `intents.py` | Label-space guard, E6 focus subset, confusable pairs | E6 input | Kishore | **Done** |
| `schema.py` | Structured-output contract, JSON extraction, validation, repair | **E4** | Kishore | **Done** |
| `tools.py` | 3 simulated tools, I/O schemas, intent→tool router | **E5** | Kishore | **Done** |
| `generator.py` | `TextGenerator` protocol, `DecodeConfig`, `FakeGenerator` | E3 surface | Kishore | **Done** |
| `pipeline.py` | End-to-end orchestration | **E7** | Kishore | **Done** |
| `safety.py` | Reply screening: credential solicitation (blocking) and invented account facts (flagged) | **R13** | Kishore | **Done** |
| `__init__.py` | Curated public API, 44 exports | — | Kishore | **Done** |
| `prompts.py` | 4 prompt strategies, shared formatters, written rationale per variant | **E2** | Kishore (seam + zero-shot) → Satya (3 variants) | **Done**, 4 of 4 |
| `decoding.py` | 6-config decoding grid, seed variation, self-consistency sets | **E3** | Satya | **Done** |
| `evaluate.py` | All 6 metrics, `EvalRecord`, failure analysis, comparison tables | **E6** | Satya | **Done** |
| `experiments.py` | E2/E3/E6 runner: batched first-attempt replay through the unchanged pipeline, grid and seed sweeps, failure-case selection, result persistence | **E2/E3/E6** | Satya | **Done** |
| `data_prep.py` | BANKING77 load, stratified 385-row eval sample, train-split example bank, preprocessing record | — | Vishruth | **Done** |
| `model_loader.py` | HF model + tokenizer loading, `HFGenerator`, batched generation, token and latency log | E1 | Vishruth | **Done** |

**All 13 modules are implemented and merged.** The suite has 353 tests: 347 run offline and pass, and 6 that load real GPT-2 weights are skipped unless `SAFEBANK_MODEL_TESTS=1`. The E1 and E2/E3/E6 runs have since been done (see `WORKLOG.md`, 31 Oct).

---

## 4. The `TextGenerator` seam

The single most consequential design decision in this architecture.

`pipeline.py` never imports `torch` or `transformers`. It depends on a one-method protocol:

```python
@runtime_checkable
class TextGenerator(Protocol):
    def generate(self, prompt: str, decode: DecodeConfig) -> str: ...
```

Three consequences, all of which the project depends on:

1. **The application is testable with no model runtime.** The local development environment provides pydantic, numpy, pandas and scikit-learn, but no `torch`, `transformers`, `datasets` or `tokenizers` — the model stack runs in Colab only. The full suite (353 tests) still exercises the complete control flow via `FakeGenerator`.
2. **Teammate modules can land independently.** `model_loader.HFGenerator` drops in behind the same protocol without touching a line of the pipeline.
3. **E3 is a data change, not a code change.** The decoding grid varies `DecodeConfig`; no branch in the pipeline knows which strategy is running.

`DecodeConfig` is a frozen dataclass, so every logged run is traceable to an exact, printable configuration. `to_generate_kwargs()` emits only the knobs relevant to the chosen strategy — a greedy run cannot accidentally carry a temperature value and corrupt the E3 comparison.

---

## 5. Structured output (Requirement 9, E4)

### `AssistantResponse`

| Field | Type | Constraint | Purpose |
|---|---|---|---|
| `intent` | `str` | must be a BANKING77 label | the prediction |
| `confidence` | `float` | `0.0 ≤ x ≤ 1.0` | drives the escalation gate |
| `response` | `str` | non-empty | customer-facing reply |
| `tool_call` | `ToolCall \| None` | tool name from enum | requested lookup |
| `requires_human` | `bool` | default `False` | model-initiated escalation |
| `disclaimer` | `str` | default from `config` | provenance, application-enforced |

```json
{
  "intent": "card_arrival",
  "confidence": 0.82,
  "response": "I can see your card was dispatched. Let me check the delivery status.",
  "tool_call": { "name": "check_card_delivery_status", "args": { "card_id": "CARD_0417" } },
  "requires_human": false,
  "disclaimer": "Information shown is from a simulated system of record, not live banking data."
}
```

Two choices worth defending in the viva:

- **`extra="forbid"`.** If the model invents a field — `"account_balance": "4210.00"` — that is a hard validation failure we count, not a key we silently drop. Hallucination becomes a measurable event.
- **`disclaimer` has a schema default and is never requested from the model.** Letting the model author its own provenance notice would defeat the control. The prompt's schema block deliberately omits this field.

### Failure taxonomy

`parse_response` classifies every rejection into one of four kinds, so E4 reports *why* outputs fail rather than only how often:

| `FailureKind` | Cause |
|---|---|
| `NO_JSON_FOUND` | no balanced object in the completion |
| `MALFORMED_JSON` | object found, `json.loads` failed |
| `SCHEMA_VIOLATION` | parsed, but violates the pydantic contract |
| `UNKNOWN_INTENT` | schema-valid, but the label is not in BANKING77 |

`UNKNOWN_INTENT` is the one that matters most. A 1.5B model asked for one of 77 fine-grained labels will readily emit a plausible-sounding label that does not exist. Separating it from `SCHEMA_VIOLATION` is what lets the report distinguish a *formatting* failure from a *hallucination*.

### Repair-retry

On failure, `build_repair_prompt` shows the model its own rejected output plus the validator's error list, and regenerates — at most `REPAIR_MAX_ATTEMPTS = 2` times. E4 reports schema validity before and after this loop; the delta is the measured value of the repair mechanism.

---

## 6. Tool calling (Requirement 10, E5)

Three tools, each with a declared pydantic input schema, output schema and a deterministic simulated handler. No network, no credentials, no real financial data — Section 8 compliance.

| Tool | Input | Output | Triggering intents |
|---|---|---|---|
| `check_card_delivery_status` | `card_id: str(≥3)` | `status, dispatched_on, eta_days` | `card_arrival`, `card_delivery_estimate`, `order_physical_card`, `getting_spare_card` |
| `block_card` **(destructive)** | `account_id: str(≥3)`, `reason: lost\|stolen\|compromised\|damaged` | `blocked, ref_id, replacement_eta_days` | `lost_or_stolen_card`, `compromised_card`, `card_swallowed` |
| `find_branch` | `pincode: str(4–10)`, `service: cash_deposit\|atm\|card_collection\|identity_verification` | `branch_name, address, distance_km` | `atm_support`, `cash_withdrawal_charge`, `declined_cash_withdrawal` |

10 of the 77 intents route to a tool. The other 67 are answered with text only — most genuinely need no system lookup, and inventing one would be a reliability risk rather than a feature.

**Determinism.** Handlers derive results from a SHA-256 hash of their input against a fixed reference date, so the same argument always yields the same result. A grader re-running the notebook sees identical output. Tested explicitly, including the inverse property that different inputs do produce different results, so determinism has not collapsed into a constant.

**Two independent validation layers.** Response validation and tool-argument validation are separate on purpose: a model can emit a schema-valid response carrying nonsense tool arguments, and E5 reports those two failure sources independently.

---

## 7. Adaptation strategy: prompting vs RAG vs PEFT (report §9)

| Approach | Fit for this task | Verdict |
|---|---|---|
| **Prompting + validated structured output** | The label space is 77 fixed names that fit in context. The task is classification plus short generation, not knowledge recall. Zero training cost, and a new intent is a catalogue edit. Output is checked *after* generation (schema validation, label check, repair-retry); we do not constrain the logits *during* generation — see §12.7. | **Chosen** |
| **RAG** | There is no external corpus to retrieve from. The intent catalogue is small enough to pass in full, so retrieval would add latency and a new failure mode (wrong chunk retrieved) for no gain. RAG *would* win if the assistant had to quote bank policy documents or per-customer history. | Rejected, with the condition stated |
| **PEFT / LoRA** | Would likely beat prompting on top-1 accuracy, since BANKING77 has ~10k labelled training rows. Costs a training run, a checkpoint to version, and re-training whenever an intent is added. | Rejected for this scope; named as the first thing to try if measured accuracy is the binding constraint |

The honest position for the report: prompting was chosen because it isolates the generative-AI concepts the assignment asks us to demonstrate, and because the 77-label catalogue fits in context. Whether it is the *most accurate* option is an empirical question, and E2's numbers are what should decide it.

---

## 8. Responsible-use controls (Requirement 13, report §12)

Each control is implemented, not aspirational, and each has a test that fails if it is removed.

| Risk | Control | Where |
|---|---|---|
| **Invented intent** | Label checked against the dataset's own 77 names; mismatch → `UNKNOWN_INTENT` | `schema.parse_response` |
| **Invented response field** | `extra="forbid"` → hard validation failure | `schema.AssistantResponse` |
| **Invented tool** | Tool name is an enum; a hallucinated name fails validation before reaching the router | `schema.ToolName` |
| **Hallucinated tool request acted on** | Routing authority is the validated intent, never the model's `tool_call` field | `pipeline._handle_tool` |
| **Irreversible action on a prediction** | `block_card` is marked `destructive`; never auto-executed. Pipeline escalates for explicit customer confirmation, and the refusal holds even at confidence 1.0 | `tools.ToolSpec.destructive`, `pipeline._handle_tool` |
| **Overconfident wrong answer** | Confidence below 0.55 → escalate, and tool execution is suppressed | `pipeline._apply_confidence_gate` |
| **Model asks the customer for credentials** | Reply screened for credential solicitation. A match **withholds the reply**, substitutes a warning that we never ask for secrets, and escalates — it is not merely counted | `safety.scan_reply`, `pipeline._apply_safety_screen` |
| **Simulated data mistaken for real** | Mandatory disclaimer on every customer-facing reply, including the failure path | `config.SAFETY_DISCLAIMER`, `pipeline._compose` |
| **Real financial data exposure** | BANKING77 is public; all tools simulated; all IDs synthetic (`CARD_SIM_0001`, `ACC_SIM_0001`) | `tools.py`, `pipeline._fill_missing_args` |
| **Silent failure** | Unparseable output after repair → escalate with a stated reason, plus a safe fallback reply | `pipeline.run` |

The destructive-tool refusal is the control worth leading with in the demo. An LLM's intent prediction must not be the sole authority for blocking a customer's card. `auto_execute_destructive` defaults to `False`, and a mutation check confirmed that flipping `block_card` to non-destructive fails four tests immediately.

---

## 9. Verification

Standard-library `unittest`, not pytest, so the suite runs on a stock interpreter plus pydantic with no extra dependency.

```
python -m unittest discover -s tests -t . -v
```

```
Ran 353 tests
OK (skipped=6)
```

The suite grew from 195 to **353** as each share merged: Satya's E2/E3/E6 work +79, Vishruth's data and model loading +37 (including the 6 real-GPT-2 tests skipped unless `SAFEBANK_MODEL_TESTS=1`), and the review fixes plus the safety screen +42.

The experiment runner and its notebook add **45** more in `test_experiments.py`, taking the suite to **398** (392 run offline, the same 6 gated).

Running the full suite needs **pydantic**; `scikit-learn` is additionally required only for the macro-F1 assertions, and `numpy`/`pandas` for the results DataFrame. Those three stay out of module scope — the heavy imports in `evaluate.py` live inside the functions that use them, so `import safebank` never pulls them in at import time. The model stack (torch, transformers, datasets) is needed only in Colab for the real E1/E7 runs; Vishruth pins the complete set in `requirements.txt`.

| Module | Tests | Covers |
|---|---|---|
| `test_schema.py` | 35 | E4: JSON extraction edge cases, all 4 failure kinds, repair prompt |
| `test_tools.py` | 38 | E5: 3 tools, argument validation, determinism, routing, spec export |
| `test_pipeline.py` | 55 | E7: happy path, repair-retry, confidence gate, destructive refusal, hallucination guards, safety screen, `prompt_kwargs` passthrough, `to_row()` contract |
| `test_safety.py` | 24 | R13: credential solicitation including the observed PIN reply, negations, word boundaries, invented account facts |
| `test_generator.py` | 22 | seam: `DecodeConfig` per-strategy kwargs, protocol conformance, fake |
| `test_intents.py` | 21 | label-space structure, confusable pairs, validation guard |
| `test_prompts.py` | 59 | E2: all 4 variants, shared-block reuse across variants, dispatch |
| `test_decoding.py` | 23 | E3: 6-config grid, per-strategy kwargs, seed self-consistency set |
| `test_evaluate.py` | 39 | E6: 6 metrics, destructive-refusal routing credit, failure taxonomy, confusable pairs, pipeline rows |
| `test_experiments.py` | 45 | E2/E3/E6 runner: batching and cache hits/misses, repair fall-through, few-shot bank forwarding and train/eval overlap guard, E3 subset and seed stability, failure-case spread, persistence |
| `test_data_prep.py` | 24 | label space, 385-row stratified sample and its determinism, example bank (train origin, routing coverage, `exclude=`), preprocessing record |
| `test_model_loader.py` | 13 | `HFGenerator` contract offline (7); real GPT-2 behaviour — no prompt echo, deterministic greedy, reproducible sampling (6, gated) |

**Label-space check — CLOSED.** The 20 `FOCUS_INTENTS` names were, for most of the project, verified only for structure (20 unique, 5 themes × 4, all confusable-pair members present) and not against the real dataset, because the model stack is Colab-only. `intents.validate_label_space()` has now been run against the real label space and **passes**: 77 intents, train/test splits of 10,003 / 3,080, the 385-row eval sample covering every intent, and 35–187 train rows per intent. No name was misspelled, so the E6 analysis describes intents that were actually evaluated.

**Verified against real models.** GPT-2: no prompt echo, greedy decoding deterministic, seeded sampling reproducible, batched output identical to single, overlong prompts truncated rather than crashing. Qwen2.5-1.5B through the full pipeline: valid JSON on the first attempt, ~750 prompt tokens, `block_card` correctly escalated instead of executing.

**Remaining verification gap.** The notebook is committed without stored outputs, so E1, the reproducibility appendix and the Colab packaging are not yet evidenced. One clean Colab run closes all three.

**Beyond the green bar.** Two checks were run because a passing suite proves little on its own. A *mutation check* flipped `block_card.destructive` to `False` in memory and confirmed four tests fail — the Requirement 13 control is genuinely guarded, not merely asserted. A *routing-metric check* confirmed an all-correct run now scores `routing_accuracy 1.0` with `n_correctly_withheld 3`, and that four adversarial cases (non-destructive withheld, destructive without escalation, destructive executed under opt-in, wrong tool) are all still classified correctly — so the destructive exemption cannot mask a genuinely dropped tool call.

---

## 10. Deviations from PROJECT_PLAN.md

The plan predates the code and is stale in three places. The code is correct; the plan needs updating before Bhavani assembles the report.

| Item | PROJECT_PLAN.md | Code | Why the code is right |
|---|---|---|---|
| Intent scope | "curated 20 of 77" | full 77 kept (`EXPECTED_N_INTENTS = 77`) | Fine-grained 77-way classification is the defining characteristic of BANKING77; narrowing it weakens the dataset analysis. The 20 survive as `FOCUS_INTENTS` for E6 failure analysis only. |
| Eval set | 200 rows | 5 × 77 = **385** rows (`EVAL_EXAMPLES_PER_INTENT = 5`) | Stratified across the full label space, so every intent is represented. |
| Intent name | `card_lost_or_stolen` | `lost_or_stolen_card` | The plan's name is not a real BANKING77 label. |
| `block_card` output | `replacement_eta` | `replacement_eta_days` | Unit made explicit. |
| Tool triggers | 6 intents listed | 10 intents mapped | `order_physical_card`, `getting_spare_card`, `card_swallowed`, `declined_cash_withdrawal` added. |

385 rows × 4 prompt variants × 6 decoding configs is substantially more inference than the plan assumed. That lands on Colab T4 time and should be sized before E2 starts.

---

## 11. Handoff

**Frozen interfaces** — these are stable; build against them.

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
SafeBankPipeline(generator, allowed_intents, strategy=…, prompt_kwargs=…).run(query, decode) -> PipelineResult
PipelineResult.to_row() -> dict
```

`to_row()` keys: `query`, `ok`, `intent`, `confidence`, `response`, `attempts`, `needed_repair`, `first_failure`, `tool`, `tool_ok`, `escalated`, `safety_issues`, `reply_withheld`, `latency_ms`. `response` is the model's own reply, deliberately not the composed `final_text` — evaluation criterion 4 screens what the model wrote, and `final_text` additionally carries the application-added system-lookup trace and disclaimer, which would be false positives.

**✅ Satya (E2, E3, E6) — delivered and merged.** All four `PromptStrategy` members are implemented, and all four render the intent catalogue, tool catalogue and schema contract through the shared formatters, so an E2 accuracy delta is attributable to the strategy rather than to wording drift. `decoding.py` builds the six-config grid on top of the existing `DecodeConfig` without redefining it, and `seed_variations()` returns a single config for greedy rather than implying variability that deterministic decoding cannot have. `evaluate.py` implements all six criteria over `PipelineResult.to_row()`, with numpy, pandas and scikit-learn imported inside the functions that need them.

One review finding is worth recording here because it generalises: the first revision of `evaluate.tool_routing()` scored the pipeline's destructive-tool refusal as a routing *miss*, because it compared the expected tool against the tool actually invoked and the pipeline correctly invokes none. A run with 100% intent accuracy reported 25% routing accuracy. The fix adds an `n_correctly_withheld` category keyed off `TOOL_REGISTRY[tool].destructive`. **Any new metric must be checked against the destructive-refusal path**, or it will report a working safety control as a defect.

✅ Done 26 Oct: `evaluate.response_safety()` reads `to_row()['response']`, and `flag_unsafe_responses` now delegates to `safety.scan_reply`, so E6 reports exactly what the pipeline enforced.

**✅ Vishruth (E1, environment) — delivered and merged (PR #2).** `HFGenerator` satisfies the protocol and returns the completion only (left padding, then a slice at the input width). Every sampling knob Qwen ships is reset to neutral before a `DecodeConfig` is applied. `data_prep` reads the official CSVs, checks the published split sizes and calls `validate_label_space()`, which passes on the real 77 labels. Still owed: the notebook run with stored outputs, a warning when `build_example_bank` gets no `exclude=`, and a content hash for the downloaded CSVs.

**Environment — decided.** Model work runs in Colab; the application layer and the test suite run locally. The blocker is no longer a decision but the run itself: E1, E2, E3, E6 and the real E7 all wait on one Colab session.

---

## 12. LLM architecture and autoregressive generation (report §4b)

Source for report §4b (Requirement 4). Every architecture figure here was checked on 28 Oct 2026 against the published `config.json`, `generation_config.json` and `tokenizer_config.json` of both checkpoints. Parameter counts were computed from those configs; for Qwen they match the model card exactly (1.54 B total, 1.31 B non-embedding). The worked tokenizer example in §12.8 is pasted in from the notebook once it has run.

### 12.1 What the model computes

Both checkpoints are decoder-only causal language models. Given the tokens so far, the model outputs a probability distribution over the next token, and the probability of a whole sequence factorises into those conditionals:

$$p(x_1,\dots,x_T) = \prod_{t=1}^{T} p\left(x_t \mid x_{<t}\right)$$

Pretraining fits this by minimising next-token cross-entropy over a large corpus; instruction tuning continues with the same objective on prompt-and-response pairs. We use pretrained checkpoints only and train nothing (Section 8 of the brief). Everything SafeBank Assist does — classify, reply, request a tool, emit JSON — is this one next-token prediction applied repeatedly.

### 12.2 The two checkpoints

| | `gpt2` — E1 baseline | `Qwen2.5-1.5B-Instruct` — final system |
|---|---|---|
| Parameters | 124.4 M | 1.54 B (1.31 B excluding embeddings) |
| Decoder blocks | 12 | 28 |
| Hidden size *d* | 768 | 1,536 |
| Attention heads | 12, each with its own keys and values | 12 query heads sharing **2** key/value heads (grouped-query attention) |
| Head dimension | 64 | 128 |
| Feed-forward | 768 → 3,072 → 768, GELU | 1,536 → 8,960 → 1,536, SwiGLU |
| Normalisation | LayerNorm | RMSNorm |
| Positions | learned absolute embeddings, **1,024** slots | rotary embeddings (RoPE, θ = 10⁶), 32,768 positions |
| Tokenizer | byte-level BPE, 50,257 tokens | byte-level BPE, 151,643 tokens + 22 special |
| Output head | tied to the input embeddings | tied to the input embeddings |
| Instruction-tuned / chat format | no / none | yes / ChatML (`<\|im_start\|>` … `<\|im_end\|>`) |
| Weights in fp16 | ≈ 0.25 GB | ≈ 3.1 GB |

### 12.3 From text to vectors

**Tokenization.** Both tokenizers use byte-level byte-pair encoding: text is broken into UTF-8 bytes and frequent byte sequences are merged into single tokens. Because every byte has a token, any input is representable — a misspelt, informal BANKING77 query never fails as out-of-vocabulary; a rare word simply becomes more pieces. A larger vocabulary buys shorter sequences at the price of a bigger embedding matrix: Qwen's alone holds 233 M parameters, 15 % of the model.

Token counts drive three practical constraints in this project:

- **Cost and latency (criterion 5).** Each request re-processes the whole prompt. The measured Qwen prompt is about 750 tokens, mostly the 77-label catalogue, against at most 192 generated tokens (`config.MAX_NEW_TOKENS`).
- **Context length.** GPT-2 has exactly 1,024 learned position embeddings; there is no vector for position 1,025. The few-shot prompt runs to about 1,600 tokens, so GPT-2 only ever sees a truncated version of it.
- **The chat template.** For Qwen the prompt is wrapped in ChatML role markers before tokenization. When no system message is supplied, Qwen's template inserts a default one — *"You are Qwen, created by Alibaba Cloud. You are a helpful assistant."* — and our generator sends a single user message, so every Qwen prompt carries that hidden system turn. It is identical across all four E2 variants, so comparisons between variants stay fair, but the role-context variant's persona sits in the user turn under a generic system persona, and report §7 should say so. GPT-2 has no template and receives the raw text.

**Embeddings.** Each token id selects one row of the embedding matrix *E* (vocabulary × *d*), giving 1,536 numbers per token for Qwen and 768 for GPT-2. The two models encode position differently. GPT-2 adds a learned vector for each absolute position. Qwen rotates every query and key vector by an angle proportional to its position (RoPE), which makes attention scores depend on the *relative* distance between two tokens and removes the fixed-size position table.

### 12.4 Inside a decoder block

The embedded sequence passes through the stack of identical blocks. Each block normalises its input, applies masked multi-head self-attention, adds the result back to its input (a residual connection), then normalises again and applies a feed-forward network, again with a residual.

**Self-attention** is where tokens exchange information. Every position is projected into a query *q*, a key *k* and a value *v*. For one head:

$$\mathrm{Attention}(Q,K,V) = \mathrm{softmax}\left(\frac{QK^{\top}}{\sqrt{d_k}} + M\right)V$$

Dividing by √*d_k* (√128 for Qwen) keeps the dot products in a range where the softmax does not saturate. *M* is what makes the model **causal**: it is 0 on and below the diagonal and −∞ above it, so position *t* can attend only to positions ≤ *t*. That mask is why generation can run left to right — the model was never trained to use tokens it will not have yet. Several heads run in parallel with their own projections, so each can attend to a different part of the context.

**Grouped-query attention and the KV cache.** During generation the keys and values of all earlier tokens are cached, so each new token adds only one position. Qwen's 12 query heads share 2 key/value heads, which shrinks that cache six-fold: 28,672 bytes per token in fp16 instead of 172,032. Qwen's per-token cache is therefore *smaller* than GPT-2's (36,864 bytes, one key/value pair per head) even though the model is twelve times larger. A 1,000-token request needs about 29 MB of cache, which is why batched generation fits comfortably on a T4.

**Feed-forward.** GPT-2 uses a two-layer MLP with GELU; Qwen uses SwiGLU, a gated variant with three projections. The feed-forward layers hold most of the weights — 41.3 M of each Qwen block's 46.8 M parameters.

### 12.5 From the last hidden state to the next token

After the final block, the hidden state at the last position, *h_t*, is mapped to one score (logit) per vocabulary entry and normalised into probabilities:

$$z = W h_t, \qquad p(x_{t+1} = i \mid x_{\le t}) = \frac{e^{z_i}}{\sum_j e^{z_j}}$$

Both models tie *W* to the embedding matrix *E*: the matrix that reads tokens in also writes them out, which on Qwen saves 233 M parameters. Qwen's matrix has 151,936 rows for 151,665 defined tokens; the surplus rows are padding.

### 12.6 Autoregressive generation and decoding

Generation is a loop. The whole prompt is processed once (the *prefill*), producing a distribution for the first new token; one token is chosen, appended and fed back, and the loop repeats until the model emits an end-of-sequence token or reaches 192 new tokens. Thanks to the KV cache, each step after the prefill costs one position of computation.

*How* a token is chosen from *p* is not part of the model. It is the decoding rule, and it is what E3 varies (report §8):

- **Greedy** takes the most probable token. Deterministic: the same prompt always gives the same output.
- **Temperature** divides the logits by *T* before the softmax. *T* < 1 sharpens the distribution, *T* > 1 flattens it.
- **Top-k** samples only among the *k* most probable tokens.
- **Top-p (nucleus)** samples from the smallest set of tokens whose probabilities sum to at least *p*, so the candidate set shrinks when the model is confident and grows when it is not.

Because the rule sits outside the model, a checkpoint can ship its own. Qwen2.5-1.5B-Instruct's published `generation_config.json` sets `do_sample=True, temperature=0.7, top_k=20, top_p=0.8, repetition_penalty=1.1`. Left in place, sampling would be on by default and a "temperature only" E3 run would also apply top-k, top-p and a repetition penalty. `model_loader` resets every one of these to neutral before applying a `DecodeConfig`, so each E3 configuration means exactly what its label says.

### 12.7 What the architecture explains about our design

1. **The model writes JSON one token at a time and has no notion of validity.** Nothing in the softmax prevents a trailing comma or a missing brace, so structure is enforced after generation: extraction, schema validation and repair-retry (§5 above).
2. **An intent label is just a token sequence.** The model can produce a plausible label that does not exist as easily as a real one, so every label is checked against the dataset's 77 names (`UNKNOWN_INTENT`). Constrained decoding — masking the logits so only valid labels or valid JSON can be produced — would enforce this during generation. We validate afterwards instead: simpler, at the cost of a retry when the model strays.
3. **`confidence` is generated text, not a probability.** The model's real uncertainty is the softmax in §12.5; the number it writes in `"confidence": 0.82` is itself generated digits. It works as an escalation signal, but it is not calibrated and the report must not present it as a probability. A score derived from the logits of the predicted label would be the principled alternative (report §13).
4. **Every request pays for the whole catalogue.** Prefill cost grows with prompt length, and the 77-label catalogue dominates the ~750-token prompt. That is the strongest practical argument for the PEFT alternative in §7 above: a fine-tuned model would not need the catalogue in its prompt.
5. **The context window limits the baseline.** GPT-2 cannot see a whole few-shot prompt, so its few-shot numbers partly measure truncation rather than capability (report §13).
6. **Sampling makes outputs vary between runs.** Under any non-greedy rule the same query can receive a different label on a different seed, which is why E3 measures self-consistency across seeds as well as accuracy.

### 12.8 Worked example — paste from notebook §4

Notebook §4, "Tokenization walkthrough", prints the token ids and vocabulary pieces for the first evaluation query, then the model's vocabulary size, hidden size, layer count, head count and context length. Paste that output below once the notebook has run on Colab. Expected: hidden size 1536, layers 28, heads 12 (query heads only), context 32768, and a vocabulary size of 151,643 (the base BPE vocabulary, without the 22 special tokens). Anything else means the wrong checkpoint was loaded.

```
[paste notebook §4 output here]
```
