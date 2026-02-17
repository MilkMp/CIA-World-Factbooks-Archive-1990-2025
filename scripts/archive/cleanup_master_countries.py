"""
CIA Factbook Archive - MasterCountries Cleanup
===============================================
1. Fixes bad/garbage names from HTML parsing failures
2. Merges duplicate FIPS codes (same country, different codes across years)
3. Updates country names to modern official names
4. Adds ISOAlpha2 column using authoritative FIPS-to-ISO crosswalk
   Source: NGA GEC data via github.com/mysociety/gaze

Run: py cleanup_master_countries.py
"""
import pyodbc

CONN_STR = (
    "DRIVER={ODBC Driver 18 for SQL Server};"
    "SERVER=localhost;"
    "DATABASE=CIA_WorldFactbook;"
    "Trusted_Connection=yes;"
    "TrustServerCertificate=yes;"
)

# ============================================================
# FIPS 10-4 -> ISO 3166-1 Alpha-2 crosswalk
# Source: NGA Geopolitical Entities and Codes (GEC)
# via https://github.com/mysociety/gaze/blob/master/data/
#     fips-10-4-to-iso-country-codes.csv
# ============================================================
FIPS_TO_ISO = {
    "AF": "AF",  # Afghanistan
    "AX": None,  # Akrotiri (no ISO code — UK sovereign base)
    "AL": "AL",  # Albania
    "AG": "DZ",  # Algeria
    "AQ": "AS",  # American Samoa
    "AN": "AD",  # Andorra
    "AO": "AO",  # Angola
    "AV": "AI",  # Anguilla
    "AY": "AQ",  # Antarctica
    "AC": "AG",  # Antigua and Barbuda
    "AR": "AR",  # Argentina
    "AM": "AM",  # Armenia
    "AA": "AW",  # Aruba
    "AT": "AU",  # Ashmore and Cartier Islands (territory of Australia)
    "AS": "AU",  # Australia
    "AU": "AT",  # Austria
    "AJ": "AZ",  # Azerbaijan
    "BF": "BS",  # Bahamas
    "BA": "BH",  # Bahrain
    "FQ": "UM",  # Baker Island (US Minor Outlying Islands)
    "BG": "BD",  # Bangladesh
    "BB": "BB",  # Barbados
    "BS": "RE",  # Bassas da India (French territory near Reunion)
    "BO": "BY",  # Belarus
    "BE": "BE",  # Belgium
    "BH": "BZ",  # Belize
    "BN": "BJ",  # Benin
    "BD": "BM",  # Bermuda
    "BT": "BT",  # Bhutan
    "BL": "BO",  # Bolivia
    "BK": "BA",  # Bosnia and Herzegovina
    "BC": "BW",  # Botswana
    "BV": "BV",  # Bouvet Island
    "BR": "BR",  # Brazil
    "IO": "IO",  # British Indian Ocean Territory
    "BX": "BN",  # Brunei
    "BU": "BG",  # Bulgaria
    "UV": "BF",  # Burkina Faso
    "BM": "MM",  # Burma / Myanmar
    "BY": "BI",  # Burundi
    "CB": "KH",  # Cambodia
    "CM": "CM",  # Cameroon
    "CA": "CA",  # Canada
    "CV": "CV",  # Cape Verde
    "CJ": "KY",  # Cayman Islands
    "CT": "CF",  # Central African Republic
    "CD": "TD",  # Chad
    "CI": "CL",  # Chile
    "CH": "CN",  # China
    "KT": "CX",  # Christmas Island
    "IP": "PF",  # Clipperton Island
    "CK": "CC",  # Cocos (Keeling) Islands
    "CO": "CO",  # Colombia
    "CN": "KM",  # Comoros
    "CG": "CD",  # Congo (Democratic Republic)
    "CF": "CG",  # Congo (Republic)
    "CW": "CK",  # Cook Islands
    "CR": "AU",  # Coral Sea Islands (territory of Australia)
    "CS": "CR",  # Costa Rica
    "IV": "CI",  # Cote d'Ivoire
    "HR": "HR",  # Croatia
    "CU": "CU",  # Cuba
    "UC": "CW",  # Curacao
    "CY": "CY",  # Cyprus
    "EZ": "CZ",  # Czech Republic / Czechia
    "DA": "DK",  # Denmark
    "DX": None,  # Dhekelia (no ISO code — UK sovereign base)
    "DJ": "DJ",  # Djibouti
    "DO": "DM",  # Dominica
    "DR": "DO",  # Dominican Republic
    "EC": "EC",  # Ecuador
    "EG": "EG",  # Egypt
    "ES": "SV",  # El Salvador
    "EK": "GQ",  # Equatorial Guinea
    "ER": "ER",  # Eritrea
    "EN": "EE",  # Estonia
    "ET": "ET",  # Ethiopia
    "PJ": None,  # Etorofu/Habomai/Kunashiri/Shikotan (disputed)
    "EU": "RE",  # Europa Island (French territory)
    "FK": "FK",  # Falkland Islands
    "FO": "FO",  # Faroe Islands
    "FJ": "FJ",  # Fiji
    "FI": "FI",  # Finland
    "FR": "FR",  # France
    "FG": "GF",  # French Guiana
    "FP": "PF",  # French Polynesia
    "FS": "TF",  # French Southern and Antarctic Lands
    "GB": "GA",  # Gabon
    "GA": "GM",  # Gambia
    "GZ": "PS",  # Gaza Strip
    "GG": "GE",  # Georgia
    "GM": "DE",  # Germany
    "GH": "GH",  # Ghana
    "GI": "GI",  # Gibraltar
    "GO": "RE",  # Glorioso Islands (French territory)
    "GR": "GR",  # Greece
    "GL": "GL",  # Greenland
    "GJ": "GD",  # Grenada
    "GP": "GP",  # Guadeloupe
    "GQ": "GU",  # Guam
    "GT": "GT",  # Guatemala
    "GK": "GB",  # Guernsey
    "GV": "GN",  # Guinea
    "PU": "GW",  # Guinea-Bissau
    "GY": "GY",  # Guyana
    "HA": "HT",  # Haiti
    "HM": "HM",  # Heard Island and McDonald Islands
    "HO": "HN",  # Honduras
    "HK": "HK",  # Hong Kong
    "HQ": "UM",  # Howland Island (US Minor Outlying Islands)
    "HU": "HU",  # Hungary
    "IC": "IS",  # Iceland
    "IN": "IN",  # India
    "ID": "ID",  # Indonesia
    "IR": "IR",  # Iran
    "IZ": "IQ",  # Iraq
    "EI": "IE",  # Ireland
    "IM": "GB",  # Isle of Man (Crown dependency of UK)
    "IS": "IL",  # Israel
    "IT": "IT",  # Italy
    "JM": "JM",  # Jamaica
    "JN": "SJ",  # Jan Mayen
    "JA": "JP",  # Japan
    "DQ": "UM",  # Jarvis Island (US Minor Outlying Islands)
    "JE": "GB",  # Jersey
    "JQ": "UM",  # Johnston Atoll (US Minor Outlying Islands)
    "JO": "JO",  # Jordan
    "JU": "RE",  # Juan de Nova Island (French territory)
    "KZ": "KZ",  # Kazakhstan
    "KE": "KE",  # Kenya
    "KQ": "UM",  # Kingman Reef (US Minor Outlying Islands)
    "KR": "KI",  # Kiribati
    "KN": "KP",  # Korea, North
    "KS": "KR",  # Korea, South
    "KV": None,  # Kosovo (no universally assigned ISO code)
    "KU": "KW",  # Kuwait
    "KG": "KG",  # Kyrgyzstan
    "LA": "LA",  # Laos
    "LG": "LV",  # Latvia
    "LE": "LB",  # Lebanon
    "LT": "LS",  # Lesotho
    "LI": "LR",  # Liberia
    "LY": "LY",  # Libya
    "LS": "LI",  # Liechtenstein
    "LH": "LT",  # Lithuania
    "LU": "LU",  # Luxembourg
    "MC": "MO",  # Macau
    "MK": "MK",  # North Macedonia
    "MA": "MG",  # Madagascar
    "MI": "MW",  # Malawi
    "MY": "MY",  # Malaysia
    "MV": "MV",  # Maldives
    "ML": "ML",  # Mali
    "MT": "MT",  # Malta
    "RM": "MH",  # Marshall Islands
    "MB": "MQ",  # Martinique
    "MR": "MR",  # Mauritania
    "MP": "MU",  # Mauritius
    "MF": "YT",  # Mayotte
    "MX": "MX",  # Mexico
    "FM": "FM",  # Micronesia
    "MQ": "UM",  # Midway Islands (US Minor Outlying Islands)
    "MD": "MD",  # Moldova
    "MN": "MC",  # Monaco
    "MG": "MN",  # Mongolia
    "MJ": "ME",  # Montenegro
    "MH": "MS",  # Montserrat
    "MO": "MA",  # Morocco
    "MZ": "MZ",  # Mozambique
    "WA": "NA",  # Namibia
    "NR": "NR",  # Nauru
    "BQ": "UM",  # Navassa Island (US Minor Outlying Islands)
    "NP": "NP",  # Nepal
    "NL": "NL",  # Netherlands
    "NC": "NC",  # New Caledonia
    "NZ": "NZ",  # New Zealand
    "NU": "NI",  # Nicaragua
    "NG": "NE",  # Niger
    "NI": "NG",  # Nigeria
    "NE": "NU",  # Niue
    "NF": "NF",  # Norfolk Island
    "CQ": "MP",  # Northern Mariana Islands
    "NO": "NO",  # Norway
    "MU": "OM",  # Oman
    "PK": "PK",  # Pakistan
    "PS": "PW",  # Palau
    "LQ": "UM",  # Palmyra Atoll (US Minor Outlying Islands)
    "PM": "PA",  # Panama
    "PP": "PG",  # Papua New Guinea
    "PF": None,  # Paracel Islands (disputed, no ISO code)
    "PA": "PY",  # Paraguay
    "PE": "PE",  # Peru
    "RP": "PH",  # Philippines
    "PC": "PN",  # Pitcairn Islands
    "PL": "PL",  # Poland
    "PO": "PT",  # Portugal
    "RQ": "PR",  # Puerto Rico
    "QA": "QA",  # Qatar
    "RE": "RE",  # Reunion
    "RO": "RO",  # Romania
    "RS": "RU",  # Russia
    "RW": "RW",  # Rwanda
    "TB": "BL",  # Saint Barthelemy
    "SH": "SH",  # Saint Helena
    "SC": "KN",  # Saint Kitts and Nevis
    "ST": "LC",  # Saint Lucia
    "RN": "MF",  # Saint Martin
    "SB": "PM",  # Saint Pierre and Miquelon
    "VC": "VC",  # Saint Vincent and the Grenadines
    "WS": "WS",  # Samoa
    "SM": "SM",  # San Marino
    "TP": "ST",  # Sao Tome and Principe
    "SA": "SA",  # Saudi Arabia
    "SG": "SN",  # Senegal
    "RI": "RS",  # Serbia
    "SE": "SC",  # Seychelles
    "SL": "SL",  # Sierra Leone
    "SN": "SG",  # Singapore
    "NN": "SX",  # Sint Maarten
    "LO": "SK",  # Slovakia
    "SI": "SI",  # Slovenia
    "BP": "SB",  # Solomon Islands
    "SO": "SO",  # Somalia
    "SF": "ZA",  # South Africa
    "SX": "GS",  # South Georgia and the South Sandwich Islands
    "OD": "SS",  # South Sudan
    "SP": "ES",  # Spain
    "PG": None,  # Spratly Islands (disputed, no ISO code)
    "CE": "LK",  # Sri Lanka
    "SU": "SD",  # Sudan
    "NS": "SR",  # Suriname
    "SV": "SJ",  # Svalbard
    "WZ": "SZ",  # Eswatini (formerly Swaziland)
    "SW": "SE",  # Sweden
    "SZ": "CH",  # Switzerland
    "SY": "SY",  # Syria
    "TW": "TW",  # Taiwan
    "TI": "TJ",  # Tajikistan
    "TZ": "TZ",  # Tanzania
    "TH": "TH",  # Thailand
    "TT": "TL",  # Timor-Leste
    "TO": "TG",  # Togo
    "TL": "TK",  # Tokelau
    "TN": "TO",  # Tonga
    "TD": "TT",  # Trinidad and Tobago
    "TE": "UM",  # Tromelin Island (French territory)
    "TS": "TN",  # Tunisia
    "TU": "TR",  # Turkey / Turkiye
    "TX": "TM",  # Turkmenistan
    "TK": "TC",  # Turks and Caicos Islands
    "TV": "TV",  # Tuvalu
    "UG": "UG",  # Uganda
    "UP": "UA",  # Ukraine
    "AE": "AE",  # United Arab Emirates
    "UK": "GB",  # United Kingdom
    "US": "US",  # United States
    "UY": "UY",  # Uruguay
    "UZ": "UZ",  # Uzbekistan
    "NH": "VU",  # Vanuatu
    "VT": "VA",  # Vatican City / Holy See
    "VE": "VE",  # Venezuela
    "VM": "VN",  # Vietnam
    "VI": "VG",  # Virgin Islands (British)
    "VQ": "VI",  # Virgin Islands (U.S.)
    "WQ": "UM",  # Wake Island (US Minor Outlying Islands)
    "WF": "WF",  # Wallis and Futuna
    "WE": "PS",  # West Bank
    "WI": "EH",  # Western Sahara
    "YM": "YE",  # Yemen
    "ZA": "ZM",  # Zambia
    "ZI": "ZW",  # Zimbabwe
    # Dissolved / historical entities
    "NT": "AN",  # Netherlands Antilles (dissolved 2010, ISO AN now deleted)
    "YI": "CS",  # Serbia and Montenegro (dissolved 2006, ISO CS now deleted)
    "ZZ": None,  # Iles Eparses (no own ISO code)
    # Codes that appear in data but aren't standard FIPS —
    # likely came from JSON source using ISO codes directly
    "SS": "SS",  # South Sudan (ISO code, not FIPS — FIPS is OD)
    "VA": "VA",  # Vatican City (ISO code, not FIPS — FIPS is VT)
    "CC": "CC",  # Cocos (Keeling) Islands (same in both)
}

# ============================================================
# Name fixes for entries where HTML parser produced garbage
# ============================================================
NAME_FIXES = {
    "FQ": "Baker Island",
    "KQ": "Kingman Reef",
    "JQ": "Johnston Atoll",
    "MQ": "Midway Islands",
    "LQ": "Palmyra Atoll",
    "WQ": "Wake Island",
    "HQ": "Howland Island",
    "DQ": "Jarvis Island",
    "BQ": "Navassa Island",
    "IP": "Clipperton Island",
    "AT": "Ashmore and Cartier Islands",
    "CR": "Coral Sea Islands",
    "DX": "Dhekelia",
    "AX": "Akrotiri",
    "SS": "South Sudan",
    "VA": "Holy See (Vatican City)",
    "VT": "Holy See (Vatican City)",
    "OD": "South Sudan",
    "PJ": "Etorofu, Habomai, Kunashiri, and Shikotan Islands",
    "PF": "Paracel Islands",
    "PG": "Spratly Islands",
    "BS": "Bassas da India",
    "EU": "Europa Island",
    "GO": "Glorioso Islands",
    "JU": "Juan de Nova Island",
    "TE": "Tromelin Island",
    "ZZ": "Iles Eparses",
}

# ============================================================
# Merge duplicate codes — old FIPS -> modern FIPS
# Countries rows pointing to old get repointed to new
# ============================================================
CODE_MERGES = {
    "TC": "AE",   # United Arab Emirates (TC=Trucial States pre-1998)
    "FA": "FK",   # Falkland Islands (FA=old code pre-1991)
    "RB": "RI",   # Serbia (RB=post-split 2006, RI=post-Kosovo 2008)
    "SR": "YI",   # Serbia and Montenegro
    "SK": "NN",   # Sint Maarten (SK=old Sikkim code reused)
    "VA": "VT",   # Holy See — VA is ISO code from JSON, VT is FIPS
    "SS": "OD",   # South Sudan — SS is ISO code from JSON, OD is FIPS
}

# ============================================================
# Rename to modern official names (user chose modern names)
# ============================================================
NAME_UPDATES = {
    "EZ": "Czechia",
    "WZ": "Eswatini",
    "MK": "North Macedonia",
    "TU": "Turkiye",
    "IM": "Isle of Man",
    "BM": "Burma (Myanmar)",
    "NT": "Netherlands Antilles",
    "YI": "Serbia and Montenegro",
}


def connect_db():
    return pyodbc.connect(CONN_STR)


def diagnose(cursor):
    """Print current state of MasterCountries for review."""
    print("=" * 60)
    print("DIAGNOSTIC: Current MasterCountries State")
    print("=" * 60)

    cursor.execute("SELECT COUNT(*) FROM MasterCountries")
    print(f"Total master countries: {cursor.fetchone()[0]}")

    # Show entries with suspect names
    cursor.execute("""
        SELECT CanonicalCode, CanonicalName FROM MasterCountries
        WHERE CanonicalName IN ('CIA', 'Unknown', 'Redirect page',
              'Central Intelligence Agency', '')
        OR LEN(CanonicalName) < 3
        ORDER BY CanonicalCode
    """)
    suspect = cursor.fetchall()
    if suspect:
        print(f"\nEntries with suspect names ({len(suspect)}):")
        for code, name in suspect:
            print(f"  {code}: '{name}'")
    else:
        print("\nNo suspect names found.")

    # Show codes in CODE_MERGES
    print("\nDuplicate code pairs to merge:")
    for old_code, new_code in CODE_MERGES.items():
        cursor.execute("""
            SELECT CanonicalCode, CanonicalName FROM MasterCountries
            WHERE CanonicalCode IN (?, ?)
        """, old_code, new_code)
        rows = cursor.fetchall()
        for code, name in rows:
            print(f"  {code}: {name}")
        if len(rows) < 2:
            print(f"  NOTE: Only {len(rows)} of 2 exist for {old_code}/{new_code}")
        print()

    # CC/UC situation
    print("CC/UC (Curacao) check:")
    cursor.execute("""
        SELECT CanonicalCode, CanonicalName FROM MasterCountries
        WHERE CanonicalCode IN ('CC', 'UC')
    """)
    for code, name in cursor.fetchall():
        print(f"  {code}: {name}")

    cursor.execute("""
        SELECT DISTINCT c.Year, c.Code, c.Name
        FROM Countries c WHERE UPPER(c.Code) = 'CC'
        ORDER BY c.Year
    """)
    rows = cursor.fetchall()
    if rows:
        print("  CC in raw Countries table:")
        for year, code, name in rows:
            print(f"    {year}: {code} -> {name}")
    print()


def step1_fix_bad_names(cursor):
    """Fix entries where HTML parser produced garbage names."""
    print("--- Step 1: Fixing bad names ---")
    fixed = 0

    # Apply hardcoded name fixes
    for code, correct_name in NAME_FIXES.items():
        cursor.execute("""
            UPDATE MasterCountries SET CanonicalName = ?
            WHERE CanonicalCode = ?
            AND (CanonicalName IN ('CIA', 'Unknown', 'Redirect page',
                 'Central Intelligence Agency', '')
                 OR LEN(CanonicalName) < 3)
        """, correct_name, code)
        if cursor.rowcount > 0:
            print(f"  {code}: -> '{correct_name}'")
            fixed += 1

    # For any STILL-bad names, try to pull a good name from Countries table
    cursor.execute("""
        SELECT mc.MasterCountryID, mc.CanonicalCode, mc.CanonicalName
        FROM MasterCountries mc
        WHERE mc.CanonicalName IN ('CIA', 'Unknown', 'Redirect page',
              'Central Intelligence Agency', '')
        OR LEN(mc.CanonicalName) < 3
    """)
    remaining = cursor.fetchall()

    for master_id, code, bad_name in remaining:
        # Prefer JSON source (cleaner names)
        cursor.execute("""
            SELECT TOP 1 c.Name FROM Countries c
            WHERE c.MasterCountryID = ? AND c.Source = 'json'
            AND c.Name NOT IN ('CIA', 'Unknown', 'Redirect page', '')
            AND LEN(c.Name) > 2
        """, master_id)
        row = cursor.fetchone()

        if not row:
            # Fall back to HTML source, newest year
            cursor.execute("""
                SELECT TOP 1 c.Name FROM Countries c
                WHERE c.MasterCountryID = ? AND c.Source = 'html'
                AND c.Name NOT IN ('CIA', 'Unknown', 'Redirect page', '')
                AND LEN(c.Name) > 2
                ORDER BY c.Year DESC
            """, master_id)
            row = cursor.fetchone()

        if row:
            good_name = row[0].strip().rstrip(' \u2014').lstrip('\u2014 ')
            cursor.execute(
                "UPDATE MasterCountries SET CanonicalName = ? WHERE MasterCountryID = ?",
                good_name, master_id
            )
            print(f"  {code}: '{bad_name}' -> '{good_name}' (from Countries table)")
            fixed += 1
        else:
            print(f"  WARNING: {code} still has bad name '{bad_name}' - no good source")

    print(f"  Fixed: {fixed}")


def do_merge(cursor, old_code, new_code, label=""):
    """Merge old_code into new_code. Returns (success, message)."""
    cursor.execute(
        "SELECT MasterCountryID, CanonicalName FROM MasterCountries WHERE CanonicalCode = ?",
        old_code
    )
    old_row = cursor.fetchone()
    cursor.execute(
        "SELECT MasterCountryID, CanonicalName FROM MasterCountries WHERE CanonicalCode = ?",
        new_code
    )
    new_row = cursor.fetchone()

    if not old_row and not new_row:
        return False, f"FAIL {old_code}->{new_code}: neither code exists in MasterCountries"
    if not old_row:
        return False, f"SKIP {old_code}->{new_code}: {old_code} not in MasterCountries (already merged?)"
    if not new_row:
        return False, f"FAIL {old_code}->{new_code}: target {new_code} not in MasterCountries!"

    old_id, old_name = old_row
    new_id, _ = new_row

    if old_id == new_id:
        return False, f"SKIP {old_code}->{new_code}: same MasterCountryID ({old_id}), already merged"

    try:
        # Repoint Countries rows from old to new
        cursor.execute(
            "UPDATE Countries SET MasterCountryID = ? WHERE MasterCountryID = ?",
            new_id, old_id
        )
        repointed = cursor.rowcount

        # Verify no rows still point to old
        cursor.execute(
            "SELECT COUNT(*) FROM Countries WHERE MasterCountryID = ?", old_id
        )
        remaining = cursor.fetchone()[0]
        if remaining > 0:
            return False, (f"FAIL {old_code}->{new_code}: repointed {repointed} rows but "
                           f"{remaining} still reference old ID {old_id}")

        # Delete old MasterCountries entry
        cursor.execute(
            "DELETE FROM MasterCountries WHERE MasterCountryID = ?", old_id
        )
        if cursor.rowcount == 0:
            return False, f"FAIL {old_code}->{new_code}: DELETE returned 0 rows for ID {old_id}"

        desc = label or f"{old_name}"
        return True, f"OK   {old_code} -> {new_code} ({desc}, {repointed} rows repointed)"

    except Exception as e:
        return False, f"ERROR {old_code}->{new_code}: {e}"


def step2_merge_duplicate_codes(cursor):
    """Merge old FIPS codes into modern canonical ones."""
    print("\n--- Step 2: Merging duplicate codes ---")
    merged = 0
    failed = 0

    for old_code, new_code in CODE_MERGES.items():
        success, msg = do_merge(cursor, old_code, new_code)
        print(f"  {msg}")
        if success:
            merged += 1
        elif msg.startswith("  SKIP") or msg.startswith("SKIP"):
            pass  # already done, not a failure
        else:
            failed += 1

    # Handle CC/UC — only merge if CC is actually Curacao in our data
    cursor.execute(
        "SELECT DISTINCT c.Name FROM Countries c WHERE UPPER(c.Code) = 'CC'"
    )
    cc_names = [r[0] for r in cursor.fetchall()]
    is_curacao = any('cura' in n.lower() for n in cc_names)

    if is_curacao:
        success, msg = do_merge(cursor, "CC", "UC", label="Curacao")
        print(f"  {msg}")
        if success:
            merged += 1
        elif not msg.startswith("SKIP"):
            failed += 1
    else:
        print(f"  CC is NOT Curacao (names: {cc_names}), keeping separate")

    print(f"  Merged: {merged}", end="")
    if failed:
        print(f"  |  FAILED: {failed}")
    else:
        print()


def step3_update_names(cursor):
    """Update canonical names to modern official names."""
    print("\n--- Step 3: Updating country names ---")
    updated = 0

    for code, modern_name in NAME_UPDATES.items():
        cursor.execute(
            "UPDATE MasterCountries SET CanonicalName = ? WHERE CanonicalCode = ?",
            modern_name, code
        )
        if cursor.rowcount > 0:
            print(f"  {code}: -> '{modern_name}'")
            updated += 1

    print(f"  Updated: {updated}")


def step4_add_iso_column(cursor):
    """Add ISOAlpha2 column and populate from FIPS-to-ISO crosswalk."""
    print("\n--- Step 4: Adding ISOAlpha2 column ---")

    # Add the column if it doesn't exist
    cursor.execute("""
        IF NOT EXISTS (
            SELECT * FROM sys.columns
            WHERE object_id = OBJECT_ID('MasterCountries')
            AND name = 'ISOAlpha2'
        )
        BEGIN
            ALTER TABLE MasterCountries
            ADD ISOAlpha2 NVARCHAR(2) NULL
        END
    """)
    print("  Column added (or already exists)")

    # Populate from crosswalk
    cursor.execute("SELECT MasterCountryID, CanonicalCode FROM MasterCountries")
    all_rows = cursor.fetchall()

    mapped = 0
    unmapped = []
    for master_id, fips_code in all_rows:
        iso_code = FIPS_TO_ISO.get(fips_code)
        if iso_code:
            cursor.execute(
                "UPDATE MasterCountries SET ISOAlpha2 = ? WHERE MasterCountryID = ?",
                iso_code, master_id
            )
            mapped += 1
        else:
            unmapped.append(fips_code)

    print(f"  Mapped: {mapped}")
    if unmapped:
        print(f"  No ISO code for {len(unmapped)} entries: {', '.join(unmapped)}")
        print("  (These are disputed territories or sovereign bases with no ISO code)")


def verify(cursor):
    """Final verification report."""
    print("\n" + "=" * 60)
    print("VERIFICATION")
    print("=" * 60)

    cursor.execute("SELECT COUNT(*) FROM MasterCountries")
    count = cursor.fetchone()[0]
    print(f"Master countries: {count}")

    cursor.execute("SELECT COUNT(*) FROM Countries WHERE MasterCountryID IS NULL")
    orphans = cursor.fetchone()[0]
    if orphans > 0:
        print(f"WARNING: {orphans} Countries rows with NULL MasterCountryID!")
    else:
        print("All Countries rows have a MasterCountryID")

    # Bad names remaining?
    cursor.execute("""
        SELECT CanonicalCode, CanonicalName FROM MasterCountries
        WHERE CanonicalName IN ('CIA', 'Unknown', 'Redirect page',
              'Central Intelligence Agency', '')
        OR LEN(CanonicalName) < 3
    """)
    bad = cursor.fetchall()
    if bad:
        print(f"\nWARNING: {len(bad)} entries still have bad names:")
        for code, name in bad:
            print(f"  {code}: '{name}'")
    else:
        print("No remaining bad names")

    # ISO coverage
    cursor.execute("SELECT COUNT(*) FROM MasterCountries WHERE ISOAlpha2 IS NOT NULL")
    iso_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM MasterCountries WHERE ISOAlpha2 IS NULL")
    no_iso = cursor.fetchone()[0]
    print(f"ISO Alpha-2 mapped: {iso_count}/{count} ({no_iso} without ISO code)")

    # Full listing
    print(f"\nComplete MasterCountries listing ({count} entries):")
    print(f"  {'FIPS':<6} {'ISO':<5} {'Name'}")
    print(f"  {'----':<6} {'---':<5} {'----'}")
    cursor.execute("""
        SELECT CanonicalCode, ISOAlpha2, CanonicalName
        FROM MasterCountries
        ORDER BY CanonicalName
    """)
    for fips, iso, name in cursor.fetchall():
        iso_str = iso if iso else "--"
        print(f"  {fips:<6} {iso_str:<5} {name}")


def main():
    print("=" * 60)
    print("CIA FACTBOOK - MASTER COUNTRIES CLEANUP")
    print("=" * 60)

    conn = connect_db()
    cursor = conn.cursor()
    print("Connected to database.\n")

    # Diagnostic
    diagnose(cursor)

    # Step 1: Fix bad names
    step1_fix_bad_names(cursor)
    conn.commit()

    # Step 2: Merge duplicate codes
    step2_merge_duplicate_codes(cursor)
    conn.commit()

    # Step 3: Update renamed countries
    step3_update_names(cursor)
    conn.commit()

    # Step 4: Add ISO column
    step4_add_iso_column(cursor)
    conn.commit()

    # Verify
    verify(cursor)

    print("\nCleanup complete!")
    cursor.close()
    conn.close()
    return 0


if __name__ == '__main__':
    exit(main())
