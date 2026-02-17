"""
CIA Factbook Archive - HTML Parser Diagnostic
==============================================
Downloads sample HTML from broken and working years, analyzes the
structure to determine why parsing failed.

Saves raw HTML files to html_samples/ for manual inspection.

Run: python diagnose_parsers.py
"""
import sys
import os
import re
import zipfile
from collections import Counter
from bs4 import BeautifulSoup

# Import download and parse functions from the original builder
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_archive as ba

SAMPLE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "html_samples")
SAMPLE_COUNTRY = "us"  # Well-known country guaranteed to exist in every year

# Years to diagnose: broken + working references
SAMPLE_YEARS = [
    (2000, "classic WORKING (reference)"),
    (2003, "classic BROKEN"),
    (2008, "mid BROKEN"),
    (2009, "mid WORKING (reference)"),
    (2016, "modern OVER-PARSED"),
    (2018, "modern WORKING (reference)"),
]


def download_and_extract(year):
    """Download zip for a year, extract us.html, return path to saved HTML."""
    os.makedirs(SAMPLE_DIR, exist_ok=True)
    out_path = os.path.join(SAMPLE_DIR, f"{year}_us.html")

    # Skip download if we already have the file
    if os.path.exists(out_path) and os.path.getsize(out_path) > 1000:
        print(f"  Already have {year}_us.html ({os.path.getsize(out_path):,} bytes)")
        return out_path

    print(f"  Downloading {year} zip from Wayback Machine...")
    zip_path = ba.download_zip(year)
    if not zip_path:
        print(f"  FAILED to download {year}")
        return None

    with zipfile.ZipFile(zip_path) as zf:
        all_files = zf.namelist()
        # Find us.html in geos/
        candidates = [
            f for f in all_files
            if '/geos/' in f and f.endswith('.html')
            and os.path.splitext(os.path.basename(f))[0].lower() == SAMPLE_COUNTRY
        ]
        if not candidates:
            # Try without geos/ path
            candidates = [
                f for f in all_files
                if f.endswith('.html')
                and os.path.splitext(os.path.basename(f))[0].lower() == SAMPLE_COUNTRY
            ]
        if not candidates:
            print(f"  No {SAMPLE_COUNTRY}.html found in {year} zip!")
            print(f"  Available HTML files (first 20):")
            html_files = [f for f in all_files if f.endswith('.html')][:20]
            for hf in html_files:
                print(f"    {hf}")
            return None

        html_bytes = zf.read(candidates[0])
        with open(out_path, 'wb') as f:
            f.write(html_bytes)
        print(f"  Extracted: {candidates[0]} -> {out_path} ({len(html_bytes):,} bytes)")

    return out_path


def analyze_structure(html_path, year, label):
    """Analyze HTML structure and print detailed report."""
    with open(html_path, 'r', encoding='utf-8', errors='replace') as f:
        html = f.read()

    soup = BeautifulSoup(html, 'html.parser')

    print(f"\n{'='*70}")
    print(f"  YEAR {year} — {label}")
    print(f"{'='*70}")
    print(f"  File size: {len(html):,} bytes")

    # ---- Key structural markers ----
    print(f"\n  KEY MARKERS:")
    markers = [
        ('<a name=', html.count('<a name=')),
        ('<a id=', html.count('<a id=')),
        ('class="category"', html.count('class="category"')),
        ('class="category_data"', html.count('class="category_data"')),
        ('CollapsiblePanel', html.count('CollapsiblePanel')),
        ('field-anchor', html.count('field-anchor')),
        ('-category-section-anchor', html.count('-category-section-anchor')),
        ('<b>', html.count('<b>')),
        ('<td', html.count('<td')),
        ('class="fl_region"', html.count('class="fl_region"')),
    ]
    for marker, count in markers:
        flag = " <---" if count > 0 else ""
        print(f"    {marker:<45} {count:>5}{flag}")

    # ---- Anchor elements ----
    anchors_name = soup.find_all('a', attrs={'name': True})
    if anchors_name:
        print(f"\n  <a name=...> ANCHORS ({len(anchors_name)}):")
        for a in anchors_name[:15]:
            text = a.get_text()[:60].strip()
            print(f"    name=\"{a.get('name')}\"  text=\"{text}\"")
        if len(anchors_name) > 15:
            print(f"    ... and {len(anchors_name) - 15} more")

    anchors_id = soup.find_all('a', id=True)
    if anchors_id:
        print(f"\n  <a id=...> ANCHORS ({len(anchors_id)}):")
        for a in anchors_id[:15]:
            text = a.get_text()[:60].strip()
            print(f"    id=\"{a.get('id')}\"  text=\"{text}\"")

    # ---- CSS classes ----
    classes = Counter()
    for tag in soup.find_all(True):
        for cls in tag.get('class', []):
            classes[cls] += 1
    if classes:
        print(f"\n  TOP 25 CSS CLASSES:")
        for cls, count in classes.most_common(25):
            print(f"    {cls:<40} {count:>5}")

    # ---- ID attributes (sample) ----
    ids = [tag.get('id') for tag in soup.find_all(id=True)]
    if ids:
        print(f"\n  SAMPLE IDs (first 20 of {len(ids)}):")
        for id_val in ids[:20]:
            print(f"    {id_val}")

    # ---- Bold tags (potential field names) ----
    bold_tags = soup.find_all('b')
    field_like = [b.get_text().strip() for b in bold_tags if b.get_text().strip().endswith(':')]
    if field_like:
        print(f"\n  <b>FieldName:</b> PATTERNS ({len(field_like)}):")
        for fn in field_like[:20]:
            print(f"    {fn}")
        if len(field_like) > 20:
            print(f"    ... and {len(field_like) - 20} more")

    # ---- Category spans ----
    cat_spans = soup.find_all('span', class_='category')
    if cat_spans:
        print(f"\n  <span class=\"category\"> ({len(cat_spans)}):")
        for cs in cat_spans[:15]:
            print(f"    \"{cs.get_text()[:80].strip()}\"")

    # ---- Run current parser ----
    print(f"\n  CURRENT PARSER RESULT:")
    fmt = ba.detect_format(html)
    name, categories = ba.parse_country_html(html)
    total_fields = sum(len(fields) for _, fields in categories)
    fell_back = (len(categories) == 1 and categories[0][0] == 'Full Content')

    print(f"    Format detected: {fmt}")
    print(f"    Country name: {name}")
    print(f"    Categories: {len(categories)}")
    print(f"    Total fields: {total_fields}")
    print(f"    Fell back to 'Full Content': {fell_back}")

    if not fell_back:
        print(f"\n    Categories found:")
        for cat_name, fields in categories[:8]:
            print(f"      [{len(fields)} fields] {cat_name}")
            for fn, fc in fields[:3]:
                preview = fc[:80].replace('\n', ' ')
                print(f"        {fn}: {preview}...")
    else:
        # Show a snippet of what the Full Content looks like
        if categories:
            text = categories[0][1][0][1][:500] if categories[0][1] else ""
            print(f"\n    Full Content preview (first 500 chars):")
            print(f"    {text[:500]}")

    # ---- Summary line ----
    status = "OK" if not fell_back and total_fields > 10 else "BROKEN"
    if total_fields > 50000:
        status = "OVER-PARSED"
    print(f"\n  >>> STATUS: {status} ({total_fields} fields)")


def main():
    print("=" * 70)
    print("CIA FACTBOOK - HTML PARSER DIAGNOSTIC")
    print("=" * 70)
    print(f"Downloading samples for {len(SAMPLE_YEARS)} years...")
    print(f"Output directory: {SAMPLE_DIR}\n")

    for year, label in SAMPLE_YEARS:
        print(f"\n{'#'*70}")
        print(f"# Year {year} — {label}")
        print(f"{'#'*70}")

        path = download_and_extract(year)
        if path:
            analyze_structure(path, year, label)
        else:
            print(f"  SKIPPED: Could not get HTML for {year}")

    # Summary
    print(f"\n\n{'='*70}")
    print("DIAGNOSTIC SUMMARY")
    print(f"{'='*70}")
    print(f"HTML files saved to: {SAMPLE_DIR}")
    print("Compare the working vs broken files to determine what changed.")
    print("\nNext step: Based on the output above, we'll write the fixed parsers.")


if __name__ == '__main__':
    main()
