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
| **Due** | Sunday, 25 October 2026, 11:59 PM |
| **Submission** | Portal → Assignment 1 → Add submission |

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
| Model | `Qwen2.5-1.5B-Instruct` | Causal LM, instruction-tuned, ~3 GB fp16, fits 8 GB VRAM and Colab T4 |
| Naive baseline | `gpt-2` | Deliberately weak, makes E1→E2 improvement visible |
| Schema validation | `pydantic` v2 | Already installed locally |
| Intent scope | Curated **20 of 77** intents across 5 themes | Keeps few-shot prompts tractable; deliberately includes confusable pairs for failure analysis. Scope decision documented in the report. |
| Eval set | 200 rows, stratified, `seed=42` | Reproducible; large enough for meaningful accuracy |
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
| `check_card_delivery_status` | `{card_id: str}` | `{status, dispatched_on, eta_days}` | card_arrival, card_delivery_estimate |
| `block_card` | `{account_id: str, reason: enum}` | `{blocked: bool, ref_id, replacement_eta}` | card_lost_or_stolen, compromised_card |
| `find_branch` | `{pincode: str, service: enum}` | `{branch_name, address, distance_km}` | atm_support, cash_withdrawal_charge |

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

- [ ] Technical report, 10–15 pages excl. appendix — *Bhavani assembles, all write*
- [ ] Working Colab notebook — *Vishruth packages*
- [ ] Dataset description + preprocessing record — *Vishruth → Bhavani*
- [ ] Prompt experiment log (baseline + improved) — *Satya*
- [ ] Decoding comparison table — *Satya*
- [ ] Structured-output schema + validated samples — *Kishore*
- [ ] Tool/function spec + demonstration — *Kishore*
- [ ] Evaluation + failure-analysis table — *Satya*
- [ ] 8–10 min group demonstration — *all 4 speak*
- [ ] Individual contribution statement, signed by every member — *Bhavani collects*

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

- Environment setup: `requirements.txt` with pinned versions, isolated venv or Colab runtime
- Resolve the Python 3.14 / Blackwell GPU CUDA question; confirm `torch.cuda.get_device_capability()`
- Model + tokenizer loading, device placement, caching (`model_loader.py`)
- `data_prep.py` — BANKING77 load, 20-intent curation, stratified 200-row sample, seed freeze
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

## 7. Timeline (today = 15 Oct, due 25 Oct)

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
2. **Environment decision** — local venv (faster iteration, 8 GB Blackwell GPU) vs Colab-only (zero local installs, matches grading environment). *Awaiting Kishore's approval; nothing installed yet.*
3. **BITS IDs** for all 4 members, needed for the report title page.
4. **Lecture alignment** — Kishore/Satya to confirm the concept sections match the depth covered in CS1–CS3.
