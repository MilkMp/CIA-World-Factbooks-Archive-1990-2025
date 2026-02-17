import pyodbc
import html

CONN_STR = (
    "DRIVER={ODBC Driver 18 for SQL Server};"
    "SERVER=localhost;"
    "DATABASE=CIA_WorldFactbook;"
    "Trusted_Connection=yes;"
    "TrustServerCertificate=yes;"
)

conn = pyodbc.connect(CONN_STR)
cursor = conn.cursor()

# Get a sample from 2020
print("=== Sample from 2020 (HTML source) ===")
cursor.execute("SELECT TOP 5 Code, Name FROM Countries WHERE Year = 2020 AND Code IN ('af', 'us', 'ch')")
for code, name in cursor.fetchall():
    print(f"Code: '{code}' | Name: '{name}' | Repr: {repr(name)}")

# Get sample from 2021
print("\n=== Sample from 2021 (JSON source) ===")
cursor.execute("SELECT TOP 5 Code, Name FROM Countries WHERE Year = 2021 AND Code IN ('AF', 'US', 'CH')")
for code, name in cursor.fetchall():
    print(f"Code: '{code}' | Name: '{name}' | Repr: {repr(name)}")

# Check what's in MasterCountries
print("\n=== MasterCountries (what we created) ===")
cursor.execute("SELECT TOP 10 CanonicalCode, CanonicalName FROM MasterCountries WHERE CanonicalCode IN ('AF', 'US', 'CH') ORDER BY CanonicalCode")
for code, name in cursor.fetchall():
    print(f"Code: '{code}' | Name: '{name}' | Repr: {repr(name)}")

conn.close()
