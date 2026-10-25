# Project Status & Handoff

**SafeBank Assist** · PCAM ZG516 Group Major Project · Group 22 · due **31 Oct 2026**

Last updated: 23 Oct 2026 by Kishore (Solution Architect).

- **[`WORKLOG.md`](WORKLOG.md)** — live status, what's done, what's pending, and **complete specifications for every unwritten file**. Start here if you are picking up a task.
- [`ARCHITECTURE.md`](ARCHITECTURE.md) — full technical detail and report source material.
- This page is the 2-minute version.

---

## Where the project stands

| Area | Module | Status | Owner |
|---|---|---|---|
| Config & constants | `config.py` | ✅ Done | Kishore |
| Label space, E6 focus set | `intents.py` | ✅ Done | Kishore |
| **E4** structured output + repair | `schema.py` | ✅ Done, 35 tests | Kishore |
| **E5** 3 simulated tools + router | `tools.py` | ✅ Done, 38 tests | Kishore |
| Generation seam, decode config | `generator.py` | ✅ Done, 22 tests | Kishore |
| **E7** end-to-end pipeline | `pipeline.py` | ✅ Done, 37 tests | Kishore |
| Package API | `__init__.py` | ✅ Done | Kishore |
| **E2** prompt strategies | `prompts.py` | 🟡 **1 of 4 done** (`ZERO_SHOT`) | Kishore → **Satya** |
| **E3** decoding grid | `decoding.py` | ⬜ Not started | **Satya** |
| **E6** metrics + failure analysis | `evaluate.py` | ⬜ Not started | **Satya** |
| Dataset load + sampling | `data_prep.py` | ⬜ Not started | **Vishruth** |
| **E1** model/tokenizer loading | `model_loader.py` | ⬜ Not started | **Vishruth** |
| Pinned dependencies | `requirements.txt` | ⬜ Not started | **Vishruth** |
| Report assembly | — | ⬜ Not started | **Bhavani** |

**Kishore's share is complete.** 195 tests pass with only pydantic installed.

---

## Verify it yourself in 30 seconds

```powershell
cd GenAI_Project1
python -m unittest discover -s tests -t . -v
```

Expected: `Ran 195 tests ... OK`. No install step, no `PYTHONPATH` — the suite puts `src` on the path itself. Needs **only pydantic**; no torch, no GPU, no network.

To see the whole application actually run:

```powershell
python -c "import sys; sys.path.insert(0,'src'); from safebank import *; p=SafeBankPipeline(FakeGenerator(), list(FOCUS_INTENTS)); r=p.run('my card has not arrived'); print(r.final_text)"
```

---

## Satya — start here

Three things are waiting for you, in this order.

**1. `prompts.py` — finish 3 of the 4 variants.** `ZERO_SHOT` is implemented as the reference. `FEW_SHOT`, `ROLE_CONTEXT` and `CONSTRAINT_BASED` raise `NotImplementedError` and each docstring already contains the intended signature, the design rationale, and numbered implementation notes. Read the docstring, then write the body.

- **Reuse** `format_intent_catalogue()`, `format_tool_catalogue()` and `format_schema_contract()`. If each variant hand-writes its own schema text, an accuracy difference in E2 could be caused by wording drift instead of by the strategy, and the comparison table stops meaning anything.
- Few-shot examples must come from the **train split only**. Drawing them from the evaluation sample contaminates every number in E2.
- `test_prompts.py::TestPendingVariantsAreHonestlyAbsent` asserts these still raise. **Those tests are meant to fail when you implement a variant** — replace each with real content assertions as you go.

**2. `decoding.py` — build the E3 grid.** `DecodeConfig` and `DecodeStrategy` already exist in `generator.py`; build the grid on top, do not redefine them. `DecodeConfig.to_generate_kwargs()` already emits only the knobs relevant to each strategy, and `.with_seed(n)` gives you the seed variation for the self-consistency measurement.

**3. `evaluate.py` — the 6 metrics.** Consume `PipelineResult.to_row()`; it already carries `ok`, `intent`, `confidence`, `attempts`, `needed_repair`, `first_failure`, `tool`, `tool_ok`, `escalated`, `latency_ms`. **scikit-learn 1.9.0, pandas and matplotlib are already installed locally**, so you can write and unit-test all the metrics code before any model exists — feed it `FakeGenerator` output.

### Interfaces that are frozen — build against these, don't change them

```python
parse_response(raw, allowed_intents) -> ValidationOutcome
execute_tool(name, args)             -> ToolResult
route_intent(intent)                 -> ToolName | None
build_prompt(strategy, query, allowed_intents, **kwargs) -> str
SafeBankPipeline(generator, allowed_intents, strategy=…).run(query, decode) -> PipelineResult
class TextGenerator(Protocol):
    def generate(self, prompt: str, decode: DecodeConfig) -> str: ...
```

If you think one of these needs to change, message me first — `pipeline.py` and 195 tests depend on them.

---

## Vishruth — start here

`model_loader.HFGenerator` must match `TextGenerator` structurally and return **the completion only**, with the prompt stripped. The pipeline feeds your return value straight into `parse_response`, so a prompt echo gets scored as a model failure.

- Seed from `decode.seed` before every sampled generation, and pass `**decode.to_generate_kwargs()`.
- Keep `import torch` / `import transformers` **inside function bodies**. The package must still import on a machine without them, or the whole test suite breaks.
- `data_prep.py` must call `intents.validate_label_space(labels)` on the loaded label space — see blocker 3 below.

---

## 3 open items that need a group decision

**1. 🔴 Environment — this blocks E1, E2, E3 and the real E7 run.**
`torch`, `transformers`, `datasets` and `tokenizers` are **not installed** and will not be installed on Kishore's machine (company laptop; Python 3.14.5 also predates stable wheels). Verified present: pydantic 2.13.4, numpy 2.5.2, pandas 2.3.3, scikit-learn 1.9.0, matplotlib, seaborn, scipy.
**Proposal:** all model work runs in Colab; the application layer and tests stay local. This is Open Item 2 in `PROJECT_PLAN.md` and it is now the critical path.

**2. 🟠 `PROJECT_PLAN.md` is stale — Bhavani must not quote it yet.**
Most important: the plan says *20 intents / 200 eval rows*; the code uses the **full 77 intents / 385 rows** (`EVAL_EXAMPLES_PER_INTENT = 5`). Full list of deviations in `ARCHITECTURE.md` §10.
Note the workload: 385 rows × 4 prompt variants × 6 decoding configs is far more inference than the plan assumed. **Satya should size this against Colab T4 time before starting E2.**

**3. 🟠 The 20 `FOCUS_INTENTS` names are unverified against the real dataset.**
They are structurally tested (20 unique, 5 themes × 4) but not checked against BANKING77, because `datasets` isn't installed. `intents.validate_label_space()` will raise `LabelSpaceError` naming any typo the first time `data_prep.py` supplies real labels. **This must run clean before any number goes in the report.**

---

## Ground rules

- **Branch per person**, PR into `main`. Don't commit straight to `main`.
- Nobody edits `schema.py`, `tools.py`, `pipeline.py` or `generator.py` without telling Kishore — 195 tests depend on them.
- Run the suite before every push. It takes 0.01s; there's no excuse.
- No real customer or financial data, ever. All IDs stay synthetic (`CARD_SIM_0001`, `ACC_SIM_0001`). Section 8 of the brief.
- Keep heavy imports (`torch`, `transformers`, `datasets`) inside function bodies so the package imports anywhere.
