import pyodbc
import html as html_module

CONN_STR = (
    "DRIVER={ODBC Driver 18 for SQL Server};"
    "SERVER=localhost;"
    "DATABASE=CIA_WorldFactbook;"
    "Trusted_Connection=yes;"
    "TrustServerCertificate=yes;"
)

def normalize_code(code):
    """Normalize country code to uppercase"""
    return code.upper() if code else None

def normalize_name(name):
    """Normalize country name by removing trailing dashes and unescaping HTML entities"""
    if not name:
        return None
    # Remove trailing " —"
    name = name.rstrip(' —').strip()
    # Unescape HTML entities like &#39; to '
    name = html_module.unescape(name)
    return name

conn = pyodbc.connect(CONN_STR)
cursor = conn.cursor()

# Test with a few specific countries
test_codes = ['af', 'AF', 'us', 'US', 'ch', 'CH']

print("=== Testing normalize_name function ===\n")
for test_code in test_codes:
    cursor.execute("SELECT Code, Name FROM Countries WHERE Code = ?", test_code)
    rows = cursor.fetchall()
    if rows:
        for code, name in rows:
            normalized = normalize_name(name)
            print(f"Original: '{name}'")
            print(f"Normalized: '{normalized}'")
            print()

# Now test the actual query from the migration script
print("\n=== Testing DISTINCT query (first 20) ===\n")
cursor.execute("""
    SELECT DISTINCT Code, Name 
    FROM Countries 
    ORDER BY Code
""")

count = 0
for code, name in cursor.fetchall():
    if count < 20:
        normalized_name = normalize_name(name)
        print(f"{code:5} | '{name}' → '{normalized_name}'")
        count += 1
    else:
        break

conn.close()
