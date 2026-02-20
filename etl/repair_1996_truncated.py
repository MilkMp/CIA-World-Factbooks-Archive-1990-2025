"""
Repair 1996 truncated countries using CIA's original text file.
================================================================
The Project Gutenberg edition (ebook #27675) of the 1996 CIA World Factbook
is truncated for 7 sovereign countries. The CIA's own text file (wfb-96.txt)
downloaded from the Wayback Machine has the complete data.

This script:
1. Parses the CIA original text for the 7 affected countries
2. Deletes their existing truncated data from the SQLite database
3. Inserts the complete parsed data

Source: https://web.archive.org/web/19970528151800id_/http://www.odci.gov:80/cia/publications/nsolo/wfb-96.txt.gz

Usage:
  python repair_1996_truncated.py              # Repair all 7 countries
  python repair_1996_truncated.py --dry-run    # Preview without DB changes
"""
import sqlite3
import re
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
DB_PATH = os.path.join(PROJECT_DIR, "data", "factbook.db")
CIA_TEXT = os.path.join(PROJECT_DIR, "samples", "text_samples", "1996_cia_original.txt")

TRUNCATED_COUNTRIES = [
    "Venezuela", "Armenia", "Greece", "Luxembourg",
    "Malta", "Monaco", "Tuvalu",
]

SECTION_NAMES = {
    'Geography', 'People', 'Government', 'Economy', 'Communications',
    'Transportation', 'Defense Forces', 'Transnational Issues',
}


def parse_cia_original(text):
    """Parse the CIA original page-header format into country entries."""
    lines = text.split('\n')
    page_re = re.compile(
        r'^\d{2}/\d{2}/\d{2}\s+FACTBOOK COUNTRY REPORT\s+Page\s+\d+\s*$'
    )

    entries = {}
    current_country = None
    current_section = None
    current_lines = []

    for i, line in enumerate(lines):
        if page_re.match(line):
            for j in range(i + 1, min(i + 4, len(lines))):
                stripped = lines[j].strip()
                if stripped:
                    current_country = stripped
                    break
            continue

        if current_country is None:
            continue

        stripped = line.strip()

        # Centered section header: heavily indented, matches known section
        if stripped in SECTION_NAMES and len(line) > 10 and line[0] == ' ':
            if current_section and current_lines:
                if current_country not in entries:
                    entries[current_country] = []
                entries[current_country].append(
                    (current_section, '\n'.join(current_lines))
                )
            current_section = stripped
            current_lines = []
            continue

        # Skip centered country name repetitions on page breaks
        if stripped == current_country:
            indent = len(line) - len(line.lstrip())
            if indent > 20:
                continue

        if current_section:
            current_lines.append(line)

    # Save last section
    if current_section and current_lines and current_country:
        if current_country not in entries:
            entries[current_country] = []
        entries[current_country].append(
            (current_section, '\n'.join(current_lines))
        )

    return entries


def extract_cia_fields(section_text):
    """Extract field name/value pairs from a CIA section block.

    Format:
        FieldName:            (5-space indent, capital start, colon)
             value text        (10-space indent)
        sub_field:             (5-space indent, lowercase start)
             value text
    """
    fields = []
    current_name = None
    current_parts = []

    for line in section_text.split('\n'):
        stripped = line.strip()
        if not stripped:
            continue

        indent = len(line) - len(line.lstrip())

        # Top-level field: 3-7 space indent, capital start, colon
        field_match = re.match(
            r"^\s{3,7}([A-Z][\w\s\-,()\/\.']+?):\s*(.*)", line
        )
        if field_match:
            fname = field_match.group(1).strip()
            fval = field_match.group(2).strip()
            if current_name:
                val = ' '.join(current_parts).strip()
                if val:
                    fields.append((current_name, val))
            current_name = fname
            current_parts = [fval] if fval else []
            continue

        # Sub-field: 3-7 space indent, lowercase start, colon
        sub_match = re.match(
            r"^\s{3,7}([a-z][\w\s\-,()\/\.']*?):\s*(.*)", line
        )
        if sub_match and current_name:
            sub_name = sub_match.group(1).strip()
            sub_val = sub_match.group(2).strip()
            if sub_val:
                current_parts.append(f"{sub_name}: {sub_val}")
            else:
                current_parts.append(f"{sub_name}:")
            continue

        # Value continuation: 8+ space indent
        if indent >= 8 and current_name:
            current_parts.append(stripped)
            continue

        # Other content
        if current_name and stripped:
            current_parts.append(stripped)

    if current_name:
        val = ' '.join(current_parts).strip()
        if val:
            fields.append((current_name, val))

    return fields


def main():
    dry_run = '--dry-run' in sys.argv

    if not os.path.exists(CIA_TEXT):
        print(f"ERROR: CIA original text not found at {CIA_TEXT}")
        print("Download it first with the Wayback Machine URL.")
        return 1

    if not os.path.exists(DB_PATH):
        print(f"ERROR: Database not found at {DB_PATH}")
        return 1

    print("=" * 60)
    print("REPAIR 1996 TRUNCATED COUNTRIES")
    print("=" * 60)
    if dry_run:
        print("MODE: DRY RUN (no database changes)\n")

    # Parse CIA original text
    print("Parsing CIA original text...")
    with open(CIA_TEXT, 'r', encoding='utf-8', errors='replace') as f:
        text = f.read()

    entries = parse_cia_original(text)
    print(f"  Parsed {len(entries)} countries from CIA original\n")

    # Connect to database
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    cursor = db.cursor()

    results = []

    for country_name in TRUNCATED_COUNTRIES:
        print(f"--- {country_name} ---")

        # Find in CIA original
        if country_name not in entries:
            print(f"  WARNING: {country_name} not found in CIA original text")
            results.append((country_name, "NOT FOUND", 0, 0))
            continue

        sections = entries[country_name]
        section_names = [s[0] for s in sections]
        new_fields = []
        for sname, stext in sections:
            fields = extract_cia_fields(stext)
            new_fields.append((sname, fields))

        total_new = sum(len(f) for _, f in new_fields)
        print(f"  CIA original: {len(sections)} sections {section_names}, "
              f"{total_new} fields")

        # Find existing country in DB
        row = cursor.execute("""
            SELECT c.CountryID, c.Code, c.MasterCountryID,
                   COUNT(cf.FieldID) as old_count
            FROM Countries c
            LEFT JOIN CountryFields cf ON cf.CountryID = c.CountryID
            WHERE c.Year = 1996 AND c.Name = ?
            GROUP BY c.CountryID
        """, [country_name]).fetchone()

        if not row:
            # Try matching via MasterCountries
            row = cursor.execute("""
                SELECT c.CountryID, c.Code, c.MasterCountryID,
                       COUNT(cf.FieldID) as old_count
                FROM Countries c
                LEFT JOIN CountryFields cf ON cf.CountryID = c.CountryID
                JOIN MasterCountries mc ON c.MasterCountryID = mc.MasterCountryID
                WHERE c.Year = 1996 AND mc.CanonicalName = ?
                GROUP BY c.CountryID
            """, [country_name]).fetchone()

        if not row:
            print(f"  WARNING: {country_name} not found in DB for 1996")
            results.append((country_name, "NOT IN DB", 0, total_new))
            continue

        country_id = row['CountryID']
        old_count = row['old_count']
        master_id = row['MasterCountryID']
        code = row['Code']
        print(f"  Current DB: CountryID={country_id}, {old_count} fields")

        if dry_run:
            print(f"  Would replace {old_count} fields with {total_new} fields")
            results.append((country_name, "DRY RUN", old_count, total_new))
            continue

        # Delete existing fields and categories
        cursor.execute(
            "DELETE FROM CountryFields WHERE CountryID = ?", [country_id]
        )
        cursor.execute(
            "DELETE FROM CountryCategories WHERE CountryID = ?", [country_id]
        )

        # Insert new categories and fields
        for cat_title, fields in new_fields:
            cursor.execute(
                "INSERT INTO CountryCategories (CountryID, CategoryTitle) "
                "VALUES (?, ?)",
                [country_id, cat_title[:200]]
            )
            cat_id = cursor.lastrowid

            for fname, content in fields:
                cursor.execute(
                    "INSERT INTO CountryFields "
                    "(CategoryID, CountryID, FieldName, Content) "
                    "VALUES (?, ?, ?, ?)",
                    [cat_id, country_id, fname[:200], content]
                )

        db.commit()
        print(f"  Replaced {old_count} fields -> {total_new} fields")
        results.append((country_name, "OK", old_count, total_new))

    # Summary
    print(f"\n{'=' * 60}")
    print("REPAIR SUMMARY")
    print(f"{'=' * 60}")
    print(f"{'Country':<20} {'Status':<12} {'Before':>8} {'After':>8}")
    print("-" * 52)
    for name, status, before, after in results:
        print(f"{name:<20} {status:<12} {before:>8} {after:>8}")

    # Verify
    if not dry_run:
        print(f"\nVerification:")
        for country_name in TRUNCATED_COUNTRIES:
            row = cursor.execute("""
                SELECT COUNT(cf.FieldID) as cnt
                FROM CountryFields cf
                JOIN Countries c ON cf.CountryID = c.CountryID
                JOIN MasterCountries mc ON c.MasterCountryID = mc.MasterCountryID
                WHERE c.Year = 1996 AND mc.CanonicalName = ?
            """, [country_name]).fetchone()
            print(f"  {country_name}: {row['cnt']} fields")

    db.close()
    print("\nDone.")
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
