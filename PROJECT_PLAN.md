# PCAM ZG516 – Applied Generative AI
# Group Major Project / Assignment–1 — Group 22 Project Plan

| | |
|---|---|
| **Course** | PCAM* ZG516 – Applied Generative AI (S2-25_PCAMZG516) |
| **Coverage** | CS1–CS5 + ELS 1 |
| **Group** | 22 |
| **Members** | Nandhaluru Kishore, Vishruth M, Satya Prakash, Takkars Bhavani |
| **Dataset** | D1 – BANKING77 *(confirmed by instructor)* |
| **Maximum Marks** | 20 |
| **Due** | Saturday, 31 October 2026, 11:59 PM *(extended from 25 Oct)* |
| **Submission** | Portal → Assignment 1 → Add submission |

---

> ## ⚠️ Read `WORKLOG.md` first
>
> **This plan was written on 15 Oct, before any code existed. [`WORKLOG.md`](WORKLOG.md) is the live status document and wins wherever the two disagree.**
>
> Corrected in this file on 25 Oct to match the implementation: the eval set is **385 rows across all 77 intents** (not 200 rows across 20), the intent name is `lost_or_stolen_card` (not `card_lost_or_stolen`), `block_card` returns `replacement_eta_days`, and **10** intents route to a tool (not 6).
>
> Current state: application code ~90% done, **experiment results 0%**, report ~5%. See `WORKLOG.md` §1.

---

## 1. The Application We Are Building

**Name:** SafeBank Assist — a first-line banking support triage assistant.

**Target user:** Tier-1 customer support agent at a retail bank (and, by extension, the end customer through a self-service channel).

**Problem:** Incoming customer messages are free-text and ambiguous. A human agent must read each one, work out what the customer actually wants out of 77 possible request types, decide whether a system lookup is needed, and reply safely without inventing account facts. This is slow and inconsistent.

**Input:** one free-text customer query (e.g. *"My new card hasn't arrived yet, it's been two weeks"*).

**Output:** a validated JSON object carrying the predicted intent, a confidence value, a safe customer-facing reply, an optional tool call, and an escalation flag.

**Why a generative LLM is the right choice:** a plain classifier gives a label but no reply, no reasoning and no routing decision. A causal LM does intent understanding, natural-language response generation, structured-output emission and tool-call selection in a single prompted pass, and adapts to new intents without retraining.

### Pipeline (satisfies Section 5 — Minimum Technical Workflow)

```
customer query
  → preprocessing / sample selection
  → programmatic prompt template
  → tokenizer
  → pretrained causal LLM (autoregressive generation)
  → decoding control (greedy | temperature | top-k | top-p)
  → raw completion
  → JSON parse + schema validation (repair-retry on failure)
  → intent + confidence
  → tool router → simulated tool execution → tool result
  → final composed response + safety disclaimer
  → evaluation: baseline vs improved system
```

### Technical choices

| Item | Choice | Reason |
|---|---|---|
| Model | `Qwen2.5-1.5B-Instruct` | Causal LM, instruction-tuned, ~3 GB fp16, fits a free Colab T4 |
| Naive baseline | `gpt-2` | Deliberately weak, makes E1→E2 improvement visible |
| Schema validation | `pydantic` v2 | Only dependency of the application layer; no model runtime needed to test it |
| Intent scope | **All 77 intents** kept in the label space (`config.EXPECTED_N_INTENTS = 77`) | *Corrected 25 Oct.* Fine-grained 77-way classification is the defining characteristic of BANKING77; narrowing it would weaken the dataset analysis. The curated 20 survive as `intents.FOCUS_INTENTS`, used only for the E6 failure analysis. |
| Eval set | **385 rows** = 5 per intent × 77, stratified, `seed=42` (`config.EVAL_EXAMPLES_PER_INTENT = 5`) | *Corrected 25 Oct (was 200).* Every intent represented. Note the inference cost: see `WORKLOG.md` §5 for the budget and the agreed scope cut for E3. |
| Tools | 3 simulated functions | No real banking data or credentials (Section 8 compliance) |

### Output schema

```json
{
  "intent": "card_arrival",
  "confidence": 0.82,
  "response": "I can see your card was dispatched. Let me check the delivery status for you.",
  "tool_call": { "name": "check_card_delivery_status", "args": { "card_id": "CARD_0417" } },
  "requires_human": false,
  "disclaimer": "Information shown is from a simulated system of record."
}
```

### Simulated tools (Requirement 10)

| Tool | Input schema | Output schema | Triggering intents |
|---|---|---|---|
| `check_card_delivery_status` | `{card_id: str}` | `{status, dispatched_on, eta_days}` | `card_arrival`, `card_delivery_estimate`, `order_physical_card`, `getting_spare_card` |
| `block_card` **(destructive)** | `{account_id: str, reason: enum}` | `{blocked: bool, ref_id, replacement_eta_days}` | `lost_or_stolen_card`, `compromised_card`, `card_swallowed` |
| `find_branch` | `{pincode: str, service: enum}` | `{branch_name, address, distance_km}` | `atm_support`, `cash_withdrawal_charge`, `declined_cash_withdrawal` |

*Corrected 25 Oct:* **10** intents route to a tool, not 6. The intent name is `lost_or_stolen_card` (the plan's original `card_lost_or_stolen` is not a real BANKING77 label), and `block_card` returns `replacement_eta_days`. `block_card` is flagged `destructive` and is **never auto-executed** — the pipeline escalates for explicit customer confirmation. The other 67 intents are answered with text only. See `tools.INTENT_TO_TOOL`.

---

## 2. Mark-by-Mark Coverage Map (Section 11 Rubric)

| # | Rubric component | Marks | How we earn it | Owner |
|---|---|---|---|---|
| 1 | Problem + dataset analysis | **2** | Section 1 above + BANKING77 field analysis, class distribution plot, stratified sampling record, preprocessing log | Vishruth (data) + Bhavani (write-up) |
| 2 | LLM / generative-model understanding | **3** | Comparison of ≥3 model families (GAN, VAE, diffusion vs autoregressive) + tokenization → embeddings → attention → LM head → autoregressive decoding, illustrated with our real tokenizer output + decoding study | Kishore (architecture) + Satya (families, decoding) |
| 3 | Prompt engineering | **3** | 4 prompt variants (zero-shot, few-shot, role/context, constraint-based) with an accuracy comparison table + design rationale for each | Satya |
| 4 | Adaptation strategy | **2** | Prompting vs RAG vs PEFT argued from our measured numbers; justify prompting + constrained decoding; state when RAG/PEFT would win | Kishore |
| 5 | Structured output + tool calling | **3** | Pydantic schema, validity-rate metric, repair-retry logic, 3 tool schemas, live invocation trace | Kishore |
| 6 | Implementation | **3** | Clean modular code, Colab notebook running top-to-bottom, frozen seeds, pinned `requirements.txt` | Vishruth (env, reproducibility) + Kishore (pipeline) |
| 7 | Evaluation + failure analysis | **2** | 6 metrics (below) + baseline vs final comparison + ≥3 analysed failure cases with root causes | Satya |
| 8 | Report + demo + contribution | **2** | 10–15 page report on the prescribed 14-section structure, 8–10 min demo with all 4 speaking, signed contribution statement | Bhavani (assembly) + all (demo) |

**Evaluation criteria (Requirement 12 needs ≥4; we use 6):**
1. Intent accuracy (top-1) and macro-F1
2. JSON schema validity rate
3. Tool-routing correctness
4. Response safety — no invented account facts (rubric-scored)
5. Latency and tokens per response
6. Output stability across decoding settings (self-consistency)

---

## 3. Requirement Checklist (Section 4 — all 13)

| Req | What it demands | Where it lands | Owner |
|---|---|---|---|
| 1 | Problem definition | Report §2 | Kishore |
| 2 | Dataset understanding | Report §3 | Vishruth → Bhavani |
| 3 | ≥3 generative model families compared | Report §4a | Satya |
| 4 | LLM architecture + autoregressive generation | Report §4b | Kishore |
| 5 | Baseline with pretrained HF causal LM | E1, Report §6 | Vishruth |
| 6 | Zero-shot / few-shot / role / constraint prompts | E2, Report §7 | Satya |
| 7 | Greedy vs temperature vs top-k/top-p | E3, Report §8 | Satya |
| 8 | Prompting vs RAG vs fine-tuning/PEFT | Report §9 | Kishore |
| 9 | Machine-readable output schema | E4, Report §10a | Kishore |
| 10 | ≥1 tool/function with I/O schema + invocation | E5, Report §10b | Kishore |
| 11 | Reusable parameterized prompt template | `prompts.py`, Report §7 | Satya |
| 12 | ≥4 evaluation criteria + failure analysis | E6, Report §11–12 | Satya |
| 13 | Hallucination / misuse / privacy / reliability controls | Report §12 | Kishore → Bhavani |

## 4. Experiment Checklist (Section 6 — E1 to E7)

| Exp | Minimum requirement | Our evidence | Owner |
|---|---|---|---|
| E1 | One simple prompt, ≥3 outputs | 5 outputs, GPT-2 vs Qwen side by side | Vishruth |
| E2 | ≥4 prompt variants | 4 variants × 200 eval rows, accuracy table | Satya |
| E3 | Greedy + temperature + top-k/top-p | 6-config grid, 3 sample outputs each, variability analysis | Satya |
| E4 | One schema + validation | Pydantic schema, validity rate before/after repair-retry | Kishore |
| E5 | ≥1 function | 3 tools, schemas, full invocation trace | Kishore |
| E6 | ≥3 failure cases | 6 cases across 4 failure classes, root-cause table | Satya |
| E7 | Integrated workflow | End-to-end notebook demo | Kishore |

## 5. Deliverables Checklist (Section 9 — all 10)

*Status as of 25 Oct. Live version in `WORKLOG.md` §1.*

- [ ] Technical report, 10–15 pages excl. appendix — *Bhavani assembles, all write* — **not started.** §1/§5/§10/§12 source material is already written in `ARCHITECTURE.md` and needs only formatting; start there without waiting for results
- [ ] Working Colab notebook — *Vishruth packages* — **not started**
- [ ] Dataset description + preprocessing record — *Vishruth → Bhavani* — **not started**, blocked on `data_prep.py`
- [ ] Prompt experiment log (baseline + improved) — *Satya* — **code merged (4/4 variants, 59 tests), no results yet**
- [ ] Decoding comparison table — *Satya* — **6-config grid merged (`decoding.py`, 23 tests), no results yet**
- [x] Structured-output schema + validated samples — *Kishore* — **DONE.** `schema.py` merged, 35 tests, `response_json_schema()` exports for the appendix
- [x] Tool/function spec + demonstration — *Kishore* — **DONE.** `tools.py` merged, 38 tests, `tool_specs_json()` exports all 3 contracts
- [ ] Evaluation + failure-analysis table — *Satya* — **all 6 metrics merged (`evaluate.py`, 39 tests, review blocker fixed), no results yet**
- [ ] 8–10 min group demonstration — *all 4 speak* — **not started, not rehearsed**
- [ ] Individual contribution statement, signed by every member — *Bhavani collects* — **not started.** Git commit history is usable as supporting evidence

---

## 6. Work Division

### Kishore — Solution Architect & Application  *(heaviest: design + core code)*

**Owns the architecture and the application itself.**

Code:
- `schema.py` — pydantic models (`AssistantResponse`, `ToolCall`), validation + repair-retry
- `tools.py` — the 3 simulated tools, their I/O schemas, the tool router
- `pipeline.py` — the end-to-end orchestrator tying prompt → model → decode → validate → route → respond
- E4, E5, E7 integration

Writing:
- Report §2 Problem statement & motivation
- Report §4b LLM architecture (tokenization, embeddings, attention, LM head, autoregressive generation)
- Report §5 Proposed application architecture + the pipeline diagram
- Report §9 Adaptation strategy: prompting vs RAG vs PEFT
- Report §10 Structured output and tool calling
- Report §12 Responsible-use controls

Rubric ownership: components 4, 5, half of 2, half of 6 → **~8 marks**

### Satya Prakash — Experiments & Evaluation Lead *(heavy: logic + code)*

**Owns everything measured.**

Code:
- `prompts.py` — 4 reusable parameterized prompt templates
- `decoding.py` — the decoding configuration grid
- `evaluate.py` — all 6 metrics, confusion analysis, comparison tables
- E2, E3, E6

Writing:
- Report §4a Generative-model family comparison (GAN / VAE / diffusion / autoregressive)
- Report §7 Prompt-engineering experiments + why each prompt was designed that way
- Report §8 Decoding experiments
- Report §11 Evaluation and results
- Report §13 Limitations

Rubric ownership: components 3, 7, half of 2 → **~6.5 marks**

### Vishruth M — Framework, Environment & Reproducibility

**Owns everything to do with dependencies and making it run anywhere.** No conceptual writing load.

- Environment setup: `requirements.txt` with pinned versions, Colab runtime for the model stack
- Confirm the Colab GPU is usable for the chosen model; record `torch.cuda.get_device_capability()`
- Model + tokenizer loading, device placement, caching (`model_loader.py`)
- `data_prep.py` — BANKING77 load, full 77-intent label space read from the dataset, stratified **385-row** sample (5 per intent), seed freeze, mandatory `validate_label_space()` call *(corrected 25 Oct; see `WORKLOG.md` §5.1 for the full spec)*
- E1 baseline implementation
- Colab packaging: pip-install cell, clean top-to-bottom run on free T4
- Reproducibility appendix (versions, seeds, hardware)
- Report §3 Dataset description + preparation (raw material; Bhavani polishes), §6 Baseline implementation

Rubric ownership: component 1 (data half), half of 6 → **~3 marks**

### Takkars Bhavani — Report Assembly & Submission *(light load, no coding, no environment)*

- Report §1 Abstract and §14 Conclusion and future work (short sections)
- Polish Report §3 dataset description from Vishruth's output; build the representative-examples table
- Assemble all sections into the BITS WILP template, apply formatting, page numbering, keep it inside 10–15 pages
- References and Appendix assembly (prompts, schemas, output samples)
- Collect and compile the individual contribution statement; chase all 4 signatures
- Final proofread for Section 8 "What Students Should NOT Do" compliance
- Upload the submission on the portal before the deadline

Rubric ownership: component 8 (assembly half) → **~1 mark**

### Demo speaking split (8–10 min, every member must be able to explain the whole workflow)

| Minutes | Segment | Speaker |
|---|---|---|
| 0:00–1:30 | Problem, user, why an LLM | Bhavani |
| 1:30–3:00 | Dataset, preprocessing, baseline setup | Vishruth |
| 3:00–5:00 | Prompt engineering + decoding results | Satya |
| 5:00–7:30 | Architecture, structured output, live tool call | Kishore |
| 7:30–9:00 | Evaluation, failures, responsible use | Satya + Kishore |
| 9:00–10:00 | Limitations, future work, Q&A | all |

---

## 7. Timeline

> **Superseded.** The table below is the original 15 Oct plan and is kept only as a record of intent. The deadline moved to **31 Oct** and the actual schedule is in **`WORKLOG.md` §2**, which also carries the Monday 26 Oct escalation trigger for the environment work.
>
> What actually happened versus this plan: the environment and dataset work (rows 2–4 below) **did not start**, so E1 never ran. The architecture, schema, tools and pipeline work landed on 23 Oct, and E2/E3/E6 code landed 25 Oct in PR #1. Nothing has run against a real model yet.

### Original plan (15 Oct, superseded)

| Dates | Milestone | Owner |
|---|---|---|
| 15–16 Oct | Architecture frozen, schema + tool specs agreed | Kishore |
| 15–16 Oct | Environment decision (local venv vs Colab), stack installed, CUDA verified | Vishruth |
| 17 Oct | Dataset loaded, 20-intent subset curated, 200-row eval set frozen | Vishruth |
| 17–18 Oct | E1 baseline complete | Vishruth |
| 18–20 Oct | E2 prompts + E3 decoding complete | Satya |
| 18–20 Oct | E4 schema + E5 tools complete | Kishore |
| 21 Oct | E7 integrated pipeline running | Kishore |
| 21–22 Oct | E6 evaluation + failure analysis complete | Satya |
| 22–23 Oct | All report sections drafted | all |
| 23–24 Oct | Report assembled, formatted, PDF generated | Bhavani |
| 24 Oct | Colab clean run verified; demo rehearsal | Vishruth + all |
| 25 Oct | Final review, signatures, **submit** (buffer day) | Bhavani |

**Critical path:** environment → data → E1 → E2/E3 → E7 → evaluation → report. Vishruth's environment work blocks everything, so it goes first.

---

## 8. Compliance Guardrails (Section 8 — What NOT to do)

| Rule | How we comply |
|---|---|
| No training an LLM from scratch | We only use pretrained HF checkpoints |
| No ChatGPT screenshots as evidence | All evidence is notebook output with code |
| No unexplained prompts | Every prompt variant carries a written design rationale |
| No accuracy claims without procedure | 200-row frozen eval set, documented metrics |
| No real personal/financial data | BANKING77 is public; all tools are simulated; IDs are synthetic |
| Don't treat generated text as correct | Failure analysis + confidence + escalation flag + disclaimer field |
| Don't make later modules mandatory | No diffusion or multimodal content |

## 9. Open Items

1. ~~**Dataset confirmation**~~ — **CLOSED.** D1 BANKING77 confirmed by the instructor. Group membership correction (Takkars Bhavani in place of Shruti Dubey) also acknowledged. SQuAD fallback no longer needed.
2. 🔴 **Environment decision — STILL OPEN, and now the critical path.** The local development environment provides `pydantic 2.13.4`, `numpy 2.5.2`, `pandas 2.3.3`, `scikit-learn 1.9.0`, `matplotlib`, `seaborn` and `scipy`, but **not** `torch`, `transformers`, `datasets` or `tokenizers`. A local model runtime is therefore not available. *Proposal: all model work in Colab; the application layer and tests stay local.* This blocks E1, E2, E3 and the real E7 run. See `WORKLOG.md` §5.3 for the dependency split.
3. **BITS IDs** for all 4 members, needed for the report title page.
4. **Lecture alignment** — Kishore/Satya to confirm the concept sections match the depth covered in CS1–CS3.
