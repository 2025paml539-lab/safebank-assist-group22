# Project Status & Handoff

**SafeBank Assist** · PCAM ZG516 Group Major Project · Group 22 · due **31 Oct 2026**

Last updated: 30 Oct 2026 by Vishruth (data, environment).

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
| **E7** end-to-end pipeline | `pipeline.py` | ✅ Done, 55 tests | Kishore |
| **R13** reply safety screen | `safety.py` | ✅ Done, 24 tests | Kishore |
| Package API | `__init__.py` | ✅ Done | Kishore |
| **E2** prompt strategies | `prompts.py` | ✅ Done, 59 tests (4 of 4) | Kishore (seam) → **Satya** |
| **E3** decoding grid | `decoding.py` | ✅ Done, 23 tests | **Satya** |
| **E6** metrics + failure analysis | `evaluate.py` | ✅ Done, 39 tests | **Satya** |
| Dataset load + sampling | `data_prep.py` | ✅ Done, 24 tests | **Vishruth** |
| **E1** model/tokenizer loading | `model_loader.py` | ✅ Done, 13 tests (6 gated on real GPT-2) | **Vishruth** |
| Pinned dependencies | `requirements.txt`, `requirements-colab.txt` | ✅ Done | **Vishruth** |
| Colab notebook | `notebooks/safebank_colab.ipynb` | 🟡 **Runs clean on a Colab T4 (30 Oct, from the fork)**; T4 outputs and artifacts not yet committed | **Vishruth** |
| Report assembly | — | 🔴 Not started — drafts ready, see `WORKLOG.md` §2.1 | **Bhavani** |

**All code is complete and merged — Kishore, Satya and Vishruth.** **353 tests** (347 run offline and pass, 6 gated on real GPT-2), a few seconds, with only pydantic required (scikit-learn additionally for the macro-F1 assertions).

**Satya's share (E2/E3/E6) is merged** (PR #1, 25 Oct). It added **+79** tests: `test_prompts.py` grew 42 → 59 as the three new variants replaced the stub tests, plus a new `test_decoding.py` (23) and `test_evaluate.py` (39, including 5 regression tests for the destructive-refusal routing credit). A further **+2** came from exposing the model reply in `to_row()` for evaluation criterion 4, giving 276. Vishruth's PR #2 then added +37, and the review fixes plus the safety screen +40, for **353**.

**All code is now complete.** The experiment *runs* are what remains, and they wait only on a Colab session — see item 1 below.

---

## Verify it yourself in 30 seconds

Install the current dependency set, then run the suite:

```powershell
python -m pip install pydantic numpy pandas scikit-learn
python -m unittest discover -s tests -t . -v
```

Expected: `Ran 353 tests ... OK (skipped=6)`, a few seconds. No `PYTHONPATH` — the suite puts `src` on the path itself; no torch, no GPU, no network.

To see the whole application actually run:

```powershell
python -c "import sys; sys.path.insert(0,'src'); from safebank import *; p=SafeBankPipeline(FakeGenerator(), list(FOCUS_INTENTS)); r=p.run('my card has not arrived'); print(r.final_text)"
```

---

## Satya — done

All three modules are implemented and tested through the real pipeline control flow via the `TextGenerator` seam, using the scripted `FakeGenerator` in place of the model so the logic can be verified with no GPU or model runtime present. The modules are model-agnostic by design: when Vishruth's `model_loader.HFGenerator` lands, the same code produces the real E2/E3/E6 numbers in Colab with no change — `FakeGenerator` is a development fixture, never a source of reported results. Summary of what landed, for the group:

**1. `prompts.py` — 4 of 4 variants done.** `FEW_SHOT`, `ROLE_CONTEXT` and `CONSTRAINT_BASED` now build real prompts; none falls back to zero-shot. All reuse `format_intent_catalogue()`, `format_tool_catalogue()` and `format_schema_contract()`, so the shared blocks are byte-identical across variants and an E2 accuracy delta is attributable to the strategy. Few-shot takes train-split pairs via its `examples=` argument (offline fallback bank is clearly marked as illustrative, **not** eval data — pass Vishruth's train split for real E2 numbers). `TestPendingVariantsAreHonestlyAbsent` was replaced with content assertions; `test_prompts.py` is now 59 tests.

**2. `decoding.py` — E3 grid done.** Built on top of `DecodeConfig`/`DecodeStrategy` (not redefined), via `to_generate_kwargs()` and `.with_seed(n)`. `build_decoding_grid()` returns the 6-config grid (greedy, two temperatures, top-k, two top-p); `self_consistency_configs()` returns the seed-varied run set for criterion 6. 23 tests.

**3. `evaluate.py` — 6 metrics + E6 failure analysis done.** Consumes `PipelineResult.to_row()` via `EvalRecord` (which pairs a row with its gold intent). All six metrics plus `analyse_failures()` and the `evaluate_run()`/`results_dataframe()` helpers. 39 tests.

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

If you think one of these needs to change, message me first — `pipeline.py` and 353 tests depend on them.

---

## Vishruth — T4 run done; next is the group-repo PR

`data_prep.py`, `model_loader.py`, both requirements files and the notebook are merged (PR #2), and `validate_label_space()` passes on the real 77 labels. On 29 Oct the dataset-link fix (V1) landed on Vishruth's fork, the notebook ran top to bottom with no errors on a local CPU (nbconvert and VS Code), and report §6 was drafted from that run. On 30 Oct the notebook ran top to bottom on a Colab T4 (float16) from the fork, with the same E1 replies as the CPU run, so §6 is confirmed. Still owed:

1. 🔴 **Get the fix into the group repo (V1b) — now blocks Satya.** The group repo's `main` is still `a4a1e5f`, without the fix; any Colab run that clones it (E2/E3/E6) fails with a 404 on `dataset_infos.json`. Open a PR from the fork's `main` into `2025paml539-lab/safebank-assist-group22`; Kishore to review and merge; then point the notebook's `REPO_URL` back at the group repo.
2. 🟡 **Commit the T4 run.** The run itself is done; commit the notebook with its T4 outputs and replace `artifacts/results/device_report.json` and `e1_baseline.csv`, which in git are from the CPU run, with the files from the Colab runtime.
3. 🟡 Sign the contribution row in Appendix I (V4): the description is updated; add name and date.
4. 🟡 Warn when `build_example_bank` gets no `exclude=` — today the train/test-overlap protection is opt-in.
5. 🟡 Record a SHA-256 of each downloaded CSV in `preprocessing_record()`, so the frozen-eval-set claim can be checked.

---

## Open items

**1. 🟠 The Colab runs — E1 and the E7 smoke run are done on a T4 (30 Oct); E2, E3, E6 still to run.**
Decided: the model stack (`torch`, `transformers`, `datasets`, `tokenizers`) runs in Colab only; the application layer and tests run locally on pydantic, numpy, pandas and scikit-learn. The environment is verified on a T4. What blocks the E2/E3/E6 runs is the dataset fix reaching the group repo (see Vishruth, item 1); until it is merged, run from the fork.

**2. 🟠 `PROJECT_PLAN.md` is stale — Bhavani must not quote it yet.**
Most important: the plan says *20 intents / 200 eval rows*; the code uses the **full 77 intents / 385 rows** (`EVAL_EXAMPLES_PER_INTENT = 5`). Full list of deviations in `ARCHITECTURE.md` §10.
Note the workload: 385 rows × 4 prompt variants × 6 decoding configs is far more inference than the plan assumed. **Satya should size this against Colab T4 time before starting E2.**

**3. ✅ CLOSED — the 20 `FOCUS_INTENTS` names are verified.** `validate_label_space()` passed on the real 77 labels on 25 Oct.

---

## Ground rules

- **Branch per person**, PR into `main`. Don't commit straight to `main`.
- Nobody edits `schema.py`, `tools.py`, `pipeline.py` or `generator.py` without telling Kishore — 353 tests depend on them.
- Run the suite before every push. It takes 3 seconds; there's no excuse.
- No real customer or financial data, ever. All IDs stay synthetic (`CARD_SIM_0001`, `ACC_SIM_0001`). Section 8 of the brief.
- Keep heavy imports (`torch`, `transformers`, `datasets`) inside function bodies so the package imports anywhere.
