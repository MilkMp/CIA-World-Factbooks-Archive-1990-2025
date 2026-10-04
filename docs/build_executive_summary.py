"""Build the dated October 2026 executive summary from its Markdown source.

Run from any directory with: python docs/build_executive_summary.py
"""

from __future__ import annotations

from pathlib import Path
import subprocess

from pypdf import PdfReader


DOCS = Path(__file__).resolve().parent
SUMMARY_MD = DOCS / "EXECUTIVE_SUMMARY_2026-10-03.md"
SUMMARY_PDF = DOCS / "CIA_Factbook_Archive_Executive_Summary.pdf"


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
    build_pdf(SUMMARY_MD, SUMMARY_PDF)
    print(f"{SUMMARY_PDF}: {len(PdfReader(SUMMARY_PDF).pages)} pages")


if __name__ == "__main__":
    build()
