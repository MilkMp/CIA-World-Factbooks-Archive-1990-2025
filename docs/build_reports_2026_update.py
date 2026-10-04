"""Build the October 2026 review PDFs from their Markdown sources.

Run from any directory with: python docs/build_reports_2026_update.py
"""

from __future__ import annotations

from pathlib import Path
import subprocess

from pypdf import PdfReader


DOCS = Path(__file__).resolve().parent
SUMMARY_MD = DOCS / "EXECUTIVE_SUMMARY_2026-10-03.md"
SUMMARY_PDF = DOCS / "CIA_Factbook_Archive_Executive_Summary.pdf"
REPORT_MD = DOCS / "PROJECT_REPORT_UPDATE_2026-10-03.md"
REPORT_PDF = DOCS / "PROJECT_REPORT_2026-10-03.pdf"


def build_pdf(source: Path, output: Path) -> None:
    command = [
        "pandoc", str(source), "--standalone", "--from", "markdown+raw_tex",
        "--pdf-engine=xelatex", "-V", "geometry:margin=0.8in",
        "-V", "fontsize=10pt", "-V", "colorlinks=true",
        "-V", "linkcolor=MidnightBlue", "-V", "urlcolor=MidnightBlue",
        "--output", str(output),
    ]
    subprocess.run(command, check=True)


def build() -> None:
    for source, output in ((SUMMARY_MD, SUMMARY_PDF), (REPORT_MD, REPORT_PDF)):
        build_pdf(source, output)
        print(f"{output}: {len(PdfReader(output).pages)} pages")


if __name__ == "__main__":
    build()
