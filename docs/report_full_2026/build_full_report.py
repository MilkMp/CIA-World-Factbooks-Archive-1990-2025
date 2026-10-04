"""Build the review PDF from narrative, generated evidence appendices, and figures."""

from __future__ import annotations

from pathlib import Path
import subprocess

from pypdf import PdfReader


HERE = Path(__file__).resolve().parent
OUTPUT = HERE.parent / "PROJECT_REPORT_FULL_2026-10-03.pdf"


def main() -> None:
    subprocess.run(["python", str(HERE / "make_figures.py")], check=True)
    subprocess.run(["python", str(HERE / "make_appendices.py")], check=True)
    cmd = [
        "pandoc",
        str(HERE / "report.md"),
        str(HERE / "appendices.md"),
        "--standalone",
        "--from", "markdown+raw_tex+link_attributes",
        "--top-level-division=chapter",
        "--toc-depth=1",
        "--pdf-engine=xelatex",
        "--resource-path", str(HERE),
        "--output", str(OUTPUT),
    ]
    subprocess.run(cmd, check=True, cwd=HERE)
    pages = len(PdfReader(OUTPUT).pages)
    print(f"Built {OUTPUT}: {pages} pages")
    if pages < 60:
        raise SystemExit(f"Full report is {pages} pages, below the requested 60-page scale")


if __name__ == "__main__":
    main()
