# SafeBank Assist — Solution Architecture

**PCAM ZG516 Applied Generative AI · Group Major Project / Assignment-1 · Group 22**

Author: Nandhaluru Kishore (Solution Architect & Application Lead)
Source material for report §2, §4b, §5, §9, §10 and §12.
Status as of 23 October 2026.

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
| `__init__.py` | Curated public API, 44 exports | — | Kishore | **Done** |
| `prompts.py` | 4 prompt strategies | **E2** | Kishore (seam + zero-shot) → Satya (3 variants) | **Done**, 4 of 4 implemented |
| `decoding.py` | Decoding grid | **E3** | Satya | **Done** |
| `evaluate.py` | 6 metrics, comparison, failure analysis | **E6** | Satya | **Done** |
| `data_prep.py` | BANKING77 load, stratified sample | — | Vishruth | Not started |
| `model_loader.py` | HF model + tokenizer loading | E1 | Vishruth | Not started |

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

1. **The application is testable with no model runtime.** Verified on this machine: Python 3.14.5 has pydantic 2.13.4, numpy, pandas and scikit-learn, but `torch`, `transformers`, `datasets` and `tokenizers` are all absent and must not be installed. The full 195-test suite still exercises the complete control flow via `FakeGenerator`.
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
| **Prompting + constrained decoding** | The label space is 77 fixed names that fit in context. The task is classification plus short generation, not knowledge recall. Zero training cost, and a new intent is a catalogue edit. | **Chosen** |
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
| **Simulated data mistaken for real** | Mandatory disclaimer on every customer-facing reply, including the failure path | `config.SAFETY_DISCLAIMER`, `pipeline._compose` |
| **Real financial data exposure** | BANKING77 is public; all tools simulated; all IDs synthetic (`CARD_SIM_0001`, `ACC_SIM_0001`) | `tools.py`, `pipeline._fill_missing_args` |
| **Silent failure** | Unparseable output after repair → escalate with a stated reason, plus a safe fallback reply | `pipeline.run` |

The destructive-tool refusal is the control worth leading with in the demo. An LLM's intent prediction must not be the sole authority for blocking a customer's card. `auto_execute_destructive` defaults to `False`, and a mutation check confirmed that flipping `block_card` to non-destructive fails four tests immediately.

---

## 9. Verification

Standard-library `unittest`. pytest is not installed on the development machine and must not be installed, so the suite runs on a stock interpreter plus pydantic.

```
python -m unittest discover -s tests -t . -v
```

```
Ran 274 tests in 3.1s
OK
```

Satya's E2/E3/E6 work took the suite from 195 to **274** — a net **+79**: the original 195 already included 42 prompt-seam tests in `test_prompts.py`, which grew to 59 (+17 as the three variants replaced the stub tests), plus a new `test_decoding.py` (23) and `test_evaluate.py` (39). Running the full suite and the application now needs **pydantic, numpy, pandas and scikit-learn** — the E6 evaluation metrics (macro-F1, the results DataFrame) added the latter three. They stay out of module scope: the heavy imports in `evaluate.py` live inside the functions that use them, following the same pattern as `model_loader.py`'s torch imports, so `import safebank` never pulls them in at import time. The model stack (torch, transformers, datasets) is still needed only in Colab for the real E1/E7 runs; Vishruth pins the complete set in `requirements.txt`.

| Module | Tests | Covers |
|---|---|---|
| `test_schema.py` | 35 | E4: JSON extraction edge cases, all 4 failure kinds, repair prompt |
| `test_tools.py` | 38 | E5: 3 tools, argument validation, determinism, routing, spec export |
| `test_pipeline.py` | 37 | E7: happy path, repair-retry, confidence gate, destructive refusal, hallucination guards |
| `test_generator.py` | 22 | seam: `DecodeConfig` per-strategy kwargs, protocol conformance, fake |
| `test_intents.py` | 21 | label-space structure, confusable pairs, validation guard |
| `test_prompts.py` | 59 | E2: all 4 variants, shared-block reuse across variants, dispatch |
| `test_decoding.py` | 23 | E3: 6-config grid, per-strategy kwargs, seed self-consistency set |
| `test_evaluate.py` | 39 | E6: 6 metrics, destructive-refusal routing credit, failure taxonomy, confusable pairs, pipeline rows |

**Known verification gap.** The 20 `FOCUS_INTENTS` names are checked for structure (20 unique, 5 themes × 4, all confusable-pair members present) but **not** against the real BANKING77 label space, because `datasets` is not installed. `intents.validate_label_space` will raise `LabelSpaceError` naming any mismatch the first time `data_prep.py` supplies the real labels. That check must be run before any number is quoted in the report.

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

# orchestration (E7)
SafeBankPipeline(generator, allowed_intents, strategy=…).run(query, decode) -> PipelineResult
PipelineResult.to_row() -> dict
```

**→ Satya (E2, E3, E6).** `prompts.PromptStrategy` has four members; `ZERO_SHOT` is implemented as the reference. `FEW_SHOT`, `ROLE_CONTEXT` and `CONSTRAINT_BASED` raise `NotImplementedError` with the intended signature, design rationale and implementation notes in their docstrings. Reuse `format_intent_catalogue`, `format_tool_catalogue` and `format_schema_contract` — if each variant hand-writes its own schema text, an E2 accuracy delta becomes unattributable to the strategy. `decoding.py` should build the grid on top of the existing `DecodeConfig` rather than redefining it. `evaluate.py` can consume `PipelineResult.to_row()` directly; scikit-learn 1.9.0 is already available locally for macro-F1 and confusion matrices.

The three stub tests in `test_prompts.py::TestPendingVariantsAreHonestlyAbsent` are expected to fail once a variant is implemented — replace them with real content assertions at that point.

**→ Vishruth (E1, environment).** `model_loader.HFGenerator` must satisfy `TextGenerator` structurally and return the completion **only**, with the prompt stripped; the pipeline feeds the result straight into `parse_response`, and a prompt echo would be scored as a model failure. Seed from `decode.seed` before every sampled generation and pass `**decode.to_generate_kwargs()`. Keep `import torch` inside function bodies so the package still imports on a machine without it. `data_prep.py` must call `intents.validate_label_space(labels)` on the loaded label space.

**Open decision, still blocking.** `torch`, `transformers` and `datasets` are absent and will not be installed on this machine (company laptop; Python 3.14.5 also predates stable wheels for them). E1, E2, E3 and the real E7 run therefore need Colab. The application layer and this test suite stay local. This is PROJECT_PLAN.md Open Item 2 and it now gates three of the four workstreams.
