"""
CIA Factbook Archive - Entity Type Classifier
==============================================
Reads "Dependency status" and "Government type" fields from CountryFields
to auto-classify each MasterCountry as sovereign, territory, disputed, etc.

Phase 1 (default): READ-ONLY — prints proposed classifications for review.
Phase 2 (--apply):  Adds EntityType column and writes to MasterCountries.

Run:  py classify_entities.py          # review mode
      py classify_entities.py --apply  # write to database
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

# ============================================================
# Entity type categories (CIA Factbook terminology)
# ============================================================
# sovereign        - Independent state / sovereign nation
# territory        - Dependency, overseas territory, unincorporated territory
# disputed         - Disputed sovereignty (Kosovo, West Bank, etc.)
# freely_associated - Self-governing in free association with another state
# special_admin    - Special Administrative Region (Hong Kong, Macau)
# crown_dependency - Crown dependency of the UK (Jersey, Guernsey, Isle of Man)
# antarctic        - Antarctic territory/claim
# misc             - Oceans, World, EU, other non-country entries
# dissolved        - Historical entity that no longer exists

# Hardcoded overrides for entries we know can't be auto-classified
# or where the auto-classifier gets it wrong
OVERRIDES = {
    # Oceans and non-countries
    "XQ": "misc",      # Arctic Ocean
    "ZH": "misc",      # Atlantic Ocean
    "XO": "misc",      # Indian Ocean
    "ZN": "misc",      # Pacific Ocean
    "OO": "misc",      # Southern Ocean
    "XX": "misc",      # World
    "EE": "misc",      # European Union

    # Disputed territories
    "KV": "disputed",  # Kosovo
    "GZ": "disputed",  # Gaza Strip
    "WE": "disputed",  # West Bank
    "PF": "disputed",  # Paracel Islands
    "PG": "disputed",  # Spratly Islands
    "PJ": "disputed",  # Etorofu/Habomai/Kunashiri/Shikotan Islands

    # UK sovereign base areas
    "AX": "territory", # Akrotiri
    "DX": "territory", # Dhekelia

    # Special Administrative Regions
    "HK": "special_admin",  # Hong Kong
    "MC": "special_admin",  # Macau

    # Crown dependencies
    "GK": "crown_dependency",  # Guernsey
    "JE": "crown_dependency",  # Jersey
    "IM": "crown_dependency",  # Isle of Man

    # Freely associated states
    "RM": "freely_associated",  # Marshall Islands
    "FM": "freely_associated",  # Micronesia
    "PS": "freely_associated",  # Palau

    # Antarctic
    "AY": "antarctic",  # Antarctica

    # Dissolved entities
    "NT": "dissolved",  # Netherlands Antilles
    "YI": "dissolved",  # Serbia and Montenegro

    # French territories that appear in older data
    "BS": "territory",  # Bassas da India
    "EU": "territory",  # Europa Island
    "GO": "territory",  # Glorioso Islands
    "JU": "territory",  # Juan de Nova Island
    "TE": "territory",  # Tromelin Island
    "ZZ": "territory",  # Iles Eparses
    "IP": "territory",  # Clipperton Island

    # US Minor Outlying Islands territories
    "FQ": "territory",  # Baker Island
    "HQ": "territory",  # Howland Island
    "DQ": "territory",  # Jarvis Island
    "JQ": "territory",  # Johnston Atoll
    "KQ": "territory",  # Kingman Reef
    "MQ": "territory",  # Midway Islands
    "LQ": "territory",  # Palmyra Atoll
    "WQ": "territory",  # Wake Island
    "BQ": "territory",  # Navassa Island
    "UM": "territory",  # US Pacific Island Wildlife Refuges

    # Holy See is sovereign (unique: city-state, theocratic)
    "VT": "sovereign",

    # Western Sahara — sovereignty unresolved
    "WI": "disputed",
}


def connect_db():
    return pyodbc.connect(CONN_STR)


def get_gov_fields(cursor, master_id):
    """Get the most recent Government type and Dependency status for a country."""
    # Get the most recent year's data
    cursor.execute("""
        SELECT TOP 1 cf.FieldName, cf.Content
        FROM CountryFields cf
        JOIN Countries c ON cf.CountryID = c.CountryID
        WHERE c.MasterCountryID = ?
          AND cf.FieldName LIKE '%ependency%status%'
        ORDER BY c.Year DESC
    """, master_id)
    dep_row = cursor.fetchone()
    dep_status = dep_row[1] if dep_row else ""

    cursor.execute("""
        SELECT TOP 1 cf.FieldName, cf.Content
        FROM CountryFields cf
        JOIN Countries c ON cf.CountryID = c.CountryID
        WHERE c.MasterCountryID = ?
          AND cf.FieldName LIKE '%overnment%type%'
        ORDER BY c.Year DESC
    """, master_id)
    gov_row = cursor.fetchone()
    gov_type = gov_row[1] if gov_row else ""

    return dep_status.strip(), gov_type.strip()


def classify(dep_status, gov_type, fips_code, name):
    """Auto-classify entity type from dependency status and government type text."""
    # Check overrides first
    if fips_code in OVERRIDES:
        return OVERRIDES[fips_code], "override"

    dep_lower = dep_status.lower()
    gov_lower = gov_type.lower()
    name_lower = name.lower()

    # If there's a dependency status, it's almost certainly a territory
    if dep_lower:
        if any(kw in dep_lower for kw in [
            'territory', 'dependency', 'overseas', 'unincorporated',
            'self-governing', 'crown', 'collectivity', 'constituent',
            'special municipality', 'country within'
        ]):
            return "territory", f"dep: {dep_status[:60]}"

        if 'free association' in dep_lower or 'freely associated' in dep_lower:
            return "freely_associated", f"dep: {dep_status[:60]}"

        # Generic dependency — classify as territory
        if dep_lower and dep_lower not in ('none', 'n/a', ''):
            return "territory", f"dep: {dep_status[:60]}"

    # No dependency status — likely sovereign, but check government type
    if gov_lower:
        # These are almost always sovereign states
        sovereign_keywords = [
            'republic', 'monarchy', 'kingdom', 'democracy', 'federation',
            'parliamentary', 'presidential', 'communist', 'theocra',
            'socialist', 'constitutional', 'emirate', 'sultanate',
            'oligarch', 'authoritarian', 'military', 'transitional',
            'single-party', 'dictatorship'
        ]
        if any(kw in gov_lower for kw in sovereign_keywords):
            return "sovereign", f"gov: {gov_type[:60]}"

    # If we have a government type but couldn't classify
    if gov_lower:
        return "sovereign", f"gov (default): {gov_type[:60]}"

    # No data at all — unknown
    return "unknown", "no gov/dep data"


def main():
    apply_mode = "--apply" in sys.argv

    print("=" * 70)
    print("CIA FACTBOOK - ENTITY TYPE CLASSIFIER")
    print("=" * 70)
    if apply_mode:
        print("MODE: APPLY (will write to database)")
    else:
        print("MODE: REVIEW (read-only, run with --apply to write)")
    print()

    conn = connect_db()
    cursor = conn.cursor()

    # Get all master countries
    cursor.execute("""
        SELECT MasterCountryID, CanonicalCode, CanonicalName
        FROM MasterCountries
        ORDER BY CanonicalName
    """)
    master_countries = cursor.fetchall()
    print(f"Processing {len(master_countries)} master countries...\n")

    results = {}
    by_type = {}

    for master_id, fips_code, name in master_countries:
        dep_status, gov_type = get_gov_fields(cursor, master_id)
        entity_type, reason = classify(dep_status, gov_type, fips_code, name)
        results[fips_code] = (entity_type, name, reason)

        if entity_type not in by_type:
            by_type[entity_type] = []
        by_type[entity_type].append((fips_code, name, reason))

    # Print results grouped by type
    for etype in sorted(by_type.keys()):
        entries = by_type[etype]
        print(f"\n{'='*50}")
        print(f"  {etype.upper()} ({len(entries)})")
        print(f"{'='*50}")
        for code, name, reason in sorted(entries, key=lambda x: x[1]):
            print(f"  {code:<6} {name:<45} [{reason}]")

    # Summary
    print(f"\n{'='*50}")
    print("SUMMARY")
    print(f"{'='*50}")
    for etype in sorted(by_type.keys()):
        print(f"  {etype:<20} {len(by_type[etype]):>4}")
    print(f"  {'TOTAL':<20} {len(results):>4}")

    # Apply mode
    if apply_mode:
        print(f"\n--- Applying to database ---")

        # Add column
        cursor.execute("""
            IF NOT EXISTS (
                SELECT * FROM sys.columns
                WHERE object_id = OBJECT_ID('MasterCountries')
                AND name = 'EntityType'
            )
            BEGIN
                ALTER TABLE MasterCountries
                ADD EntityType NVARCHAR(20) NULL
            END
        """)

        # Update all rows
        updated = 0
        for fips_code, (entity_type, name, reason) in results.items():
            cursor.execute(
                "UPDATE MasterCountries SET EntityType = ? WHERE CanonicalCode = ?",
                entity_type, fips_code
            )
            updated += cursor.rowcount

        conn.commit()
        print(f"  Updated {updated} rows")
        print("  Done! EntityType column populated.")
    else:
        print(f"\nReview the output above. If it looks good, run:")
        print(f"  py classify_entities.py --apply")

    cursor.close()
    conn.close()
    return 0


if __name__ == '__main__':
    exit(main())
