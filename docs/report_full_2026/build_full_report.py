"""Build the dated report PDF from narrative, evidence appendices, and figures."""

from __future__ import annotations

from pathlib import Path
import subprocess
import tempfile

from pypdf import PdfReader

from make_cited_report import cited_report

HERE = Path(__file__).resolve().parent
OUTPUT = HERE.parent / "PROJECT_REPORT_FULL_2026-10-03.pdf"


def main() -> None:
    subprocess.run(["python", str(HERE / "make_figures.py")], check=True)
    subprocess.run(["python", str(HERE / "make_appendices.py")], check=True)
    with tempfile.TemporaryDirectory(prefix="factbook-report-") as temp_dir:
        cited_source = Path(temp_dir) / "report_cited.md"
        cited_source.write_text(cited_report(), encoding="utf-8")
        cmd = [
            "pandoc",
            str(cited_source),
            str(HERE / "appendices.md"),
            "--standalone",
            "--from", "markdown+raw_tex+link_attributes",
            "--top-level-division=section",
            "--lua-filter", str(HERE / "section_pages.lua"),
            "--citeproc",
            "--bibliography", str(HERE / "references.json"),
            "--csl", str(HERE / "chicago-notes-bibliography.csl"),
            "--metadata", "reference-section-title=Bibliography",
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
