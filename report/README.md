# Technical report

Source for the SafeBank Assist technical report (Deliverable 1) and the material that goes with it.

## Build

From the project root (`GenAI_Project1`):

```powershell
python report/build_report.py              # draft PDF: lists pending items, stamps DRAFT on each page
python report/build_report.py --final      # refuses to finish while anything is pending
python report/build_report.py --offline    # reuse report/generated/ (no network)
python report/build_report.py --preview    # also writes page images to report/build/preview/
```

Output: `report/build/SafeBank_Assist_Group22_Report.pdf`. Needs only what is already installed: the project's own packages plus markdown-it-py, matplotlib, PyMuPDF and Microsoft Edge (used headless to print the HTML to PDF). Nothing under `src/` is modified; the build only reads the code.

## Layout

| Path | Contents |
|---|---|
| `sections/00_title.md` … `14_conclusion.md` | one file per report section, in the brief's suggested structure |
| `sections/90_references.md`, `95_appendix.md` | references and appendix |
| `generated/` | tables and code listings produced by the build from the data and the code — do not edit by hand |
| `assets/` | figures and equations produced by the build |
| `contribution_statement.md` | individual contribution statement; also printed as Appendix I |
| `section8_compliance.md` | proofread against Section 8 of the brief, plus the automated checks |
| `demo_opening_segment.md` | script and slide notes for the first 90 seconds of the demo |
| `report.css`, `build_report.py` | print stylesheet and build script |

## What is still pending

Every gap is marked inline as `[[PENDING …]]`, `[[CONFIRM …]]` or `[[BITS ID]]`, highlighted in the draft PDF and listed by the build. They need the experiment runs (E1, E2, E3, E6 and the E7 trace), the tokenizer walkthrough and device report from the notebook, the BITS IDs, and each member's confirmation of the contribution statement. To fill one, edit the section file it is in and rebuild.

## Checks the build runs

- all 14 section headings, References and Appendix present, in order
- body (sections 1–14) within the 10–15 page budget
- every citation number has a reference; lists references not yet cited
- no pending markers left (`--final` only)
- no machine-specific or personal details in the text
