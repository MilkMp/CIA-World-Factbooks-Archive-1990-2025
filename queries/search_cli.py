"""
CIA World Factbook Archive - Search & Browse Tool
==================================================
26 years of data (2000-2025) | 6,916 country records | 941,225 fields

Usage:
    python factbook_search.py                    # Interactive menu
    python factbook_search.py search "nuclear"   # Search all years
    python factbook_search.py country "us" 2020  # View country in specific year
    python factbook_search.py compare "us" "Population"  # Compare field across years
    python factbook_search.py toc 2020           # Table of contents for a year
"""
import pyodbc
import sys

CONN_STR = (
    "DRIVER={ODBC Driver 18 for SQL Server};"
    "SERVER=localhost;"
    "DATABASE=CIA_WorldFactbook;"
    "Trusted_Connection=yes;"
    "TrustServerCertificate=yes;"
)

def get_conn():
    return pyodbc.connect(CONN_STR)

# ============================================================
# COMMANDS
# ============================================================

def cmd_search(conn, keyword, year=None):
    """Search for a keyword across all fields"""
    cursor = conn.cursor()
    if year:
        cursor.execute("""
            SELECT TOP 50 c.Year, c.Name, c.Code, cc.CategoryTitle, cf.FieldName,
                   LEFT(cf.Content, 300) AS ContentPreview
            FROM (
                SELECT CountryID, CategoryID, FieldName, Content,
                       ROW_NUMBER() OVER(PARTITION BY CountryID, FieldName, LEFT(Content, 200) ORDER BY FieldID) AS rn
                FROM CountryFields WHERE Content LIKE ?
            ) cf
            JOIN Countries c ON cf.CountryID = c.CountryID
            JOIN CountryCategories cc ON cf.CategoryID = cc.CategoryID
            WHERE cf.rn = 1 AND c.Year = ?
            ORDER BY c.Name, cc.CategoryTitle
        """, f'%{keyword}%', year)
    else:
        cursor.execute("""
            SELECT TOP 50 c.Year, c.Name, c.Code, cc.CategoryTitle, cf.FieldName,
                   LEFT(cf.Content, 300) AS ContentPreview
            FROM (
                SELECT CountryID, CategoryID, FieldName, Content,
                       ROW_NUMBER() OVER(PARTITION BY CountryID, FieldName, LEFT(Content, 200) ORDER BY FieldID) AS rn
                FROM CountryFields WHERE Content LIKE ?
            ) cf
            JOIN Countries c ON cf.CountryID = c.CountryID
            JOIN CountryCategories cc ON cf.CategoryID = cc.CategoryID
            WHERE cf.rn = 1
            ORDER BY c.Year DESC, c.Name
        """, f'%{keyword}%')

    rows = cursor.fetchall()
    if not rows:
        print(f"  No results for '{keyword}'")
        return

    print(f"\n  Found {len(rows)} results for '{keyword}'" + (f" (year {year})" if year else "") + ":\n")
    for r in rows:
        preview = r[5].replace('\n', ' ')[:200] if r[5] else ""
        print(f"  [{r[0]}] {r[1]} ({r[2]})")
        print(f"    {r[3]} > {r[4]}")
        print(f"    {preview}...")
        print()

def find_master_country(cursor, code_or_name):
    """Find a MasterCountryID by FIPS code, ISO code, or name fragment."""
    upper = code_or_name.upper()

    # Try FIPS code (CanonicalCode)
    cursor.execute(
        "SELECT MasterCountryID, CanonicalName FROM MasterCountries WHERE CanonicalCode = ?",
        upper
    )
    row = cursor.fetchone()
    if row:
        return row[0], row[1]

    # Try ISO code
    cursor.execute(
        "SELECT MasterCountryID, CanonicalName FROM MasterCountries WHERE ISOAlpha2 = ?",
        upper
    )
    row = cursor.fetchone()
    if row:
        return row[0], row[1]

    # Try name search
    cursor.execute(
        "SELECT MasterCountryID, CanonicalName FROM MasterCountries WHERE CanonicalName LIKE ?",
        f'%{code_or_name}%'
    )
    row = cursor.fetchone()
    if row:
        return row[0], row[1]

    return None, None


def cmd_country(conn, code, year=None):
    """View all data for a country"""
    cursor = conn.cursor()

    # Find via MasterCountries for consistent cross-year lookup
    master_id, _ = find_master_country(cursor, code)

    if master_id and year:
        cursor.execute("""
            SELECT c.CountryID, c.Year, c.Code, c.Name
            FROM Countries c
            WHERE c.MasterCountryID = ? AND c.Year = ?
        """, master_id, year)
    elif master_id:
        cursor.execute("""
            SELECT TOP 1 c.CountryID, c.Year, c.Code, c.Name
            FROM Countries c
            WHERE c.MasterCountryID = ?
            ORDER BY c.Year DESC
        """, master_id)
    elif year:
        cursor.execute("""
            SELECT c.CountryID, c.Year, c.Code, c.Name
            FROM Countries c
            WHERE (c.Code = ? OR c.Code = ?) AND c.Year = ?
        """, code.lower(), code.upper(), year)
    else:
        cursor.execute("""
            SELECT TOP 1 c.CountryID, c.Year, c.Code, c.Name
            FROM Countries c
            WHERE c.Code = ? OR c.Code = ?
            ORDER BY c.Year DESC
        """, code.lower(), code.upper())

    row = cursor.fetchone()
    if not row:
        # Last resort: name search directly on Countries
        cursor.execute("""
            SELECT TOP 1 c.CountryID, c.Year, c.Code, c.Name
            FROM Countries c
            WHERE c.Name LIKE ?
            ORDER BY c.Year DESC
        """, f'%{code}%')
        row = cursor.fetchone()

    if not row:
        print(f"  Country '{code}' not found")
        return

    country_id, yr, ccode, name = row
    print(f"\n  === {name} ({ccode}) - {yr} ===\n")

    cursor.execute("""
        SELECT cc.CategoryTitle, cf.FieldName, cf.Content
        FROM CountryCategories cc
        JOIN CountryFields cf ON cc.CategoryID = cf.CategoryID
        WHERE cc.CountryID = ?
        ORDER BY cc.CategoryID, cf.FieldID
    """, country_id)

    current_cat = None
    for r in cursor.fetchall():
        if r[0] != current_cat:
            current_cat = r[0]
            print(f"\n  --- {current_cat} ---")
        content = r[2][:500] if r[2] else ""
        content = content.replace('\n', ' ')
        print(f"    {r[1]}: {content}")

def cmd_compare(conn, code, field_name):
    """Compare a field across all years for a country (uses MasterCountryID)"""
    cursor = conn.cursor()

    # Find the master country so we match across HTML/JSON years
    master_id, master_name = find_master_country(cursor, code)

    if master_id:
        cursor.execute("""
            SELECT c.Year, c.Name, cf.FieldName, LEFT(cf.Content, 500)
            FROM CountryFields cf
            JOIN Countries c ON cf.CountryID = c.CountryID
            WHERE c.MasterCountryID = ? AND cf.FieldName LIKE ?
            ORDER BY c.Year
        """, master_id, f'%{field_name}%')
    else:
        # Fallback: try direct code match both cases
        cursor.execute("""
            SELECT c.Year, c.Name, cf.FieldName, LEFT(cf.Content, 500)
            FROM CountryFields cf
            JOIN Countries c ON cf.CountryID = c.CountryID
            WHERE (c.Code = ? OR c.Code = ?) AND cf.FieldName LIKE ?
            ORDER BY c.Year
        """, code.lower(), code.upper(), f'%{field_name}%')

    rows = cursor.fetchall()
    if not rows:
        # Last resort: name search
        cursor.execute("""
            SELECT c.Year, c.Name, cf.FieldName, LEFT(cf.Content, 500)
            FROM CountryFields cf
            JOIN Countries c ON cf.CountryID = c.CountryID
            WHERE c.Name LIKE ? AND cf.FieldName LIKE ?
            ORDER BY c.Year
        """, f'%{code}%', f'%{field_name}%')
        rows = cursor.fetchall()

    if not rows:
        print(f"  No data found for '{code}' / '{field_name}'")
        return

    label = master_name or rows[0][1]
    print(f"\n  === {label} - '{field_name}' across years ===\n")
    for r in rows:
        content = r[3].replace('\n', ' ')[:300] if r[3] else ""
        print(f"  [{r[0]}] {r[2]}: {content}")
        print()

def cmd_toc(conn, year):
    """Show table of contents for a year"""
    cursor = conn.cursor()

    # List all countries for that year
    cursor.execute("""
        SELECT c.Code, c.Name
        FROM Countries c
        WHERE c.Year = ?
        ORDER BY c.Name
    """, year)

    countries = cursor.fetchall()
    if not countries:
        print(f"  No data for year {year}")
        return

    print(f"\n  === {year} World Factbook - {len(countries)} Countries ===\n")
    for i, c in enumerate(countries, 1):
        print(f"  {i:3d}. [{c[0]}] {c[1]}")

    # Show categories for first country as an example of structure
    cursor.execute("""
        SELECT DISTINCT cc.CategoryTitle
        FROM CountryCategories cc
        JOIN Countries c ON cc.CountryID = c.CountryID
        WHERE c.Year = ?
        ORDER BY cc.CategoryTitle
    """, year)

    cats = cursor.fetchall()
    print(f"\n  Categories available ({len(cats)}):")
    for c in cats[:30]:
        print(f"    - {c[0]}")
    if len(cats) > 30:
        print(f"    ... and {len(cats)-30} more")

def cmd_years(conn):
    """Show summary of all years"""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT c.Year, COUNT(DISTINCT c.CountryID) AS Countries,
               COUNT(DISTINCT cc.CategoryID) AS Categories,
               COUNT(cf.FieldID) AS Fields,
               c.Source
        FROM Countries c
        LEFT JOIN CountryCategories cc ON c.CountryID = cc.CountryID
        LEFT JOIN CountryFields cf ON c.CountryID = cf.CountryID
        GROUP BY c.Year, c.Source
        ORDER BY c.Year
    """)

    print(f"\n  === CIA World Factbook Archive ===\n")
    print(f"  {'Year':<6} {'Countries':<12} {'Categories':<12} {'Fields':<10} {'Source'}")
    print(f"  {'-'*5:<6} {'-'*9:<12} {'-'*10:<12} {'-'*6:<10} {'-'*6}")
    total_c = total_cat = total_f = 0
    for r in cursor.fetchall():
        print(f"  {r[0]:<6} {r[1]:<12} {r[2]:<12} {r[3]:<10} {r[4]}")
        total_c += r[1]
        total_cat += r[2]
        total_f += r[3]
    print(f"  {'-'*5:<6} {'-'*9:<12} {'-'*10:<12} {'-'*6:<10}")
    print(f"  {'TOTAL':<6} {total_c:<12} {total_cat:<12} {total_f:<10}")

def cmd_countries(conn, year=None):
    """List all unique countries"""
    cursor = conn.cursor()
    if year:
        cursor.execute("""
            SELECT Code, Name FROM Countries WHERE Year = ? ORDER BY Name
        """, year)
    else:
        cursor.execute("""
            SELECT DISTINCT Code, Name FROM Countries ORDER BY Name
        """)
    rows = cursor.fetchall()
    print(f"\n  {'Code':<6} Name")
    print(f"  {'-'*4:<6} {'-'*30}")
    for r in rows:
        print(f"  {r[0]:<6} {r[1]}")
    print(f"\n  Total: {len(rows)}")

# ============================================================
# INTERACTIVE MENU
# ============================================================

def interactive(conn):
    """Interactive menu"""
    print("""
  ============================================
   CIA World Factbook Archive
   26 years (2000-2025) | ~941K data fields
  ============================================

  Commands:
    search <keyword> [year]     Search all data
    country <code/name> [year]  View country data
    compare <code> <field>      Compare field across years
    toc <year>                  Table of contents
    years                       Show all years summary
    countries [year]            List all countries
    quit                        Exit
    """)

    while True:
        try:
            cmd = input("\n  > ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if not cmd:
            continue

        parts = cmd.split(maxsplit=2)
        action = parts[0].lower()

        if action in ('quit', 'exit', 'q'):
            break
        elif action == 'search' and len(parts) >= 2:
            year = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else None
            cmd_search(conn, parts[1], year)
        elif action == 'country' and len(parts) >= 2:
            year = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else None
            cmd_country(conn, parts[1], year)
        elif action == 'compare' and len(parts) >= 3:
            cmd_compare(conn, parts[1], parts[2])
        elif action == 'toc' and len(parts) >= 2:
            cmd_toc(conn, int(parts[1]))
        elif action == 'years':
            cmd_years(conn)
        elif action == 'countries':
            year = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else None
            cmd_countries(conn, year)
        else:
            print("  Unknown command. Type 'search', 'country', 'compare', 'toc', 'years', or 'quit'.")

# ============================================================
# MAIN
# ============================================================

def main():
    conn = get_conn()

    if len(sys.argv) > 1:
        action = sys.argv[1].lower()
        if action == 'search' and len(sys.argv) >= 3:
            year = int(sys.argv[3]) if len(sys.argv) > 3 else None
            cmd_search(conn, sys.argv[2], year)
        elif action == 'country' and len(sys.argv) >= 3:
            year = int(sys.argv[3]) if len(sys.argv) > 3 else None
            cmd_country(conn, sys.argv[2], year)
        elif action == 'compare' and len(sys.argv) >= 4:
            cmd_compare(conn, sys.argv[2], sys.argv[3])
        elif action == 'toc' and len(sys.argv) >= 3:
            cmd_toc(conn, int(sys.argv[2]))
        elif action == 'years':
            cmd_years(conn)
        elif action == 'countries':
            year = int(sys.argv[2]) if len(sys.argv) > 2 else None
            cmd_countries(conn, year)
        else:
            print(__doc__)
    else:
        interactive(conn)

    conn.close()

if __name__ == '__main__':
    main()
