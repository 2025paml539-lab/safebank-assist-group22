# SafeBank Assist — BANKING77 intent triage with a pretrained causal LLM

**PCAM\* ZG516 Applied Generative AI · Group Major Project / Assignment-1 · Group 22**
Dataset D1 — BANKING77 · Final model `Qwen2.5-1.5B-Instruct` · Baseline `gpt2` · Submitted 31 October 2026

| Member | BITS ID |
|---|---|
| Nandhaluru Kishore | 2025paml539 |
| Vishruth M | 2025paml536 |
| Satya Prakash | 2025paml561 |
| Takkars Bhavani | 2025paml562 |

---

## Start here

| What you want | Where it is |
|---|---|
| **The submitted documents** | **[`submission/`](submission/)** — report PDF, contribution statement, demo deck, both executed notebooks |
| **The demo video** | **[8–10 minute group demonstration](https://drive.google.com/file/d/1-Hq-l2G5sG9Ew2WHOgonSB35ubDcduhy/view?usp=sharing)** (Google Drive) |
| **The application code** | [`src/safebank/`](src/safebank/) |
| **The tests** | [`tests/`](tests/) — 398 tests; the command is below |
| **The experiment results** | [`artifacts/results/`](artifacts/results/) — every raw result row behind every number in the report |
| **The notebooks** | [`notebooks/`](notebooks/) — both committed with stored outputs |
| **The report source** | [`report/`](report/) — one file per section; `build_report.py` regenerates the PDF |
| **Technical detail** | [`ARCHITECTURE.md`](ARCHITECTURE.md) |
| **Who did what, and when** | [`WORKLOG.md`](WORKLOG.md) |

## What is in `submission/`

| File | What it is |
|---|---|
| `SafeBank_Assist_Group22_Report.pdf` | Technical report — 32 pages: title, 15 body pages covering sections 1–14, and 16 pages of references and appendices A–I |
| `SafeBank_Assist_Group22_Contribution_Statement.pdf` | Individual contribution statement, confirmed by name and date by all four members. Also printed as Appendix I of the report |
| `SafeBank_Assist_Group22_Demo.pptx` | Demo deck, 16:9, with speaker notes on every slide |
| `SafeBank_Assist_Group22_Notebook_1_Colab_T4_E1_E7.ipynb` | Executed notebook, stored outputs — E1 baseline (GPT-2 vs Qwen), tokenizer walkthrough, E7 integrated run, device report. Colab Tesla T4 |
| `SafeBank_Assist_Group22_Notebook_2_Experiments_E2_E3_E6.ipynb` | Executed notebook, stored outputs — E2 prompt experiments, E3 decoding grid, E6 evaluation and failure analysis. NVIDIA A100 80 GB |

Both notebooks keep their stored outputs, so every result can be read without running anything.

## What the application does

One free-text banking support message in; one validated decision out — the BANKING77 intent,
a confidence value, a customer-safe reply, an optional call to one of three simulated banking
tools, and an escalation flag. The model does the language work; deterministic code decides what
is shown: JSON schema validation with a repair-retry loop, a check that the label exists in
BANKING77, a reply-safety screen that withholds replies asking for credentials, a confidence
gate, and a rule that a card is never blocked without human confirmation.

```
message → prompt template → tokenizer → causal LLM → decoding control → raw text
        → JSON parse → schema validation → repair-retry (max 2)
        → label check → confidence gate → tool router → simulated tool
        → reply-safety screen → validated reply + disclaimer, or escalation with a reason
```

## Headline results

Measured on a frozen stratified sample of 385 messages, 5 per intent, seed 42, test split only.

| Result | Figure |
|---|---|
| Best prompt strategy | Few-shot — **47.8%** accuracy, **0.450** macro-F1 (zero-shot 40.3%, role/context 39.0%, constraint-based 40.0%) |
| Significance | Paired exact McNemar: few-shot vs zero-shot p = 0.002; the other three are indistinguishable (p 0.47–1.0) |
| Structured-output validity | 83.4% first attempt → **94.8%** after repair; 47 of 60 formatting failures rescued, only 1 of 62 invented labels |
| Decoding | Greedy best at **48.1%**; temperature 0.7 costs ~3 points, 1.2 costs 8.6; top-k 50 indistinguishable from plain temperature 0.7 |
| Reply safety | Replies flagged unsafe **17.4% → 3.9%**; 15 withheld and escalated, 9 of them asking for a secret |
| Tool routing | 68% of the 50 tool-triggering messages handled correctly; every miss followed a wrong intent |
| Tests | **398** pass, 6 skipped (real-model, gated on `SAFEBANK_MODEL_TESTS=1`) |

Two of the four prompt hypotheses did not hold, and both are reported: few-shot *lowered*
first-attempt validity (every violation was an invented tool name), and the role persona did not
make replies safer. The repair loop's near-total failure on invented labels is explained rather
than hidden — the retry prompt never re-states the valid label space.

## Run it yourself

The application layer and the whole test suite run with no GPU, no model download and no network:

```bash
python -m unittest discover -s tests -t .     # 398 tests, a few seconds
```

Expected: `Ran 398 tests ... OK (skipped=6)`. The 6 skipped tests load real GPT-2 weights and are
gated behind `SAFEBANK_MODEL_TESTS=1`.

See the whole pipeline run against a scripted generator, still with no model:

```bash
python -c "import sys; sys.path.insert(0,'src'); from safebank import *; p=SafeBankPipeline(FakeGenerator(), list(FOCUS_INTENTS)); print(p.run('my card has not arrived').final_text)"
```

Regenerate the submitted documents:

```bash
python report/build_report.py --final       # the report PDF; refuses to build if anything is pending
python report/build_contribution_pdf.py     # the contribution statement as a standalone PDF
python report/build_demo_deck.py            # the demo deck, every figure read from artifacts/results/
```

The model stack (`torch`, `transformers`, `datasets`) is needed only to re-run the experiments,
and those run in Colab or on a GPU server — see the notebooks.

## Reproducibility and honesty notes

- **Frozen evaluation set.** 385 messages, 5 per intent, seed 42, test split only. Few-shot
  examples come from the training split, and the experiment runner refuses to start if an example
  is also an evaluation message.
- **Two machines.** E1 and the integrated E7 trace ran on a free Colab Tesla T4 (float16, torch
  2.11.0+cu130). E2, E3 and E6 ran on an NVIDIA A100-SXM4-80GB (float16, torch 2.8.0+cu128),
  because the newer torch build needed a CUDA 13 driver the server did not have. Both records are
  in Appendix F. Comparisons within E2 and within E3 each come from one machine, and the
  evaluation sample was rebuilt on the second machine and confirmed identical.
- **No real data.** Public dataset, three simulated tools, synthetic identifiers only
  (`CARD_SIM_0001`, `ACC_SIM_0001`). No real personal or financial information anywhere.
- **Every number is traceable.** The raw per-message result rows are in `artifacts/results/`, and
  the report was rebuilt from them.

## Repository layout

```
src/safebank/      application code — schema, tools, pipeline, prompts, decoding, evaluation,
                   data prep, model loading, safety screen, experiment runner
tests/             398 tests
notebooks/         both executed notebooks, with stored outputs
artifacts/results/ raw result rows, summaries, device reports
artifacts/figures/ generated figures
report/            report source, one file per section, plus the three build scripts
submission/        the submitted documents
```

Status, the plan and the day-by-day record are in [`WORKLOG.md`](WORKLOG.md); the design rationale
is in [`ARCHITECTURE.md`](ARCHITECTURE.md). `PROJECT_PLAN.md` predates the code and `WORKLOG.md`
wins wherever they disagree.
