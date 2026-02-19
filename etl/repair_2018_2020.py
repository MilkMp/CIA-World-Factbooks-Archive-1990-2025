"""
Repair script: re-parse 2018-2020 HTML factbooks with fixed parser.

The original parse_modern_format() only captured text inside specific
<span> classes (subfield-name, subfield-number, subfield-note) but missed
loose text nodes — causing fields like "Ports and terminals" to lose their
values (e.g., "major seaport(s):" without "Pago Pago").

This script:
  1. Downloads 2018-2020 factbook zips from the Wayback Machine
  2. Re-parses every country HTML with the fixed parser
  3. Updates CountryFields.Content in the SQLite database
"""

import os
import re
import sys
import zipfile
import sqlite3
import urllib.request

# ── Paths ──
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(PROJECT_ROOT, "data", "factbook.db")
WORK_DIR = os.path.join(PROJECT_ROOT, "etl", "work")

# Import parsers from build_archive
sys.path.insert(0, os.path.join(PROJECT_ROOT, "etl"))
from build_archive import (
    parse_country_html,
    download_zip,
    WAYBACK_TIMESTAMPS,
)

YEARS = [2018, 2019, 2020]


def get_country_files(zip_path):
    """Extract list of country HTML files from a zip."""
    with zipfile.ZipFile(zip_path) as zf:
        all_files = zf.namelist()
        geos = sorted([f for f in all_files if '/geos/' in f and f.endswith('.html')])

        seen_codes = set()
        unique = []
        skip = ['template', 'print', 'summary', 'notes', 'appendix', 'index', 'wfb']
        for g in geos:
            code = os.path.splitext(os.path.basename(g))[0].lower()
            if len(code) > 5:
                continue
            if any(p in code for p in skip):
                continue
            if code not in seen_codes:
                seen_codes.add(code)
                unique.append(g)
    return unique


def repair_year(db, year, zip_path):
    """Re-parse all countries for a year and update the DB."""
    cursor = db.cursor()

    # Get existing country records for this year
    existing = cursor.execute(
        "SELECT CountryID, Code FROM Countries WHERE Year = ?", (year,)
    ).fetchall()
    code_to_id = {row[1]: row[0] for row in existing}
    print(f"\n{'='*60}")
    print(f"  Year {year}: {len(code_to_id)} countries in DB")

    # Get category mapping: CountryID -> {CategoryTitle: CategoryID}
    cat_map = {}
    for cid in code_to_id.values():
        cats = cursor.execute(
            "SELECT CategoryID, CategoryTitle FROM CountryCategories WHERE CountryID = ?",
            (cid,),
        ).fetchall()
        cat_map[cid] = {row[1]: row[0] for row in cats}

    geo_files = get_country_files(zip_path)
    print(f"  {len(geo_files)} country files in zip")

    updated = 0
    skipped = 0
    new_fields = 0
    errors = 0

    with zipfile.ZipFile(zip_path) as zf:
        for gf in geo_files:
            code = os.path.splitext(os.path.basename(gf))[0].lower()
            country_id = code_to_id.get(code)

            if not country_id:
                skipped += 1
                continue

            try:
                html = zf.read(gf).decode('utf-8', errors='replace')
                name, categories = parse_country_html(html, year)

                # Delete existing fields for this country
                cursor.execute(
                    "DELETE FROM CountryFields WHERE CountryID = ?",
                    (country_id,),
                )

                # Also delete old categories and recreate
                cursor.execute(
                    "DELETE FROM CountryCategories WHERE CountryID = ?",
                    (country_id,),
                )

                # Insert re-parsed categories and fields
                for cat_title, fields in categories:
                    cursor.execute(
                        "INSERT INTO CountryCategories (CountryID, CategoryTitle) VALUES (?, ?)",
                        (country_id, cat_title[:200]),
                    )
                    cat_id = cursor.lastrowid

                    for fname, content in fields:
                        cursor.execute(
                            "INSERT INTO CountryFields (CategoryID, CountryID, FieldName, Content) VALUES (?, ?, ?, ?)",
                            (cat_id, country_id, fname[:200], content),
                        )
                        new_fields += 1

                updated += 1

            except Exception as e:
                print(f"    ERROR [{code}]: {e}")
                errors += 1

    db.commit()
    print(f"  Updated: {updated}, Skipped: {skipped}, Errors: {errors}")
    print(f"  Total fields inserted: {new_fields}")
    return updated, errors


def verify_repair(db):
    """Spot-check a few known-bad fields."""
    cursor = db.cursor()
    print(f"\n{'='*60}")
    print("  VERIFICATION")
    print(f"{'='*60}")

    checks = [
        ("AS", 2018, "Ports and terminals", "Pago Pago"),
        ("AS", 2019, "Ports and terminals", "Pago Pago"),
        ("AS", 2020, "Ports and terminals", "Pago Pago"),
        ("US", 2018, "Ports and terminals", "Long Beach"),
        ("US", 2018, "Exports", "est."),
    ]

    all_ok = True
    for iso2, year, field_like, expected_substr in checks:
        row = cursor.execute("""
            SELECT cf.Content
            FROM CountryFields cf
            JOIN Countries c ON cf.CountryID = c.CountryID
            JOIN MasterCountries mc ON c.MasterCountryID = mc.MasterCountryID
            WHERE mc.ISOAlpha2 = ? AND c.Year = ? AND cf.FieldName LIKE ?
            LIMIT 1
        """, (iso2, year, f"%{field_like}%")).fetchone()

        if row and expected_substr in row[0]:
            print(f"  OK   {iso2}/{year}/{field_like}: found '{expected_substr}'")
        else:
            content = row[0][:80] if row else "<NOT FOUND>"
            print(f"  FAIL {iso2}/{year}/{field_like}: expected '{expected_substr}' in '{content}'")
            all_ok = False

    return all_ok


def main():
    print("=== Repair 2018-2020 Factbook Data ===")
    print(f"  DB: {DB_PATH}")

    # Backup
    backup_path = DB_PATH + ".backup_before_repair"
    if not os.path.exists(backup_path):
        import shutil
        shutil.copy2(DB_PATH, backup_path)
        print(f"  Backup: {backup_path}")
    else:
        print(f"  Backup already exists: {backup_path}")

    db = sqlite3.connect(DB_PATH)

    for year in YEARS:
        print(f"\n  Downloading {year} zip...")
        zip_path = download_zip(year)
        if not zip_path:
            print(f"  FAILED to download {year} zip — skipping")
            continue
        repair_year(db, year, zip_path)

    ok = verify_repair(db)
    db.close()

    if ok:
        print("\n  All verification checks passed.")
    else:
        print("\n  Some checks FAILED — review output above.")

    print("\nDone.")


if __name__ == "__main__":
    main()
