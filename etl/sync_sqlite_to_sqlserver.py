"""
Sync SQLite factbook.db -> SQL Server CIA_WorldFactbook
=======================================================
Compares CountryFields.Content between both databases and updates
SQL Server to match SQLite. Run this after any SQLite data fixes.

Usage:
  python etl/sync_sqlite_to_sqlserver.py              # sync all years
  python etl/sync_sqlite_to_sqlserver.py --years 2025  # sync single year
  python etl/sync_sqlite_to_sqlserver.py --dry-run     # preview without writing
"""
import pyodbc
import sqlite3
import sys
import os
import time

SQLITE_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "factbook.db")
CONN_STR = (
    "DRIVER={ODBC Driver 18 for SQL Server};"
    "SERVER=localhost;"
    "DATABASE=CIA_WorldFactbook;"
    "Trusted_Connection=yes;"
    "TrustServerCertificate=yes;"
)


def sync_country_fields(sc, mc, sql_conn, years, dry_run=False):
    """Sync CountryFields.Content from SQLite to SQL Server."""
    total_updated = 0

    for year in years:
        # Build SQLite lookup: (Code, CategoryTitle, FieldName) -> Content
        sc.execute("""
            SELECT co.Code, cc.CategoryTitle, cf.FieldName, cf.Content
            FROM CountryFields cf
            JOIN Countries co ON cf.CountryID = co.CountryID
            JOIN CountryCategories cc ON cf.CategoryID = cc.CategoryID
            WHERE co.Year = ?
        """, (year,))
        sqlite_lookup = {(code, cat, fn): content for code, cat, fn, content in sc.fetchall()}

        # Get SQL Server fields for this year
        mc.execute("""
            SELECT cf.FieldID, co.Code, cc.CategoryTitle, cf.FieldName, cf.Content
            FROM CountryFields cf
            JOIN Countries co ON cf.CountryID = co.CountryID
            JOIN CountryCategories cc ON cf.CategoryID = cc.CategoryID
            WHERE co.Year = ?
        """, year)

        year_updated = 0
        for fid, code, cat, fname, old_content in mc.fetchall():
            key = (code, cat, fname)
            if key in sqlite_lookup:
                new_content = sqlite_lookup[key]
                if new_content and new_content != old_content:
                    if not dry_run:
                        mc.execute(
                            "UPDATE CountryFields SET Content = ? WHERE FieldID = ?",
                            new_content, fid,
                        )
                    year_updated += 1

        if not dry_run:
            sql_conn.commit()
        print(f"  {year}: {year_updated} fields {'would be ' if dry_run else ''}updated")
        total_updated += year_updated

    return total_updated


def sync_master_countries(sc, mc, sql_conn, dry_run=False):
    """Sync MasterCountryID links from SQLite to SQL Server."""
    sc.execute("""
        SELECT co.Year, co.Code, co.MasterCountryID
        FROM Countries co
        WHERE co.MasterCountryID IS NOT NULL
    """)
    sqlite_links = {}
    for year, code, mid in sc.fetchall():
        sqlite_links[(year, code)] = mid

    mc.execute("SELECT CountryID, Year, Code, MasterCountryID FROM Countries")
    updated = 0
    for cid, year, code, old_mid in mc.fetchall():
        key = (year, code)
        if key in sqlite_links:
            new_mid = sqlite_links[key]
            if new_mid != old_mid:
                if not dry_run:
                    mc.execute(
                        "UPDATE Countries SET MasterCountryID = ? WHERE CountryID = ?",
                        new_mid, cid,
                    )
                updated += 1

    if not dry_run:
        sql_conn.commit()
    if updated:
        print(f"  MasterCountryID: {updated} {'would be ' if dry_run else ''}updated")
    return updated


def main():
    dry_run = "--dry-run" in sys.argv

    # Parse --years
    target_years = []
    for i, arg in enumerate(sys.argv[1:], 1):
        if arg == "--years" and i < len(sys.argv) - 1:
            try:
                target_years.append(int(sys.argv[i + 1]))
            except ValueError:
                pass
        elif not arg.startswith("--"):
            try:
                target_years.append(int(arg))
            except ValueError:
                pass

    # Connect
    db_path = os.path.abspath(SQLITE_PATH)
    if not os.path.exists(db_path):
        print(f"ERROR: SQLite database not found at {db_path}")
        return 1

    print("=" * 60)
    print("SYNC: SQLite -> SQL Server")
    print("=" * 60)
    if dry_run:
        print("MODE: DRY RUN (no changes will be written)")
    print(f"  SQLite:     {db_path}")
    print(f"  SQL Server: localhost/CIA_WorldFactbook")

    sqlite_conn = sqlite3.connect(db_path)
    sc = sqlite_conn.cursor()

    try:
        sql_conn = pyodbc.connect(CONN_STR)
    except pyodbc.Error as e:
        print(f"ERROR: Cannot connect to SQL Server: {e}")
        sqlite_conn.close()
        return 1
    mc = sql_conn.cursor()

    # Determine years to sync
    if not target_years:
        sc.execute("SELECT DISTINCT Year FROM Countries ORDER BY Year")
        target_years = [row[0] for row in sc.fetchall()]

    print(f"  Years:      {min(target_years)}-{max(target_years)} ({len(target_years)} years)")
    print()

    # Sync CountryFields
    t0 = time.time()
    print("Syncing CountryFields.Content...")
    fields_updated = sync_country_fields(sc, mc, sql_conn, target_years, dry_run)

    # Sync MasterCountryID links
    print("\nSyncing Countries.MasterCountryID...")
    links_updated = sync_master_countries(sc, mc, sql_conn, dry_run)

    elapsed = time.time() - t0

    # Summary
    print(f"\n{'=' * 60}")
    print(f"SYNC COMPLETE ({elapsed:.1f}s)")
    print(f"{'=' * 60}")
    print(f"  CountryFields updated: {fields_updated}")
    print(f"  MasterCountryID updated: {links_updated}")
    if dry_run:
        print("  (dry run — no changes written)")

    sqlite_conn.close()
    sql_conn.close()
    return 0


if __name__ == "__main__":
    exit(main())
