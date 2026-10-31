"""
Build the individual contribution statement as a standalone PDF.

The statement is already printed as Appendix I of the main report; this produces
it as a separate document for portals that ask for it on its own. It reuses the
main build's toolchain and stylesheet, so the two look the same:

    Markdown -> HTML (markdown-it-py) -> PDF (Microsoft Edge, headless)

Usage, from the project root:

    python report/build_contribution_pdf.py

Output: report/build/SafeBank_Assist_Group22_Contribution_Statement.pdf
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent
BUILD = HERE / "build"
SOURCE = HERE / "contribution_statement.md"
OUT = BUILD / "SafeBank_Assist_Group22_Contribution_Statement.pdf"

TITLE = "PCAM* ZG516 – Applied Generative AI · Group Major Project / Assignment – 1"
SUBTITLE = "Group 22 · SafeBank Assist · Individual contribution statement"


def find_edge() -> str:
    for p in (r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
              r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"):
        if Path(p).exists():
            return p
    found = shutil.which("msedge")
    if found:
        return found
    raise SystemExit(
        "Microsoft Edge not found. Open report/build/contribution_statement.html "
        "in a browser and print it to PDF."
    )


def render_html(markdown_text: str) -> str:
    from markdown_it import MarkdownIt

    body = MarkdownIt("commonmark").enable("table").render(markdown_text)
    return (
        '<!doctype html>\n<html lang="en"><head><meta charset="utf-8">'
        "<title>SafeBank Assist — contribution statement, Group 22</title>"
        '<link rel="stylesheet" href="../report.css">'
        "<style>body{padding:0}h1.doc{font-size:13pt;margin:0 0 2pt}"
        "p.doc{font-size:10pt;color:#333;margin:0 0 14pt}</style>"
        "</head>\n<body>\n"
        f'<h1 class="doc">{TITLE}</h1>\n<p class="doc">{SUBTITLE}</p>\n'
        f"{body}\n</body></html>\n"
    )


def print_pdf(html_path: Path, pdf_path: Path) -> None:
    profile = BUILD / "edge-profile-contrib"
    cmd = [
        find_edge(), "--headless=new", "--disable-gpu", "--no-first-run",
        "--no-default-browser-check", "--disable-extensions", "--no-pdf-header-footer",
        "--print-to-pdf-no-header", "--run-all-compositor-stages-before-draw",
        "--virtual-time-budget=8000", f"--user-data-dir={profile}",
        f"--print-to-pdf={pdf_path}", html_path.as_uri(),
    ]
    if pdf_path.exists():
        pdf_path.unlink()
    subprocess.run(cmd, capture_output=True, text=True, timeout=240)
    shutil.rmtree(profile, ignore_errors=True)
    if not pdf_path.exists():
        raise SystemExit("Edge did not produce a PDF. Print the HTML manually instead.")


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    BUILD.mkdir(parents=True, exist_ok=True)
    text = SOURCE.read_text(encoding="utf-8")

    rows = [l for l in text.splitlines() if l.startswith("|") and l.count("|") > 3][2:]
    unconfirmed = [r.strip("|").split("|")[0].strip() for r in rows
                   if not r.strip("|").split("|")[3].strip()]
    pending = [l for l in text.splitlines() if "[[" in l]

    html_path = BUILD / "contribution_statement.html"
    html_path.write_text(render_html(text), encoding="utf-8")
    print_pdf(html_path, OUT)

    import pymupdf
    doc = pymupdf.open(OUT)
    extracted = "".join(p.get_text() for p in doc)
    print(f"PDF: {OUT}")
    print(f"pages: {doc.page_count} | size: {OUT.stat().st_size:,} bytes")
    print(f"members in table: {len(rows)}")
    print(f"confirmations present: {len(rows) - len(unconfirmed)} of {len(rows)}")
    if unconfirmed:
        print(f"still to confirm: {', '.join(unconfirmed)}")
    if pending:
        print(f"WARNING: {len(pending)} unfilled marker(s) in the source")
    for name in ("2025paml539", "2025paml536", "2025paml561", "2025paml562"):
        print(f"  BITS ID {name} in PDF: {name in extracted}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
