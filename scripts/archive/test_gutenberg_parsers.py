"""Quick test of the Gutenberg parsers against downloaded text samples."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import load_gutenberg_years as lg

TEXT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "text_samples")

TESTS = [
    (1990, 'old'),
    (1991, 'tagged'),
    (1992, 'colon'),
    (1993, 'asterisk'),
    (1994, 'asterisk'),
    (1995, 'atsign'),
    (1996, 'atsign_bare'),
    (1999, 'atsign_bare'),
    (2001, 'equals'),
]

for year, fmt in TESTS:
    path = os.path.join(TEXT_DIR, f"{year}.txt")
    if not os.path.exists(path):
        print(f"SKIP: {year}.txt not found")
        continue

    with open(path, 'r', encoding='utf-8', errors='replace') as f:
        raw = f.read()

    text = lg.strip_pg_wrapper(raw)

    if fmt == 'old':
        countries = lg.parse_old_format(text)
    elif fmt == 'tagged':
        countries = lg.parse_tagged_format(text)
    elif fmt == 'colon':
        countries = lg.parse_colon_format(text)
    elif fmt == 'asterisk':
        countries = lg.parse_asterisk_format(text)
    elif fmt == 'atsign':
        countries = lg.parse_atsign_format(text)
    elif fmt == 'atsign_bare':
        countries = lg.parse_atsign_bare_format(text)
    elif fmt == 'equals':
        countries = lg.parse_equals_format(text)

    total_fields = sum(len(f) for _, cats in countries for _, f in cats)
    total_cats = sum(len(cats) for _, cats in countries)

    print(f"\n{'=' * 60}")
    print(f"  {year} ({fmt})")
    print(f"{'=' * 60}")
    print(f"  Countries: {len(countries)}")
    print(f"  Categories: {total_cats}")
    print(f"  Total fields: {total_fields}")
    print(f"  Avg cats/country: {total_cats / max(len(countries), 1):.1f}")
    print(f"  Avg fields/country: {total_fields / max(len(countries), 1):.1f}")

    # Show first 3 countries
    for cname, cats in countries[:3]:
        print(f"\n  {cname}: {len(cats)} categories")
        for cat_name, fields in cats[:2]:
            print(f"    [{len(fields)} fields] {cat_name}")
            for fn, fv in fields[:2]:
                preview = fv[:80].replace('\n', ' ')
                print(f"      {fn}: {preview}...")

    # Show last country to verify we got them all
    if countries:
        last_name = countries[-1][0]
        last_cats = len(countries[-1][1])
        print(f"\n  Last country: {last_name} ({last_cats} categories)")

    status = "PASS" if len(countries) > 180 and total_fields > 3000 else "FAIL"
    print(f"\n  >>> {status} ({len(countries)} countries, {total_fields:,} fields)")
