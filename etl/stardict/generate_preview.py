"""
Generate an HTML preview of StarDict dictionary entries.

Reads actual dictionaries via binary parsing and renders sample entries
in a standalone HTML file for visual inspection in VS Code or a browser.
"""

import gzip
import os
import struct
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "..", ".."))
STARDICT_DIR = os.path.join(PROJECT_ROOT, "data", "stardict")
OUTPUT_FILE = os.path.join(SCRIPT_DIR, "preview.html")


def read_ifo(dict_dir):
    """Parse .ifo metadata file."""
    name = os.path.basename(dict_dir)
    ifo_path = os.path.join(dict_dir, f"{name}.ifo")
    info = {}
    with open(ifo_path, "r", encoding="utf-8") as f:
        for line in f:
            if "=" in line:
                k, v = line.strip().split("=", 1)
                info[k] = v
    return info


def read_entries(dict_dir):
    """Read all entries from .idx + .dict.dz, return list of (word, html)."""
    name = os.path.basename(dict_dir)
    idx_path = os.path.join(dict_dir, f"{name}.idx")
    dict_path = os.path.join(dict_dir, f"{name}.dict.dz")

    # Read index
    with open(idx_path, "rb") as f:
        idx_data = f.read()

    # Read compressed dictionary
    with gzip.open(dict_path, "rb") as f:
        dict_data = f.read()

    # Parse index entries
    entries = []
    pos = 0
    while pos < len(idx_data):
        null = idx_data.index(b"\x00", pos)
        word = idx_data[pos:null].decode("utf-8")
        offset, size = struct.unpack(">II", idx_data[null + 1 : null + 9])
        defi = dict_data[offset : offset + size].decode("utf-8")
        entries.append((word, defi))
        pos = null + 9

    return entries


def read_synonyms(dict_dir):
    """Read .syn file, return dict of synonym -> main word."""
    name = os.path.basename(dict_dir)
    syn_path = os.path.join(dict_dir, f"{name}.syn")
    if not os.path.exists(syn_path):
        return {}

    with open(syn_path, "rb") as f:
        syn_data = f.read()

    # We need the entry list to resolve indices
    entries = read_entries(dict_dir)
    entry_words = [e[0] for e in entries]

    synonyms = {}
    pos = 0
    while pos < len(syn_data):
        null = syn_data.index(b"\x00", pos)
        synonym = syn_data[pos:null].decode("utf-8")
        (idx,) = struct.unpack(">I", syn_data[null + 1 : null + 5])
        if idx < len(entry_words):
            synonyms[synonym] = entry_words[idx]
        pos = null + 5

    return synonyms


def find_entry(entries, name):
    """Find an entry by headword."""
    for word, html in entries:
        if word == name:
            return html
    return None


def generate_html():
    """Generate preview.html with sample dictionary entries."""

    # Load dictionaries
    dicts = {}
    samples = [
        ("cia-factbook-2025-general", "2025 General"),
        ("cia-factbook-2025-structured", "2025 Structured"),
        ("cia-factbook-1990-general", "1990 General"),
        ("cia-factbook-1991-general", "1991 General"),
    ]

    for dict_name, label in samples:
        dict_dir = os.path.join(STARDICT_DIR, dict_name)
        if os.path.isdir(dict_dir):
            dicts[label] = {
                "info": read_ifo(dict_dir),
                "entries": read_entries(dict_dir),
                "synonyms": read_synonyms(dict_dir),
            }

    if not dicts:
        print("No dictionaries found. Run build_stardict.py first.")
        sys.exit(1)

    # Build HTML
    parts = []
    parts.append("""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>StarDict Dictionary Preview</title>
<style>
  :root {
    --bg: #111418;
    --surface: #1C2127;
    --border: #2F343C;
    --text: #E0E0E0;
    --text-dim: #8A9BA8;
    --accent: #4A9EFF;
    --accent-dim: #2D6CB4;
    --heading: #C5D0DA;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    background: var(--bg);
    color: var(--text);
    font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
    line-height: 1.6;
    padding: 2rem;
    max-width: 1200px;
    margin: 0 auto;
  }
  h1 {
    color: var(--accent);
    font-size: 1.8rem;
    margin-bottom: 0.5rem;
    border-bottom: 2px solid var(--accent-dim);
    padding-bottom: 0.5rem;
  }
  .subtitle {
    color: var(--text-dim);
    margin-bottom: 2rem;
    font-size: 0.95rem;
  }
  h2 {
    color: var(--heading);
    font-size: 1.3rem;
    margin: 2rem 0 1rem;
    border-bottom: 1px solid var(--border);
    padding-bottom: 0.3rem;
  }
  .dict-meta {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 1rem 1.5rem;
    margin-bottom: 1.5rem;
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 0.5rem;
  }
  .dict-meta .label { color: var(--text-dim); font-size: 0.85rem; }
  .dict-meta .value { color: var(--text); font-weight: 600; }
  .entry-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 8px;
    margin-bottom: 1.5rem;
    overflow: hidden;
  }
  .entry-header {
    background: linear-gradient(135deg, #1a2332, #1f2937);
    padding: 0.8rem 1.5rem;
    border-bottom: 1px solid var(--border);
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
  .entry-name {
    color: var(--accent);
    font-size: 1.1rem;
    font-weight: 700;
  }
  .entry-badge {
    background: var(--accent-dim);
    color: white;
    padding: 0.2rem 0.6rem;
    border-radius: 4px;
    font-size: 0.75rem;
    font-weight: 600;
  }
  .entry-content {
    padding: 1.2rem 1.5rem;
    font-size: 0.9rem;
    line-height: 1.7;
  }
  .entry-content h3 {
    color: var(--accent);
    font-size: 1rem;
    margin: 1.2rem 0 0.4rem;
    padding-bottom: 0.2rem;
    border-bottom: 1px solid var(--border);
  }
  .entry-content h3:first-child { margin-top: 0; }
  .entry-content b { color: var(--heading); }
  .synonym-demo {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 1.2rem 1.5rem;
    margin-bottom: 1.5rem;
  }
  .synonym-demo code {
    background: #0d1117;
    color: var(--accent);
    padding: 0.15rem 0.4rem;
    border-radius: 3px;
    font-size: 0.9rem;
  }
  .synonym-arrow {
    color: var(--text-dim);
    margin: 0 0.5rem;
  }
  .comparison {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 1.5rem;
    margin-bottom: 1.5rem;
  }
  @media (max-width: 768px) {
    .comparison { grid-template-columns: 1fr; }
  }
  .stats-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
    gap: 1rem;
    margin-bottom: 2rem;
  }
  .stat-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 1rem;
    text-align: center;
  }
  .stat-card .number {
    color: var(--accent);
    font-size: 1.8rem;
    font-weight: 700;
  }
  .stat-card .label {
    color: var(--text-dim);
    font-size: 0.8rem;
    margin-top: 0.3rem;
  }
</style>
</head>
<body>
<h1>StarDict Dictionary Preview</h1>
<p class="subtitle">Sample entries rendered from the CIA World Factbook StarDict dictionaries</p>
""")

    # Stats cards
    total_entries = sum(len(d["entries"]) for d in dicts.values())
    total_synonyms = sum(len(d["synonyms"]) for d in dicts.values())
    parts.append(f"""
<div class="stats-grid">
  <div class="stat-card">
    <div class="number">{len(dicts)}</div>
    <div class="label">Dictionaries Loaded</div>
  </div>
  <div class="stat-card">
    <div class="number">{total_entries:,}</div>
    <div class="label">Total Entries</div>
  </div>
  <div class="stat-card">
    <div class="number">{total_synonyms:,}</div>
    <div class="label">Synonym Mappings</div>
  </div>
  <div class="stat-card">
    <div class="number">72</div>
    <div class="label">Full Collection</div>
  </div>
</div>
""")

    # Synonym demonstration
    if "2025 General" in dicts:
        syns = dicts["2025 General"]["synonyms"]
        demo_codes = ["US", "CN", "RU", "AU", "JP", "GB", "FR", "DE", "IN", "BR"]
        parts.append('<h2>Synonym Lookup Demonstration</h2>')
        parts.append('<div class="synonym-demo">')
        parts.append("<p>Look up any ISO Alpha-2 code to find the country entry:</p><br>")
        for code in demo_codes:
            target = syns.get(code, "not found")
            parts.append(
                f'<code>{code}</code>'
                f'<span class="synonym-arrow">-></span>'
                f'<strong>{target}</strong><br>'
            )
        parts.append("</div>")

    # Side-by-side comparison: United States
    if "2025 General" in dicts and "2025 Structured" in dicts:
        parts.append('<h2>General vs Structured: United States 2025</h2>')
        parts.append('<div class="comparison">')

        for label in ["2025 General", "2025 Structured"]:
            edition = label.split()[-1]
            entry_html = find_entry(dicts[label]["entries"], "United States")
            if entry_html:
                # Truncate to first 3 categories for readability
                truncated = entry_html
                h3_count = 0
                for i, c in enumerate(truncated):
                    if truncated[i:i+4] == "<h3>":
                        h3_count += 1
                        if h3_count > 3:
                            truncated = truncated[:i] + "<p><i>... (truncated for preview)</i></p>"
                            break

                parts.append(f"""
<div class="entry-card">
  <div class="entry-header">
    <span class="entry-name">United States</span>
    <span class="entry-badge">{edition}</span>
  </div>
  <div class="entry-content">{truncated}</div>
</div>""")

        parts.append("</div>")

    # Sample entries from 2025
    if "2025 General" in dicts:
        parts.append('<h2>Sample Entries: 2025 General Edition</h2>')
        sample_countries = ["China", "Australia", "Japan", "Brazil"]

        for country in sample_countries:
            entry_html = find_entry(dicts["2025 General"]["entries"], country)
            if entry_html:
                # Truncate to first 2 categories
                truncated = entry_html
                h3_count = 0
                for i in range(len(truncated)):
                    if truncated[i:i+4] == "<h3>":
                        h3_count += 1
                        if h3_count > 2:
                            truncated = truncated[:i] + "<p><i>... (truncated for preview)</i></p>"
                            break

                parts.append(f"""
<div class="entry-card">
  <div class="entry-header">
    <span class="entry-name">{country}</span>
    <span class="entry-badge">2025 General</span>
  </div>
  <div class="entry-content">{truncated}</div>
</div>""")

    # Historical entries
    historical = [
        ("1990 General", "Soviet Union"),
        ("1991 General", "Yugoslavia"),
    ]
    found_historical = False
    for label, country in historical:
        if label in dicts:
            entry_html = find_entry(dicts[label]["entries"], country)
            if entry_html:
                if not found_historical:
                    parts.append('<h2>Historical Entries</h2>')
                    found_historical = True

                truncated = entry_html
                h3_count = 0
                for i in range(len(truncated)):
                    if truncated[i:i+4] == "<h3>":
                        h3_count += 1
                        if h3_count > 2:
                            truncated = truncated[:i] + "<p><i>... (truncated for preview)</i></p>"
                            break

                year = label.split()[0]
                parts.append(f"""
<div class="entry-card">
  <div class="entry-header">
    <span class="entry-name">{country}</span>
    <span class="entry-badge">{year} General</span>
  </div>
  <div class="entry-content">{truncated}</div>
</div>""")

    # Dictionary metadata
    parts.append('<h2>Dictionary Metadata (.ifo)</h2>')
    for label, d in dicts.items():
        info = d["info"]
        parts.append(f"""
<div class="dict-meta">
  <div><span class="label">Dictionary</span><br><span class="value">{label}</span></div>
  <div><span class="label">Title</span><br><span class="value">{info.get('bookname', 'N/A')}</span></div>
  <div><span class="label">Entries</span><br><span class="value">{info.get('wordcount', 'N/A')}</span></div>
  <div><span class="label">Synonyms</span><br><span class="value">{info.get('synwordcount', 'N/A')}</span></div>
</div>""")

    parts.append("""
<p class="subtitle" style="margin-top: 3rem; text-align: center;">
  Generated from StarDict dictionaries at data/stardict/<br>
  Source: <a href="https://worldfactbookarchive.org/" style="color: var(--accent);">worldfactbookarchive.org</a>
</p>
</body>
</html>""")

    html_content = "\n".join(parts)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(html_content)

    print(f"Preview generated: {OUTPUT_FILE}")
    print(f"  Dictionaries: {len(dicts)}")
    print(f"  Entries shown: ~12 sample entries")
    print(f"  Open in VS Code or browser to view")


if __name__ == "__main__":
    generate_html()
