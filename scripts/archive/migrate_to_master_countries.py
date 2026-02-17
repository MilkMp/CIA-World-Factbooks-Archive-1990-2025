import pyodbc
import html

# Database connection settings
CONN_STR = (
    "DRIVER={ODBC Driver 18 for SQL Server};"
    "SERVER=localhost;"
    "DATABASE=CIA_WorldFactbook;"
    "Trusted_Connection=yes;"
    "TrustServerCertificate=yes;"
)

def connect_db():
    """Connect to SQL Server database"""
    return pyodbc.connect(CONN_STR)

def normalize_code(code):
    """Normalize country code to uppercase"""
    return code.upper() if code else None

# Names that indicate a parsing failure - should never be chosen as canonical
BAD_NAMES = {'cia', 'unknown', '— central intelligence agency', 'central intelligence agency', ''}

def normalize_name(name):
    """Normalize country name by removing trailing dashes and unescaping HTML entities"""
    if not name:
        return None
    # Remove trailing " —"
    name = name.rstrip(' —').strip()
    # Remove leading "— " 
    name = name.lstrip('— ').strip()
    # Unescape HTML entities like &#39; to '
    name = html.unescape(name)
    return name

def is_bad_name(name):
    """Check if a name is a parsing failure artifact"""
    return name.lower().strip() in BAD_NAMES

def create_master_countries_table(cursor):
    """Create the MasterCountries table"""
    print("Creating MasterCountries table...")
    cursor.execute("""
        IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'MasterCountries')
        BEGIN
            CREATE TABLE MasterCountries (
                MasterCountryID INT IDENTITY(1,1) PRIMARY KEY,
                CanonicalCode NVARCHAR(10) NOT NULL UNIQUE,
                CanonicalName NVARCHAR(200) NOT NULL,
                CreatedDate DATETIME DEFAULT GETDATE()
            )
        END
    """)
    print("✓ MasterCountries table created")

def extract_distinct_countries(cursor):
    """Extract all distinct country codes and names from existing data"""
    print("\nExtracting distinct countries from database...")
    cursor.execute("""
        SELECT DISTINCT Code, Name 
        FROM Countries 
        ORDER BY Code
    """)
    
    countries = cursor.fetchall()
    print(f"Found {len(countries)} distinct code/name combinations")
    
    # Normalize and deduplicate
    master_countries = {}
    for code, name in countries:
        normalized_code = normalize_code(code)
        normalized_name = normalize_name(name)
        
        if normalized_code not in master_countries:
            master_countries[normalized_code] = normalized_name
        # If current stored name is bad, replace with anything better
        elif is_bad_name(master_countries[normalized_code]) and not is_bad_name(normalized_name):
            master_countries[normalized_code] = normalized_name
        # If both are good names, prefer the JSON-style (no trailing dashes, cleaner)
        # Use length as proxy: avoid very short names that are likely bad
        elif not is_bad_name(normalized_name) and len(normalized_name) > len(master_countries[normalized_code]):
            master_countries[normalized_code] = normalized_name
    
    print(f"Normalized to {len(master_countries)} unique master countries")
    return master_countries

def populate_master_countries(cursor, master_countries):
    """Insert master countries into MasterCountries table"""
    print("\nPopulating MasterCountries table...")
    
    insert_sql = """
        INSERT INTO MasterCountries (CanonicalCode, CanonicalName)
        VALUES (?, ?)
    """
    
    count = 0
    for code, name in sorted(master_countries.items()):
        try:
            cursor.execute(insert_sql, code, name)
            count += 1
        except pyodbc.IntegrityError:
            # Already exists, skip
            pass
    
    print(f"✓ Inserted {count} master countries")

def add_master_country_id_column(cursor):
    """Add MasterCountryID column to Countries table"""
    print("\nAdding MasterCountryID column to Countries table...")
    cursor.execute("""
        IF NOT EXISTS (
            SELECT * FROM sys.columns 
            WHERE object_id = OBJECT_ID('Countries') 
            AND name = 'MasterCountryID'
        )
        BEGIN
            ALTER TABLE Countries 
            ADD MasterCountryID INT NULL
        END
    """)
    print("✓ Column added")

def update_master_country_ids(cursor):
    """Update all Countries records with their corresponding MasterCountryID"""
    print("\nMapping existing countries to master IDs...")
    
    # Get all master countries
    cursor.execute("SELECT MasterCountryID, CanonicalCode FROM MasterCountries")
    master_map = {code: mid for mid, code in cursor.fetchall()}
    
    # Update Countries table
    cursor.execute("SELECT CountryID, Code FROM Countries")
    countries = cursor.fetchall()
    
    update_sql = "UPDATE Countries SET MasterCountryID = ? WHERE CountryID = ?"
    
    count = 0
    not_found = []
    for country_id, code in countries:
        normalized_code = normalize_code(code)
        master_id = master_map.get(normalized_code)
        
        if master_id:
            cursor.execute(update_sql, master_id, country_id)
            count += 1
        else:
            not_found.append(f"{country_id}: {code}")
    
    print(f"✓ Updated {count} country records")
    
    if not_found:
        print(f"⚠ Warning: {len(not_found)} records could not be mapped:")
        for item in not_found[:10]:  # Show first 10
            print(f"  - {item}")

def add_foreign_key_constraint(cursor):
    """Add foreign key constraint between Countries and MasterCountries"""
    print("\nAdding foreign key constraint...")
    cursor.execute("""
        IF NOT EXISTS (
            SELECT * FROM sys.foreign_keys 
            WHERE name = 'FK_Countries_MasterCountries'
        )
        BEGIN
            ALTER TABLE Countries
            ADD CONSTRAINT FK_Countries_MasterCountries
            FOREIGN KEY (MasterCountryID) 
            REFERENCES MasterCountries(MasterCountryID)
        END
    """)
    print("✓ Foreign key constraint added")

def verify_migration(cursor):
    """Verify the migration was successful"""
    print("\n" + "="*60)
    print("VERIFICATION")
    print("="*60)
    
    # Count master countries
    cursor.execute("SELECT COUNT(*) FROM MasterCountries")
    master_count = cursor.fetchone()[0]
    print(f"Master countries: {master_count}")
    
    # Count mapped vs unmapped
    cursor.execute("SELECT COUNT(*) FROM Countries WHERE MasterCountryID IS NOT NULL")
    mapped_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM Countries WHERE MasterCountryID IS NULL")
    unmapped_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM Countries")
    total_count = cursor.fetchone()[0]
    
    print(f"Countries mapped: {mapped_count}/{total_count}")
    if unmapped_count > 0:
        print(f"⚠ Countries unmapped: {unmapped_count}")
    else:
        print("✓ All countries mapped successfully!")
    
    # Show sample master countries
    print("\nSample master countries:")
    cursor.execute("SELECT TOP 5 CanonicalCode, CanonicalName FROM MasterCountries ORDER BY CanonicalName")
    for code, name in cursor.fetchall():
        print(f"  {code}: {name}")
    
    print("\n" + "="*60)

def main():
    print("="*60)
    print("CIA FACTBOOK MASTER COUNTRIES MIGRATION")
    print("="*60)
    
    try:
        # Connect to database
        print("\nConnecting to database...")
        conn = connect_db()
        cursor = conn.cursor()
        print("✓ Connected")
        
        # Step 0: Drop existing MasterCountries setup if re-running
        print("\nCleaning up previous migration (if any)...")
        cursor.execute("""
            IF EXISTS (SELECT * FROM sys.foreign_keys WHERE name = 'FK_Countries_MasterCountries')
                ALTER TABLE Countries DROP CONSTRAINT FK_Countries_MasterCountries
        """)
        cursor.execute("""
            IF EXISTS (SELECT * FROM sys.columns WHERE object_id = OBJECT_ID('Countries') AND name = 'MasterCountryID')
                ALTER TABLE Countries DROP COLUMN MasterCountryID
        """)
        cursor.execute("""
            IF EXISTS (SELECT * FROM sys.tables WHERE name = 'MasterCountries')
                DROP TABLE MasterCountries
        """)
        conn.commit()
        print("✓ Cleanup done")
        
        # Step 1: Create MasterCountries table
        create_master_countries_table(cursor)
        conn.commit()
        
        # Step 2: Extract distinct countries
        master_countries = extract_distinct_countries(cursor)
        
        # Step 3: Populate MasterCountries
        populate_master_countries(cursor, master_countries)
        conn.commit()
        
        # Step 4: Add MasterCountryID column to Countries
        add_master_country_id_column(cursor)
        conn.commit()
        
        # Step 5: Update all Countries records with MasterCountryID
        update_master_country_ids(cursor)
        conn.commit()
        
        # Step 6: Add foreign key constraint
        add_foreign_key_constraint(cursor)
        conn.commit()
        
        # Step 7: Verify migration
        verify_migration(cursor)
        
        print("\n✓ Migration completed successfully!")
        
        cursor.close()
        conn.close()
        
    except pyodbc.Error as e:
        print(f"\n✗ Database error: {e}")
        return 1
    except Exception as e:
        print(f"\n✗ Error: {e}")
        return 1
    
    return 0

if __name__ == '__main__':
    exit(main())
