"""
Build StarDict dictionaries from CIA World Factbook SQLite databases.

Generates two editions per year (1990-2025):
  - General:    Full field text grouped by category
  - Structured: Parsed numeric sub-values with units

Output: data/stardict/<dict-name>/{.ifo, .idx, .dict.dz, .syn}

Usage:
    python etl/stardict/build_stardict.py
    python etl/stardict/build_stardict.py --years 2025
    python etl/stardict/build_stardict.py --editions general --no-compress
"""

import argparse
import html
import os
import sqlite3
import sys
import time
from collections import OrderedDict

# ── Paths ───────────────────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "..", ".."))
GENERAL_DB = os.path.join(PROJECT_ROOT, "data", "factbook.db")
STRUCTURED_DB = os.path.join(PROJECT_ROOT, "data", "factbook_field_values.db")
DEFAULT_OUTPUT = os.path.join(PROJECT_ROOT, "data", "stardict")

ALL_YEARS = list(range(1990, 2026))

# ── SQL ─────────────────────────────────────────────────────────────
MASTER_QUERY = """
    SELECT MasterCountryID, CanonicalName, ISOAlpha2, CanonicalCode
    FROM MasterCountries
"""

GENERAL_QUERY = """
    SELECT mc.MasterCountryID, mc.CanonicalName,
           cc.CategoryTitle, cf.FieldName, cf.Content,
           cc.CategoryID, cf.FieldID
    FROM Countries co
    JOIN MasterCountries mc ON co.MasterCountryID = mc.MasterCountryID
    JOIN CountryCategories cc ON co.CountryID = cc.CountryID
    JOIN CountryFields cf ON cc.CategoryID = cf.CategoryID
                          AND cf.CountryID = co.CountryID
    WHERE co.Year = ?
    ORDER BY mc.MasterCountryID, cc.CategoryID, cf.FieldID
"""

STRUCTURED_QUERY = """
    SELECT mc.MasterCountryID, mc.CanonicalName,
           cc.CategoryTitle, cf.FieldName,
           fv.SubField, fv.NumericVal, fv.Units, fv.TextVal,
           cc.CategoryID, cf.FieldID, fv.ValueID
    FROM Countries co
    JOIN MasterCountries mc ON co.MasterCountryID = mc.MasterCountryID
    JOIN CountryFields cf ON co.CountryID = cf.CountryID
    JOIN CountryCategories cc ON cf.CategoryID = cc.CategoryID
    JOIN FieldValues fv ON cf.FieldID = fv.FieldID
    WHERE co.Year = ?
    ORDER BY mc.MasterCountryID, cc.CategoryID, cf.FieldID, fv.ValueID
"""


# ── Helpers ─────────────────────────────────────────────────────────
def esc(text):
    """HTML-escape with control-character stripping."""
    if not text:
        return ""
    cleaned = "".join(c for c in text if ord(c) >= 32 or c in "\n\r\t")
    return html.escape(cleaned, quote=False)


def build_headwords(name, iso, fips):
    """Primary headword + ISO/FIPS synonyms."""
    words = [name]
    if iso:
        words.append(iso)
    if fips and fips != iso:
        words.append(fips)
    return words


def format_numeric(val, units):
    """Format a numeric value with optional units."""
    if val is None:
        return None
    if val == int(val):
        formatted = f"{int(val):,}"
    else:
        # Trim trailing zeros: 80.90 -> 80.9, 3.00 -> 3
        formatted = f"{val:,.4f}".rstrip("0").rstrip(".")
    if units:
        return f"{formatted} {esc(units)}"
    return formatted


# ── Entry builders ──────────────────────────────────────────────────
def build_general_html(rows):
    """Build HTML from General query rows for one country.

    rows: [(CategoryTitle, FieldName, Content, CategoryID, FieldID), ...]
    """
    parts = []
    cur_cat = None
    for cat, field, content, _cid, _fid in rows:
        if not content or not content.strip():
            continue
        if cat != cur_cat:
            cur_cat = cat
            parts.append(f"<h3>{esc(cat)}</h3>")
        parts.append(f"<b>{esc(field)}</b>: {esc(content)}<br>")
    return "\n".join(parts)


def build_structured_html(rows):
    """Build HTML from Structured query rows for one country.

    rows: [(CategoryTitle, FieldName, SubField, NumericVal, Units, TextVal,
            CategoryID, FieldID, ValueID), ...]
    """
    parts = []
    cur_cat = None
    cur_field = None
    for cat, field, subfield, numval, units, textval, _cid, _fid, _vid in rows:
        if cat != cur_cat:
            cur_cat = cat
            cur_field = None
            parts.append(f"<h3>{esc(cat)}</h3>")
        if field != cur_field:
            cur_field = field
            parts.append(f"<b>{esc(field)}</b><br>")
        # Format value
        val_str = format_numeric(numval, units)
        if val_str is None and textval:
            val_str = esc(textval[:500]) + ("..." if len(textval) > 500 else "")
        if val_str:
            parts.append(f"&nbsp;&nbsp;{esc(subfield)}: {val_str}<br>")
    return "\n".join(parts)


# ── Dictionary writer ───────────────────────────────────────────────
def write_stardict(entries, year, edition, output_dir, dictzip=True):
    """Write a StarDict dictionary via PyGlossary.

    entries: [(headwords_list, html_str), ...]
    Returns: path to .ifo file, or None on error.
    """
    from pyglossary.glossary_v2 import Glossary

    dict_name = f"cia-factbook-{year}-{edition}"
    dict_dir = os.path.join(output_dir, dict_name)
    os.makedirs(dict_dir, exist_ok=True)
    ifo_path = os.path.join(dict_dir, f"{dict_name}.ifo")

    glos = Glossary()
    glos.setInfo("title", f"CIA World Factbook {year} ({edition.title()})")
    glos.setInfo("author", "Central Intelligence Agency")
    glos.setInfo(
        "description",
        f"CIA World Factbook {year} - {edition.title()} edition. "
        f"{len(entries)} countries/territories. "
        f"Source: worldfactbookarchive.org",
    )
    glos.setInfo("website", "https://worldfactbookarchive.org/")
    glos.setInfo("date", str(year))

    for headwords, definition in entries:
        entry = glos.newEntry(word=headwords, defi=definition, defiFormat="h")
        glos.addEntry(entry)

    glos.write(
        ifo_path,
        formatName="Stardict",
        dictzip=dictzip,
        sametypesequence="h",
    )
    return ifo_path


# ── Year builders ───────────────────────────────────────────────────
def build_general_dict(db, master, year, output_dir, dictzip):
    """Build General edition for one year. Returns entry count or 0."""
    t0 = time.time()
    rows = db.execute(GENERAL_QUERY, (year,)).fetchall()
    if not rows:
        print(f"  {year} general:     SKIP (no data)")
        return 0

    # Group by MasterCountryID
    grouped = OrderedDict()
    for mcid, _name, cat, field, content, cid, fid in rows:
        grouped.setdefault(mcid, []).append((cat, field, content, cid, fid))

    entries = []
    for mcid, country_rows in grouped.items():
        info = master.get(mcid)
        if not info:
            continue
        name, iso, fips = info
        headwords = build_headwords(name, iso, fips)
        body = build_general_html(country_rows)
        if body.strip():
            entries.append((headwords, body))

    if not entries:
        print(f"  {year} general:     SKIP (0 entries)")
        return 0

    write_stardict(entries, year, "general", output_dir, dictzip)
    elapsed = time.time() - t0
    print(f"  {year} general:     {len(entries):>3} entries ({elapsed:.1f}s)")
    return len(entries)


def build_structured_dict(db, master, year, output_dir, dictzip):
    """Build Structured edition for one year. Returns entry count or 0."""
    t0 = time.time()
    rows = db.execute(STRUCTURED_QUERY, (year,)).fetchall()
    if not rows:
        print(f"  {year} structured:  SKIP (no data)")
        return 0

    # Group by MasterCountryID
    grouped = OrderedDict()
    for mcid, _name, cat, field, sub, numval, units, textval, cid, fid, vid in rows:
        grouped.setdefault(mcid, []).append(
            (cat, field, sub, numval, units, textval, cid, fid, vid)
        )

    entries = []
    for mcid, country_rows in grouped.items():
        info = master.get(mcid)
        if not info:
            continue
        name, iso, fips = info
        headwords = build_headwords(name, iso, fips)
        body = build_structured_html(country_rows)
        if body.strip():
            entries.append((headwords, body))

    if not entries:
        print(f"  {year} structured:  SKIP (0 entries)")
        return 0

    write_stardict(entries, year, "structured", output_dir, dictzip)
    elapsed = time.time() - t0
    print(f"  {year} structured:  {len(entries):>3} entries ({elapsed:.1f}s)")
    return len(entries)


# ── Validation ──────────────────────────────────────────────────────
def validate_output(output_dir, years, editions):
    """Check all expected files exist and print summary."""
    print("\nValidation:")
    expected = 0
    found = 0
    total_size = 0
    issues = []

    for year in years:
        for edition in editions:
            expected += 1
            name = f"cia-factbook-{year}-{edition}"
            d = os.path.join(output_dir, name)
            ifo = os.path.join(d, f"{name}.ifo")
            idx = os.path.join(d, f"{name}.idx")
            dictf = os.path.join(d, f"{name}.dict.dz")
            if not os.path.exists(dictf):
                dictf = os.path.join(d, f"{name}.dict")

            ok = True
            for f in [ifo, idx, dictf]:
                if os.path.exists(f):
                    total_size += os.path.getsize(f)
                else:
                    ok = False
                    issues.append(f"Missing: {os.path.basename(f)}")
            syn = os.path.join(d, f"{name}.syn")
            if os.path.exists(syn):
                total_size += os.path.getsize(syn)

            if ok:
                found += 1

    print(f"  Dictionaries: {found}/{expected}")
    print(f"  Total size:   {total_size / (1024 * 1024):.1f} MB")
    if issues:
        print(f"  Issues ({len(issues)}):")
        for i in issues[:10]:
            print(f"    {i}")
    else:
        print("  All files present.")

    # Spot-check: show .ifo content for latest year
    latest = years[-1]
    ifo = os.path.join(
        output_dir,
        f"cia-factbook-{latest}-general",
        f"cia-factbook-{latest}-general.ifo",
    )
    if os.path.exists(ifo):
        print(f"\n  Spot-check ({latest} general .ifo):")
        with open(ifo, "r", encoding="utf-8") as f:
            for line in f.read().strip().split("\n"):
                print(f"    {line}")


# ── Main ────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="Build StarDict dictionaries from CIA Factbook databases."
    )
    parser.add_argument(
        "--output-dir", default=DEFAULT_OUTPUT, help="Output directory"
    )
    parser.add_argument(
        "--years", type=int, nargs="+", help="Years to build (default: all 1990-2025)"
    )
    parser.add_argument(
        "--editions",
        nargs="+",
        choices=["general", "structured"],
        help="Editions to build (default: both)",
    )
    parser.add_argument(
        "--no-compress",
        action="store_true",
        help="Skip dictzip compression (larger .dict files)",
    )
    args = parser.parse_args()

    years = args.years or ALL_YEARS
    editions = args.editions or ["general", "structured"]
    dictzip = not args.no_compress

    # Check pyglossary
    try:
        from pyglossary.glossary_v2 import Glossary

        Glossary.init()
    except ImportError:
        print("ERROR: pyglossary not installed. Run: pip install pyglossary")
        sys.exit(1)

    # Check databases
    need_general = "general" in editions
    need_structured = "structured" in editions

    if need_general and not os.path.exists(GENERAL_DB):
        print(f"ERROR: General DB not found: {GENERAL_DB}")
        sys.exit(1)
    if need_structured and not os.path.exists(STRUCTURED_DB):
        print(f"ERROR: Structured DB not found: {STRUCTURED_DB}")
        sys.exit(1)

    os.makedirs(args.output_dir, exist_ok=True)

    # Print header
    total = len(years) * len(editions)
    print(f"Building {total} StarDict dictionaries...")
    if need_general:
        size = os.path.getsize(GENERAL_DB) / (1024 * 1024)
        print(f"  General DB:    {GENERAL_DB} ({size:.0f} MB)")
    if need_structured:
        size = os.path.getsize(STRUCTURED_DB) / (1024 * 1024)
        print(f"  Structured DB: {STRUCTURED_DB} ({size:.0f} MB)")
    print(f"  Years:         {years[0]}-{years[-1]} ({len(years)} years)")
    print(f"  Editions:      {', '.join(editions)}")
    print(f"  Compression:   {'dictzip' if dictzip else 'none'}")
    print(f"  Output:        {args.output_dir}")
    print()

    t0 = time.time()
    built = 0
    total_entries = 0

    # Open databases (read-only)
    gen_db = None
    struct_db = None
    if need_general:
        gen_db = sqlite3.connect(f"file:{GENERAL_DB}?mode=ro", uri=True)
    if need_structured:
        struct_db = sqlite3.connect(f"file:{STRUCTURED_DB}?mode=ro", uri=True)

    # Load master countries from whichever DB is available
    ref_db = gen_db or struct_db
    master = {}
    for row in ref_db.execute(MASTER_QUERY).fetchall():
        master[row[0]] = (row[1], row[2], row[3])
    print(f"  Loaded {len(master)} master countries\n")

    for year in years:
        if need_general and gen_db:
            try:
                n = build_general_dict(gen_db, master, year, args.output_dir, dictzip)
                if n:
                    built += 1
                    total_entries += n
            except Exception as e:
                print(f"  {year} general:     ERROR: {e}")

        if need_structured and struct_db:
            try:
                n = build_structured_dict(
                    struct_db, master, year, args.output_dir, dictzip
                )
                if n:
                    built += 1
                    total_entries += n
            except Exception as e:
                print(f"  {year} structured:  ERROR: {e}")

    if gen_db:
        gen_db.close()
    if struct_db:
        struct_db.close()

    elapsed = time.time() - t0
    print(f"\nBuilt {built} dictionaries ({total_entries:,} total entries) in {elapsed:.1f}s")

    validate_output(args.output_dir, years, editions)


if __name__ == "__main__":
    main()
