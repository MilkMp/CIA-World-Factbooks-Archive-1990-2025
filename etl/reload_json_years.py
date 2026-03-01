"""
CIA Factbook Archive - Reload JSON Years with Year-Specific Snapshots
=====================================================================
The original load_json_years.py loaded the same JSON snapshot 5 times
for years 2021-2025. This script fixes that by using git history from
the factbook/cache.factbook.json repo to get actual year-end snapshots.

The repo was auto-updated weekly (every Thursday) since August 2021,
so each year has distinct data reflecting that year's Factbook state.

Run:
  python reload_json_years.py                     # Reload all 2021-2025
  python reload_json_years.py --year 2023         # Reload single year
  python reload_json_years.py --dry-run           # Preview without DB writes
"""
import pyodbc
import json
import os
import re
import sys
import subprocess
import glob
import time

CONN_STR = (
    "DRIVER={ODBC Driver 18 for SQL Server};"
    "SERVER=localhost;"
    "DATABASE=CIA_WorldFactbook;"
    "Trusted_Connection=yes;"
    "TrustServerCertificate=yes;"
)

WORK_DIR = r"./work"
REPO_DIR = os.path.join(WORK_DIR, "factbook-json-cache")
REPO_URL = "https://github.com/factbook/cache.factbook.json.git"

# Target years and their cutoff dates for finding year-end commits
YEAR_CUTOFFS = {
    2021: "2022-01-01",
    2022: "2023-01-01",
    2023: "2024-01-01",
    2024: "2025-01-01",
    2025: "2026-02-04",  # CIA discontinued Factbook on Feb 4, 2026
}

# Region directories in the repo
REGION_DIRS = [
    "africa", "antarctica", "australia-oceania", "central-america-n-caribbean",
    "central-asia", "east-n-southeast-asia", "europe", "middle-east",
    "north-america", "oceans", "south-america", "south-asia", "world",
]


def strip_html(text):
    """Remove HTML tags, using pipe delimiters at block-level boundaries."""
    if not text:
        return ""
    s = str(text)
    # Block-level boundaries → pipe
    s = re.sub(r'<br\s*/?\s*>\s*(?:<br\s*/?\s*>)?', ' | ', s, flags=re.IGNORECASE)
    s = re.sub(r'</p>\s*<p[^>]*>', ' | ', s, flags=re.IGNORECASE)
    # Strip remaining tags
    s = re.sub(r'<[^>]+>', ' ', s)
    s = re.sub(r'&[a-zA-Z]+;', ' ', s)
    # Clean whitespace
    s = re.sub(r'\s+', ' ', s).strip()
    # Clean pipe formatting
    s = re.sub(r'(\s*\|\s*)+', ' | ', s)   # collapse runs of pipes
    s = re.sub(r'^\s*\|\s*', '', s)         # strip leading pipe
    s = re.sub(r'\s*\|\s*$', '', s)         # strip trailing pipe
    return s


def ensure_repo():
    """Clone or update the factbook-json-cache repo with full history."""
    os.makedirs(WORK_DIR, exist_ok=True)

    if os.path.exists(os.path.join(REPO_DIR, ".git")):
        print("  Repo exists, fetching latest...")
        subprocess.run(["git", "fetch", "--all"], cwd=REPO_DIR, check=True,
                       capture_output=True)
        return True

    print("  Cloning factbook-json-cache (with full history)...")
    result = subprocess.run(
        ["git", "clone", REPO_URL, REPO_DIR],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"  FAILED to clone: {result.stderr}")
        return False
    print(f"  Cloned to {REPO_DIR}")
    return True


def find_year_end_commit(year):
    """Find the last commit before the cutoff date for a given year."""
    cutoff = YEAR_CUTOFFS[year]
    result = subprocess.run(
        ["git", "log", "--before", cutoff, "--format=%H %ai", "-1"],
        cwd=REPO_DIR, capture_output=True, text=True
    )
    if result.returncode != 0 or not result.stdout.strip():
        print(f"  WARNING: No commit found before {cutoff}")
        return None

    parts = result.stdout.strip().split(' ', 1)
    commit_hash = parts[0]
    commit_date = parts[1] if len(parts) > 1 else "unknown"
    print(f"    Year {year}: commit {commit_hash[:10]} ({commit_date})")
    return commit_hash


def checkout_commit(commit_hash):
    """Checkout a specific commit in the repo."""
    subprocess.run(
        ["git", "checkout", commit_hash, "--force"],
        cwd=REPO_DIR, capture_output=True, text=True, check=True
    )


def restore_master_branch():
    """Return to the master/main branch."""
    # Try master first, then main
    result = subprocess.run(
        ["git", "checkout", "master", "--force"],
        cwd=REPO_DIR, capture_output=True, text=True
    )
    if result.returncode != 0:
        subprocess.run(
            ["git", "checkout", "main", "--force"],
            cwd=REPO_DIR, capture_output=True, text=True
        )


def load_json_files():
    """Load all country JSON files from the current checkout."""
    json_files = []
    for region in REGION_DIRS:
        region_path = os.path.join(REPO_DIR, region)
        if os.path.exists(region_path):
            for jf in sorted(glob.glob(os.path.join(region_path, "*.json"))):
                json_files.append(jf)
    return json_files


def snapshot_master_links(cursor, year):
    """Capture Code -> MasterCountryID mapping before deletion."""
    cursor.execute("""
        SELECT Code, MasterCountryID
        FROM Countries
        WHERE Year = ? AND MasterCountryID IS NOT NULL
    """, year)
    return {row[0].upper(): row[1] for row in cursor.fetchall()}


def delete_year_data(cursor, conn, year):
    """Delete all data for a year, respecting FK constraints."""
    cursor.execute("SELECT CountryID FROM Countries WHERE Year = ?", year)
    country_ids = [row[0] for row in cursor.fetchall()]
    if not country_ids:
        return 0
    chunk_size = 50
    for i in range(0, len(country_ids), chunk_size):
        chunk = country_ids[i:i + chunk_size]
        placeholders = ','.join(['?'] * len(chunk))
        cursor.execute(f"DELETE FROM CountryFields WHERE CountryID IN ({placeholders})", chunk)
        cursor.execute(f"DELETE FROM CountryCategories WHERE CountryID IN ({placeholders})", chunk)
        cursor.execute(f"DELETE FROM Countries WHERE CountryID IN ({placeholders})", chunk)
        conn.commit()
    print(f"    Deleted {len(country_ids)} countries and all associated data")
    return len(country_ids)


def load_year_from_json(cursor, conn, year, json_files, master_links):
    """Parse JSON files and insert into database."""
    success = 0
    failed = 0
    total_fields = 0

    for jf in json_files:
        try:
            with open(jf, 'r', encoding='utf-8') as f:
                data = json.load(f)

            name = data.get("name", "Unknown")
            code = data.get("code", os.path.splitext(os.path.basename(jf))[0].upper())

            # Insert country
            cursor.execute(
                "INSERT INTO Countries (Year, Code, Name, Source) OUTPUT INSERTED.CountryID VALUES (?, ?, ?, ?)",
                year, code, name, 'json'
            )
            country_id = cursor.fetchone()[0]

            # Restore MasterCountryID
            master_id = master_links.get(code.upper())
            if not master_id:
                cursor.execute(
                    "SELECT MasterCountryID FROM MasterCountries WHERE CanonicalCode = ?",
                    code.upper()
                )
                row = cursor.fetchone()
                if row:
                    master_id = row[0]
            if master_id:
                cursor.execute(
                    "UPDATE Countries SET MasterCountryID = ? WHERE CountryID = ?",
                    master_id, country_id
                )

            # Insert categories and fields
            for cat in data.get("categories", []):
                cat_title = cat.get("title", "")
                cursor.execute(
                    "INSERT INTO CountryCategories (CountryID, CategoryTitle) OUTPUT INSERTED.CategoryID VALUES (?, ?)",
                    country_id, cat_title[:200]
                )
                cat_id = cursor.fetchone()[0]

                for field in cat.get("fields", []):
                    content = strip_html(field.get("content", field.get("value", "")))
                    fname = field.get("name", "")
                    cursor.execute(
                        "INSERT INTO CountryFields (CategoryID, CountryID, FieldName, Content) VALUES (?, ?, ?, ?)",
                        cat_id, country_id, fname[:200], content
                    )
                    total_fields += 1

            conn.commit()
            success += 1

        except Exception as e:
            conn.rollback()
            print(f"      ERROR [{os.path.basename(jf)}]: {e}")
            failed += 1

    print(f"    Loaded: {success} countries, {failed} failed, {total_fields:,} fields")
    return success, failed, total_fields


def verify_year(cursor, year):
    """Verify loaded year has reasonable data."""
    cursor.execute("SELECT COUNT(*) FROM Countries WHERE Year = ?", year)
    countries = cursor.fetchone()[0]
    cursor.execute("""
        SELECT COUNT(*) FROM CountryCategories cc
        JOIN Countries c ON cc.CountryID = c.CountryID WHERE c.Year = ?
    """, year)
    categories = cursor.fetchone()[0]
    cursor.execute("""
        SELECT COUNT(*) FROM CountryFields cf
        JOIN Countries c ON cf.CountryID = c.CountryID WHERE c.Year = ?
    """, year)
    fields = cursor.fetchone()[0]
    avg_cats = categories / max(countries, 1)
    avg_fields = fields / max(countries, 1)
    print(f"    {countries} countries | {categories:,} categories | {fields:,} fields")
    print(f"    Avg: {avg_cats:.1f} categories/country, {avg_fields:.1f} fields/country")
    return True


def main():
    dry_run = '--dry-run' in sys.argv

    # Determine target years
    target_years = []
    for i, arg in enumerate(sys.argv[1:], 1):
        if arg == '--year' and i < len(sys.argv) - 1:
            try:
                y = int(sys.argv[i + 1])
                if y in YEAR_CUTOFFS:
                    target_years.append(y)
            except ValueError:
                pass
        elif arg.startswith('--'):
            continue
        else:
            try:
                y = int(arg)
                if y in YEAR_CUTOFFS and y not in target_years:
                    target_years.append(y)
            except ValueError:
                pass

    if not target_years:
        target_years = sorted(YEAR_CUTOFFS.keys())

    print("=" * 70)
    print("CIA FACTBOOK - RELOAD JSON YEARS (Year-Specific Snapshots)")
    print("=" * 70)
    if dry_run:
        print("MODE: DRY RUN")
    print(f"Years to reload: {sorted(target_years)}")
    print()

    # Step 1: Ensure repo
    print("Step 1: Ensuring git repo...")
    if not ensure_repo():
        print("FAILED: Could not clone repo")
        return 1

    # Step 2: Find commits for each year
    print("\nStep 2: Finding year-end commits...")
    year_commits = {}
    for year in sorted(target_years):
        commit = find_year_end_commit(year)
        if commit:
            year_commits[year] = commit
        else:
            print(f"  SKIPPING {year}: no commit found")

    if dry_run:
        print("\nDry run complete. Would reload these years:")
        for year, commit in sorted(year_commits.items()):
            print(f"  {year}: commit {commit[:10]}")
        restore_master_branch()
        return 0

    # Step 3: Connect to database
    conn = pyodbc.connect(CONN_STR)
    cursor = conn.cursor()
    print("\nConnected to database.")

    results = {}
    for year in sorted(year_commits.keys()):
        commit = year_commits[year]
        print(f"\n{'=' * 60}")
        print(f"  YEAR {year}")
        print(f"{'=' * 60}")

        # Checkout year-end commit
        print(f"  Checking out commit {commit[:10]}...")
        checkout_commit(commit)

        # Find JSON files
        json_files = load_json_files()
        print(f"  Found {len(json_files)} JSON files")

        if not json_files:
            print(f"  WARNING: No JSON files found at this commit")
            results[year] = "NO DATA"
            continue

        # Snapshot and delete old data
        print(f"  Snapshotting MasterCountryID links...")
        master_links = snapshot_master_links(cursor, year)
        print(f"    Captured {len(master_links)} links")

        print(f"  Deleting old data...")
        delete_year_data(cursor, conn, year)

        # Load new data
        print(f"  Loading from JSON...")
        success, failed, total_fields = load_year_from_json(
            cursor, conn, year, json_files, master_links
        )

        # Verify
        print(f"  Verifying...")
        verify_year(cursor, year)
        results[year] = "OK" if failed == 0 else "WARNINGS"

    # Restore repo to master
    print("\nRestoring repo to master branch...")
    restore_master_branch()

    # Summary
    print(f"\n{'=' * 60}")
    print("RELOAD SUMMARY")
    print(f"{'=' * 60}")
    for year in sorted(results.keys()):
        print(f"  {year}: {results[year]}")

    # Verify data is unique per year
    print(f"\n{'=' * 60}")
    print("UNIQUENESS CHECK (field counts should differ between years)")
    print(f"{'=' * 60}")
    cursor.execute("""
        SELECT c.Year, COUNT(cf.FieldID) AS Fields
        FROM Countries c
        LEFT JOIN CountryFields cf ON c.CountryID = cf.CountryID
        WHERE c.Year BETWEEN 2021 AND 2025
        GROUP BY c.Year
        ORDER BY c.Year
    """)
    field_counts = []
    for row in cursor.fetchall():
        field_counts.append(row[1])
        print(f"  {row[0]}: {row[1]:,} fields")

    if len(set(field_counts)) > 1:
        print("  OK: Field counts differ between years (data is unique)")
    else:
        print("  WARNING: All years have identical field counts")

    # Full database status
    print(f"\n{'=' * 60}")
    print("FULL DATABASE STATUS")
    print(f"{'=' * 60}")
    cursor.execute("""
        SELECT c.Year, c.Source, COUNT(*) AS Countries
        FROM Countries c GROUP BY c.Year, c.Source ORDER BY c.Year
    """)
    year_rows = cursor.fetchall()
    print(f"  {'Year':<6} {'Countries':<12} {'Categories':<12} {'Fields':<12} {'Source'}")
    print(f"  {'-' * 5:<6} {'-' * 9:<12} {'-' * 10:<12} {'-' * 8:<12} {'-' * 6}")
    for yr, src, cnt in year_rows:
        cursor.execute("SELECT COUNT(*) FROM CountryCategories cc JOIN Countries c ON cc.CountryID = c.CountryID WHERE c.Year = ?", yr)
        cats = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM CountryFields cf JOIN Countries c ON cf.CountryID = c.CountryID WHERE c.Year = ?", yr)
        flds = cursor.fetchone()[0]
        print(f"  {yr:<6} {cnt:<12} {cats:<12} {flds:<12,} {src}")

    cursor.close()
    conn.close()
    print("\nDone!")
    return 0


if __name__ == '__main__':
    exit(main())
