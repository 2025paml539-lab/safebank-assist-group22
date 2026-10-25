# Project Status & Handoff

**SafeBank Assist** · PCAM ZG516 Group Major Project · Group 22 · due **31 Oct 2026**

Last updated: 23 Oct 2026 by Kishore (Solution Architect).
Full detail in [`ARCHITECTURE.md`](ARCHITECTURE.md). This page is the 2-minute version.

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
| **E2** prompt strategies | `prompts.py` | ✅ Done, 59 tests (4 of 4) | Kishore (seam) → **Satya** |
| **E3** decoding grid | `decoding.py` | ✅ Done, 23 tests | **Satya** |
| **E6** metrics + failure analysis | `evaluate.py` | ✅ Done, 34 tests | **Satya** |
| Dataset load + sampling | `data_prep.py` | ⬜ Not started | **Vishruth** |
| **E1** model/tokenizer loading | `model_loader.py` | ⬜ Not started | **Vishruth** |
| Pinned dependencies | `requirements.txt` | ⬜ Not started | **Vishruth** |
| Report assembly | — | ⬜ Not started | **Bhavani** |

**Kishore's share is complete.** 195 tests pass with only pydantic installed.

**Satya's share (E2/E3/E6) is complete.** That original 195 already includes the 42 prompt-seam tests in `test_prompts.py`; Satya's work added **74 more, taking the suite to 269**. Breakdown: `test_prompts.py` grew 42 → 59 (+17, the three new variants replacing the stub tests), plus a new `test_decoding.py` (23) and `test_evaluate.py` (34). The E6 evaluation metrics (macro-F1, the results DataFrame) brought numpy, pandas and scikit-learn into the dependency set — see the install list below.

---

## Verify it yourself in 30 seconds

Install the current dependency set, then run the suite:

```powershell
python -m pip install pydantic numpy pandas scikit-learn
python -m unittest discover -s tests -t . -v
```

Expected: `Ran 269 tests ... OK`. No `PYTHONPATH` — the suite puts `src` on the path itself; no torch, no GPU, no network.

To see the whole application actually run:

```powershell
python -c "import sys; sys.path.insert(0,'src'); from safebank import *; p=SafeBankPipeline(FakeGenerator(), list(FOCUS_INTENTS)); r=p.run('my card has not arrived'); print(r.final_text)"
```

---

## Satya — done

All three modules are implemented and tested through the real pipeline control flow via the `TextGenerator` seam, using the scripted `FakeGenerator` in place of the model so the logic can be verified with no GPU or model runtime present. The modules are model-agnostic by design: when Vishruth's `model_loader.HFGenerator` lands, the same code produces the real E2/E3/E6 numbers in Colab with no change — `FakeGenerator` is a development fixture, never a source of reported results. Summary of what landed, for the group:

**1. `prompts.py` — 4 of 4 variants done.** `FEW_SHOT`, `ROLE_CONTEXT` and `CONSTRAINT_BASED` now build real prompts; none falls back to zero-shot. All reuse `format_intent_catalogue()`, `format_tool_catalogue()` and `format_schema_contract()`, so the shared blocks are byte-identical across variants and an E2 accuracy delta is attributable to the strategy. Few-shot takes train-split pairs via its `examples=` argument (offline fallback bank is clearly marked as illustrative, **not** eval data — pass Vishruth's train split for real E2 numbers). `TestPendingVariantsAreHonestlyAbsent` was replaced with content assertions; `test_prompts.py` is now 59 tests.

**2. `decoding.py` — E3 grid done.** Built on top of `DecodeConfig`/`DecodeStrategy` (not redefined), via `to_generate_kwargs()` and `.with_seed(n)`. `build_decoding_grid()` returns the 6-config grid (greedy, two temperatures, top-k, two top-p); `self_consistency_configs()` returns the seed-varied run set for criterion 6. 23 tests.

**3. `evaluate.py` — 6 metrics + E6 failure analysis done.** Consumes `PipelineResult.to_row()` via `EvalRecord` (which pairs a row with its gold intent). All six metrics plus `analyse_failures()` and the `evaluate_run()`/`results_dataframe()` helpers. 34 tests.

**Dependencies this adds (for Vishruth's `requirements.txt`).** The E6 evaluation metrics bring **numpy, pandas and scikit-learn** into the application-layer dependency set (macro-F1 and the results DataFrame). Please pin all three alongside pydantic and the model stack. They are imported inside the functions that use them rather than at module top, following `model_loader.py`'s torch pattern, so `import safebank` stays lightweight — but to run the suite or the evaluation they do need to be installed.

**Note on the top-level API.** `__init__.py` is unchanged, so import the new modules as `from safebank.decoding import …` / `from safebank.evaluate import …`. Kishore: happy to add them to the curated exports if you'd prefer — your call since it's your file.

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
