"""Quick test of the fixed parsers against saved HTML samples."""
import os
from bs4 import BeautifulSoup
import repair_broken_years as repair
import build_archive as ba

SAMPLE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "html_samples")

TESTS = [
    ("2000_us.html", None, "classic (original, should still work)"),
    ("2003_us.html", "table", "table format (2001-2008 fix)"),
    ("2008_us.html", "table", "table format (2008 fix)"),
    ("2016_us.html", "expandcollapse", "expand/collapse (2015-2017 fix)"),
]

for filename, fix_type, label in TESTS:
    path = os.path.join(SAMPLE_DIR, filename)
    if not os.path.exists(path):
        print(f"SKIP: {filename} not found")
        continue

    with open(path, 'r', encoding='utf-8', errors='replace') as f:
        html = f.read()

    if fix_type:
        name, categories = repair.parse_country_fixed(html, fix_type)
    else:
        name, categories = ba.parse_country_html(html)

    total_fields = sum(len(fields) for _, fields in categories)
    fell_back = len(categories) == 1 and categories[0][0] == 'Full Content'

    print(f"\n{'='*60}")
    print(f"  {filename} — {label}")
    print(f"{'='*60}")
    print(f"  Name: {name}")
    print(f"  Categories: {len(categories)}")
    print(f"  Total fields: {total_fields}")
    print(f"  Fell back: {fell_back}")

    if fell_back:
        print(f"  >>> FAILED — still falling back to Full Content!")
    else:
        for cat_name, fields in categories[:5]:
            print(f"\n  [{len(fields)} fields] {cat_name}")
            for fn, fc in fields[:3]:
                preview = fc[:100].replace('\n', ' ')
                print(f"    {fn}: {preview}...")
        if len(categories) > 5:
            print(f"\n  ... and {len(categories) - 5} more categories")

    status = "PASS" if not fell_back and total_fields > 10 else "FAIL"
    print(f"\n  >>> {status} ({total_fields} fields)")
