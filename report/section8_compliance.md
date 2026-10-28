# Section 8 compliance — proofread of the draft (28 Oct 2026)

Checked against "8. What Students Should NOT Do" in the brief. Re-run before submission, after the results are added.

| Rule | Status | Evidence |
|---|---|---|
| Do not train a large LLM from scratch | ✅ | pretrained checkpoints only (§2, §4.2); the repository contains no training code |
| Do not submit only screenshots of ChatGPT/LLM conversations | ✅ | no screenshots in the report; evidence is code, 353 automated tests and the notebook |
| Do not use prompts without explaining why they were designed | 🟡 | the written rationale for all four strategies is in Appendix A.2; §7 must also explain each design when its results are added |
| Do not claim model accuracy without an evaluation procedure | ✅ so far | no accuracy figure is claimed yet; every number added to §7, §8 and §11 must sit next to its procedure (385-row sample, seed 42, the six criteria) |
| Do not expose real personal, financial, medical or confidential information | ✅ | public dataset, simulated tools, synthetic identifiers; the automated scan finds no personal or machine-specific details |
| Do not treat generated text as automatically correct | ✅ | validation, label check, safety screen, confidence gate and escalation (§10, §12); failure analysis in §12.1 |
| Do not make diffusion or multimodal generation mandatory | ✅ | diffusion appears only as one of the families compared in §4.1 |

## Automated checks (`python report/build_report.py`)

| Check | Result |
|---|---|
| All 14 sections, References and Appendix present, in order | ✅ |
| Every citation has a reference, and every reference is cited | ✅ — references [11], [12], [14] and [19]–[21] are cited only inside the pending §4.1 and §8 notes; keep those citations when the sections are written |
| Personal or machine-specific details | ✅ none |
| Body length, sections 1–14 (budget 10–15 pages) | 🟡 9 pages while results are pending; expected 12–14 once §4.1, §6–§8, §11 and §12.1 are filled |
| Pending items | 🔴 25 — `--final` refuses to build until there are none |
| Member details on the title page | 🔴 three BITS IDs missing |

## Before submitting

1. Fill every pending item, then run `python report/build_report.py --final` until it prints `READY`.
2. Re-read §7, §8 and §11 against rules 3 and 4: every prompt explained, every number tied to its procedure.
3. Confirm nothing added later is a screenshot of a chat interface.
4. Each member signs or confirms their own row of the contribution statement (Appendix I).
