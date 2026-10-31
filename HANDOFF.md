# Project Status & Handoff

**SafeBank Assist** · PCAM ZG516 Group Major Project · Group 22 · due **31 Oct 2026**

Last updated: 30 Oct 2026 — PR #3 and PR #4 merged; `main` is `8aa5fce`.

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
| Colab notebook | `notebooks/safebank_colab.ipynb` | ✅ **Merged with its Colab T4 outputs** (PR #3); `REPO_URL` still points at a fork | **Vishruth** |
| **E2/E3/E6** experiment runner + notebook | `experiments.py`, `notebooks/safebank_experiments.ipynb` | ✅ Done, 45 tests; **run on an A100 Kubeflow server on 31 Oct**, results in `artifacts/results/` | **Satya** |
| Report assembly | `report/` | 🟡 **Draft assembled**, builds with `python report/build_report.py`; 17 items pending | **Bhavani** |

**All code is complete and merged — Kishore, Satya and Vishruth.** **353 tests** (347 run offline and pass, 6 gated on real GPT-2), a few seconds, with only pydantic required (scikit-learn additionally for the macro-F1 assertions).

**Satya's share (E2/E3/E6) is merged** (PR #1, 25 Oct). It added **+79** tests: `test_prompts.py` grew 42 → 59 as the three new variants replaced the stub tests, plus a new `test_decoding.py` (23) and `test_evaluate.py` (39, including 5 regression tests for the destructive-refusal routing credit). A further **+2** came from exposing the model reply in `to_row()` for evaluation criterion 4, giving 276. Vishruth's PR #2 then added +37, and the review fixes plus the safety screen +40, for **353**. The E2/E3/E6 runner (`experiments.py`) and its notebook add **+45** tests, taking the suite to **398**; report §4.1 was written alongside.

**All code is now complete.** E1 and the E7 smoke run (T4, 30 Oct) are merged and E2, E3 and E6 ran on 31 Oct (A100) — see item 1 below.

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

All three modules are implemented and tested through the real pipeline control flow via the `TextGenerator` seam, using the scripted `FakeGenerator` in place of the model so the logic can be verified with no GPU or model runtime present. The modules are model-agnostic by design, and the same code has since produced the real E2/E3/E6 numbers through Vishruth's `HFGenerator` (31 Oct, A100 server) with no change — `FakeGenerator` stayed a development fixture, never a source of reported results. All of S1–S7 are done; see the 31 Oct entry in `WORKLOG.md`. Summary of what landed, for the group:

**1. `prompts.py` — 4 of 4 variants done.** `FEW_SHOT`, `ROLE_CONTEXT` and `CONSTRAINT_BASED` now build real prompts; none falls back to zero-shot. All reuse `format_intent_catalogue()`, `format_tool_catalogue()` and `format_schema_contract()`, so the shared blocks are byte-identical across variants and an E2 accuracy delta is attributable to the strategy. Few-shot takes train-split pairs via its `examples=` argument (offline fallback bank is clearly marked as illustrative, **not** eval data; the E2 run used Vishruth's train-split bank). `TestPendingVariantsAreHonestlyAbsent` was replaced with content assertions; `test_prompts.py` is now 59 tests.

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

## Vishruth — V1–V3 merged (PR #3)

`data_prep.py`, `model_loader.py`, both requirements files and the notebook are merged (PR #2), and `validate_label_space()` passes on the real 77 labels. On 29 Oct the dataset-link fix (V1) landed on Vishruth's fork, the notebook ran top to bottom with no errors on a local CPU (nbconvert and VS Code), and report §6 was drafted from that run. On 30 Oct the notebook ran top to bottom on a Colab T4 (float16) from the fork, with the same E1 replies as the CPU run, so §6 is confirmed. Still owed:

1. ✅ **CLOSED — the fix is in the group repo.** PR #3 merged as `d49e9bc`: the dataset-link fix, the notebook with its T4 outputs, the result artifacts and report §6. Colab runs that clone `main` now load the label space.
2. ✅ **CLOSED — the T4 run is committed**, together with `device_report.json`, `e1_baseline.csv`, `eval_sample.jsonl`, `few_shot_examples.json`, `preprocessing_record.json` and the class-distribution figure.
3. 🟡 Sign the contribution row in Appendix I (V4): the description is updated; add typed name and date.
4. 🟡 Delete the duplicate `artifacts/results/e1_baseline (1).csv`. That copy is the T4 run — its timings match the notebook output — and `e1_baseline.csv` is the earlier run, so keep the T4 numbers under the canonical name.
5. 🟡 Point the notebook's `REPO_URL` back at `https://github.com/2025paml539-lab/safebank-assist-group22.git`; it currently points at the fork, so a Colab clone of the committed notebook misses anything merged since.
6. 🟡 Warn when `build_example_bank` gets no `exclude=` — today the train/test-overlap protection is opt-in.
7. 🟡 Record a SHA-256 of each downloaded CSV in `preprocessing_record()`, so the frozen-eval-set claim can be checked.

The `top_k` follow-up raised in the PR #3 review is closed by **PR #4** (`8aa5fce`): `_neutral_generation_config()` set `gc.top_k = None`, but transformers 5.19 `_prepare_generation_config()` calls `update(**model.generation_config.to_dict(), defaults_only=True)`, which refills `None` fields from the model's own config — so Qwen's `top_k=20` came back and would have applied top-k truncation to the E3 temperature and top-p runs as well. It is now `gc.top_k = 0`, which is not refilled, with the test expectation updated. Greedy decoding was never affected. Not yet confirmed against a real `generate()` call, since there is no GPU locally: the first E3 run should check the `['top_k']` ignored-flag warning is gone.

---

## Open items

**1. ✅ The runs — E1 and the E7 smoke run (T4, 30 Oct) and E2, E3 and E6 (A100, Kubeflow server, 31 Oct) are done.** The real E7 integrated run remains Kishore's item.
Decided: the model stack (`torch`, `transformers`, `datasets`, `tokenizers`) runs in Colab only; the application layer and tests run locally on pydantic, numpy, pandas and scikit-learn. The environment is verified on a T4. **E2, E3 and E6 have since run** (31 Oct); the environment recipe for a fresh Kubeflow image is in the 31 Oct entry of `WORKLOG.md`. One session setting to remember: set `REPO_URL` to the group repo before the clone cell, because the committed notebook still points at a fork.

**2. 🟠 `PROJECT_PLAN.md` is stale — Bhavani must not quote it yet.**
Most important: the plan says *20 intents / 200 eval rows*; the code uses the **full 77 intents / 385 rows** (`EVAL_EXAMPLES_PER_INTENT = 5`). Full list of deviations in `ARCHITECTURE.md` §10.
Note the workload: 385 rows × 4 prompt variants × 6 decoding configs is far more inference than the plan assumed. Sized and run: E2 took about 10 minutes on an A100 (1,737 generations including repairs), and E3 ran 2,002 generations on the 77-row subset.

**3. ✅ CLOSED — the 20 `FOCUS_INTENTS` names are verified.** `validate_label_space()` passed on the real 77 labels on 25 Oct.

---

## Ground rules

- **Branch per person**, PR into `main`. Don't commit straight to `main`.
- Nobody edits `schema.py`, `tools.py`, `pipeline.py` or `generator.py` without telling Kishore — 353 tests depend on them.
- Run the suite before every push. It takes 3 seconds; there's no excuse.
- No real customer or financial data, ever. All IDs stay synthetic (`CARD_SIM_0001`, `ACC_SIM_0001`). Section 8 of the brief.
- Keep heavy imports (`torch`, `transformers`, `datasets`) inside function bodies so the package imports anywhere.
