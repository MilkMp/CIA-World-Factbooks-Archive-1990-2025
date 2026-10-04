"""Convert source links at paragraph ends into grouped Pandoc citations.

report.md keeps human-readable links for editing. The PDF build uses this
transformation so its notes and bibliography are generated from references.json.
Every linked source in the narrative must be mapped. Each cited paragraph ends
with a source list after sentence punctuation; an inline source link is retained
and included in that paragraph's grouped note.
"""

from __future__ import annotations

import json
from pathlib import Path
import re


HERE = Path(__file__).resolve().parent
LINK = re.compile(r"\[([^]]+)\]\((https?://[^)]+)\)")
TAIL = re.compile(
    r"\s*\[[^]]+\]\(https?://[^)]+\)"
    r"(?:;\s*\[[^]]+\]\(https?://[^)]+\))*\.$"
)


def cited_report() -> str:
    refs = json.loads((HERE / "references.json").read_text(encoding="utf-8"))
    url_to_id = {ref["URL"]: ref["id"] for ref in refs}
    source = (HERE / "report.md").read_text(encoding="utf-8")
    output = []
    citation_groups = 0
    for number, line in enumerate(source.splitlines(keepends=True), 1):
        newline = "\n" if line.endswith("\n") else ""
        body = line.removesuffix("\n")
        links = LINK.findall(body)
        if links:
            tail = TAIL.search(body)
            if not tail or not body[:tail.start()].rstrip().endswith("."):
                raise ValueError(f"Review citation placement on report.md line {number}")
            missing = [url for _, url in links if url not in url_to_id]
            if missing:
                raise ValueError(f"Unmapped source URL on line {number}: {missing}")
            ids = [url_to_id[url] for _, url in links]
            body = body[:tail.start()] + " [@" + "; @".join(ids) + "]"
            citation_groups += 1
        output.append(body + newline)
    if citation_groups < 50:
        raise ValueError(f"Only {citation_groups} source notes found; inspect report.md")
    return "".join(output)


if __name__ == "__main__":
    print(cited_report())
