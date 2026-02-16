"""
CIA Factbook Archive - Field Name Mapper
========================================
Maps the 1,090 distinct FieldName variants in CountryFields to canonical
(modern / standardized) names.  Creates a FieldNameMappings lookup table
so the original data stays untouched.

Phase 1 (default): READ-ONLY — prints proposed mappings for review.
Phase 2 (--apply):  Creates FieldNameMappings table and inserts rows.

Run:  py build_field_mappings.py          # review mode
      py build_field_mappings.py --apply  # write to database
"""
import pyodbc
import re
import sys

CONN_STR = (
    "DRIVER={ODBC Driver 18 for SQL Server};"
    "SERVER=localhost;"
    "DATABASE=CIA_WorldFactbook;"
    "Trusted_Connection=yes;"
    "TrustServerCertificate=yes;"
)

# ============================================================
#  Rule 3: Known CIA renames  (old name -> modern canonical)
# ============================================================
KNOWN_RENAMES = {
    # --- Pre-standard era (1990-1996) -> standard ---
    "Agriculture":                          "Agricultural products",
    "Comparative area":                     "Area - comparative",
    "Total area":                           "Area",
    "Ethnic divisions":                     "Ethnic groups",
    "Language":                             "Languages",
    "Religion":                             "Religions",
    "Disputes":                             "Disputes - international",
    "International disputes":               "Disputes - international",
    "Environment":                          "Environment - current issues",
    "Type":                                 "Government type",
    "Type of government":                   "Government type",
    "Leaders":                              "Executive branch",
    "Branches":                             "Military and security forces",  # Military branches (under Defense Forces category)
    "Overview":                             "Economic overview",
    "Telecommunications":                   "Telecommunication systems",
    "Railroads":                            "Railways",
    "Highways":                             "Roadways",
    "Organized labor":                      "Organized labor",  # Trade unions, not total workforce
    "National product":                     "Real GDP (purchasing power parity)",
    "National product per capita":          "Real GDP per capita",
    "National product real growth rate":    "Real GDP growth rate",
    "US diplomatic representation":         "Diplomatic representation from the US",
    "Diplomatic representation in US":      "Diplomatic representation in the US",
    "Civil air":                            "Civil air",  # Aircraft fleet data, not airport counts
    "Airfield":                             "Airports",
    "Airport":                              "Airports",
    "Defense expenditures":                 "Military expenditures",
    "Unemployment":                         "Unemployment rate",
    "Television":                           "Broadcast media",
    "Televisions":                          "Televisions",  # Device count owned by population, not broadcast infrastructure
    "Aid":                                  "Aid",  # Foreign aid commitments, not government budget
    "Diplomatic representation":            "Diplomatic representation in the US",
    "Land area":                            "Area",
    "Territorial sea":                      "Maritime claims",

    # --- Modern era renames (CIA renamed for clarity) ---
    "Economy - overview":                   "Economic overview",
    "Agriculture - products":               "Agricultural products",
    "GDP (purchasing power parity)":        "Real GDP (purchasing power parity)",
    "GDP - real growth rate":               "Real GDP growth rate",
    "GDP real growth rate":                 "Real GDP growth rate",
    "GDP - per capita":                     "Real GDP per capita",
    "GDP - per capita (PPP)":               "Real GDP per capita",
    "GDP per capita":                       "Real GDP per capita",
    "GDP":                                  "Real GDP (purchasing power parity)",
    "GDP composition by sector":            "GDP - composition, by sector of origin",
    "GDP - composition by sector":          "GDP - composition, by sector of origin",
    "Elevation extremes":                   "Elevation",
    "Telephone system":                     "Telecommunication systems",
    "Telephones - main lines in use":       "Telephones - fixed lines",
    "Telephones":                           "Telephones - fixed lines",
    "telephone":                            "Telephones - fixed lines",
    "Distribution of family income - Gini index": "Gini Index coefficient - distribution of family income",
    "Unemployment, youth ages 15-24":       "Youth unemployment rate (ages 15-24)",
    "Military branches":                    "Military and security forces",
    "Maternal mortality rate":              "Maternal mortality ratio",
    "Physicians density":                   "Physician density",
    "Radio broadcast stations":             "Broadcast media",
    "Television broadcast stations":        "Broadcast media",
    "Television-broadcast stations":        "Broadcast media",
    "Radio":                                "Broadcast media",
    "Radios":                               "Radios",  # Device count owned by population, not broadcast infrastructure
    "Environment - international agreements": "International environmental agreements",
    "Ports and terminals":                  "Ports",
    "Ports and harbors":                    "Ports",
    "National anthem":                      "National anthem(s)",
    "Political parties and leaders":        "Political parties",
    "Political pressure groups and leaders": "Political parties",
    "Flag description":                     "Flag",
    "Waterways":                            "Waterways",
    "Inland waterways":                     "Waterways",
    "Area Rankings":                        "Area - rankings",
    "Reserves of foreign exchange & gold":  "Reserves of foreign exchange and gold",
    "Transportation note":                  "Transportation - note",
    "Education expenditures":               "Education expenditure",
    "Health expenditures":                  "Health expenditure",
    "International law organization participation": "International law organization participation",
    "Currency":                             "Exchange rates",
    "Currency code":                        "Exchange rates",
    "Currency (code)":                      "Exchange rates",
    "Appendix A":                           "Appendix A",
    "Appendix B":                           "Appendix B",
    "Appendix C":                           "Appendix C",
    "Appendix D":                           "Appendix D",
    "Appendix E":                           "Appendix E",
    "Appendix F":                           "Appendix F",
    "Appendix G":                           "Appendix G",
    "Appendix H":                           "Appendix H",
    "Carbon dioxide emissions from consumption of energy": "Carbon dioxide emissions",
    "Terrorist groups - foreign based":     "Terrorist group(s)",
    "Terrorist groups - home based":        "Terrorist group(s)",

    # --- More pre-standard era renames ---
    "External debt":                        "Debt - external",
    "Geographic note":                      "Geography - note",
    "Defense note":                         "Military - note",
    "Government note":                      "Government - note",
    "Communications note":                  "Communications - note",
    "Name of country":                      "Country name",
    "Names":                                "Country name",
    "Long-form name":                       "Country name",
    "National capital":                     "Capital",
    "National holidays":                    "National holiday",
    "Exchange rate":                        "Exchange rates",
    "Industrial production":                "Industrial production growth rate",
    "Industry":                             "Industries",
    "Land boundary":                        "Land boundaries",
    "Manpower availability":                "Manpower availability",  # Males 15-49 fit for service (demographic, not actual personnel)
    "GNP":                                  "GNP",  # Gross National Product — different measure from GDP (used 1990-1992)
    "Growth rate (population)":             "Population growth rate",
    "Current Health Expenditure":           "Current health expenditure",
    "GDP (purchasing power parity) - real": "Real GDP (purchasing power parity)",
    "Inflation rate - consumer price index": "Inflation rate (consumer prices)",
    "Major cities - population":            "Major urban areas - population",
    "Head of Government":                   "Executive branch",
    "Chief of State":                       "Executive branch",
    "Elections":                            "Executive branch",
    "Member of":                            "International organization participation",
    "Other political or pressure groups":   "Political parties",
    "Other political pressure groups":      "Political parties",
    "Other political groups":               "Political parties",
    "Current issues":                       "Environment - current issues",
    "Dependent area":                       "Dependency status",
    "Economic aid":                         "Economic aid",
    "Economic aid - donor":                 "Economic aid",
    "Economic aid - recipient":             "Economic aid",
    "Communists":                           "Political parties",
    "Legislature":                          "Legislative branch",
    "Telephone":                            "Telecommunication systems",
    "Internet":                             "Internet users",
    "Internet Service Providers (ISPs)":    "Internet users",
    "Internet hosts":                       "Internet users",
    "FAX":                                  "Diplomatic representation in the US",
    "Gross national saving":                "Gross national saving",
    "Ease of Doing Business Index scores":  "Ease of Doing Business Index scores",
    "Maritime threats":                     "Maritime threats",
    "Child labor - children ages 5-14":     "Child labor - children ages 5-14",
    "Labor force - by occupation":          "Labor force - by occupation",
    "Demographic profile":                  "Demographic profile",

    # --- Legitimate fields dropped before 2024 (map to themselves) ---
    "Airports - with paved runways":        "Airports - with paved runways",
    "Airports - with unpaved runways":      "Airports - with unpaved runways",
    "Fiscal year":                          "Fiscal year",
    "Icebreakers":                          "Icebreakers",
    "Economy of the area administered by Turkish Cypriots": "Economy of the area administered by Turkish Cypriots",
    "HIV/AIDS - adult prevalence rate":     "HIV/AIDS - adult prevalence rate",
    "HIV/AIDS - deaths":                    "HIV/AIDS - deaths",
    "HIV/AIDS - people living with HIV/AIDS": "HIV/AIDS - people living with HIV/AIDS",
    "Stock of broad money":                 "Stock of broad money",
    "Stock of narrow money":                "Stock of narrow money",
    "Stock of money":                       "Stock of narrow money",
    "Stock of quasi money":                 "Stock of narrow money",
    "Stock of domestic credit":             "Stock of domestic credit",
    "Stock of direct foreign investment - at home": "Stock of direct foreign investment - at home",
    "Stock of direct foreign investment - abroad": "Stock of direct foreign investment - abroad",
    "Market value of publicly traded shares": "Market value of publicly traded shares",
    "Commercial bank prime lending rate":   "Commercial bank prime lending rate",
    "Central bank discount rate":           "Central bank discount rate",
    "Investment (gross fixed)":             "Investment (gross fixed)",
    "Budget surplus (+) or deficit (-)":    "Budget surplus (+) or deficit (-)",
    "Taxes and other revenues":             "Taxes and other revenues",
    "Population - distribution":            "Population distribution",
    "Population below poverty line":        "Population below poverty line",
    "Freshwater withdrawal (domestic/industrial/agricultural)": "Total water withdrawal",
    "Major infectious diseases":            "Major infectious diseases",
    "Credit ratings":                       "Credit ratings",
    "Food insecurity":                      "Food insecurity",
}

# ============================================================
#  Rule 4: Consolidation  (sub-field -> parent aggregate)
# ============================================================
CONSOLIDATION_MAP = {
    # Oil sub-fields -> Petroleum
    "Oil - production":                     "Petroleum",
    "Oil - consumption":                    "Petroleum",
    "Oil - exports":                        "Petroleum",
    "Oil - imports":                        "Petroleum",
    "Oil - proved reserves":                "Petroleum",
    # Crude oil
    "Crude oil - production":               "Petroleum",
    "Crude oil - exports":                  "Petroleum",
    "Crude oil - imports":                  "Petroleum",
    "Crude oil - proved reserves":          "Petroleum",
    # Refined petroleum
    "Refined petroleum products - production":   "Petroleum",
    "Refined petroleum products - consumption":  "Petroleum",
    "Refined petroleum products - exports":      "Petroleum",
    "Refined petroleum products - imports":       "Petroleum",
    # Natural gas sub-fields
    "Natural gas - production":             "Natural gas",
    "Natural gas - consumption":            "Natural gas",
    "Natural gas - exports":                "Natural gas",
    "Natural gas - imports":                "Natural gas",
    "Natural gas - proved reserves":        "Natural gas",
    # Electricity sub-fields
    "Electricity - production":             "Electricity",
    "Electricity - consumption":            "Electricity",
    "Electricity - exports":                "Electricity",
    "Electricity - imports":                "Electricity",
    "Electricity - installed generating capacity": "Electricity",
    "Electricity - from fossil fuels":      "Electricity generation sources",
    "Electricity - from hydroelectric plants": "Electricity generation sources",
    "Electricity - from nuclear fuels":     "Electricity generation sources",
    "Electricity - from other renewable sources": "Electricity generation sources",
    "Electricity - production by source":   "Electricity generation sources",
    "Electricity production by source":     "Electricity generation sources",
    # Military manpower -> personnel strengths
    "Military manpower - availability":             "Military and security service personnel strengths",
    "Military manpower - fit for military service": "Military and security service personnel strengths",
    "Military manpower - reaching military age annually": "Military service age and obligation",
    "Military manpower - military age":             "Military service age and obligation",
    "Military manpower - military age and obligation": "Military service age and obligation",
    "Manpower available for military service":      "Military and security service personnel strengths",
    "Manpower fit for military service":            "Military and security service personnel strengths",
    "Manpower reaching military service age annually": "Military service age and obligation",
    "Manpower reaching militarily significant age annually": "Military service age and obligation",
    "Military expenditures - dollar figure":        "Military expenditures",
    "Military expenditures - percent of GDP":       "Military expenditures",
    "Military manpower":                            "Military and security service personnel strengths",
    # Maritime claims sub-fields (1990s separate entries -> consolidated)
    "Contiguous zone":                              "Maritime claims",
    "Continental shelf":                            "Maritime claims",
    "Exclusive economic zone":                      "Maritime claims",
    "Exclusive fishing zone":                       "Maritime claims",
    "Extended economic zone":                       "Maritime claims",
    "Gulf of Sidra closing line":                   "Maritime claims",
    "Military boundary line":                       "Maritime claims",
    # Electricity sub-fields (1997 only)
    "Electricity - capacity":                       "Electricity",
    "Electricity - consumption per capita":         "Energy consumption per capita",
}

# ============================================================
#  Rule 5: Country-specific government body keywords
# ============================================================
GOV_BODY_KEYWORDS = [
    "Assembly", "Senate", "Parliament", "Congress", "Council",
    "Chamber", "House of", "Duma", "Diet", "Sejm", "Seimas",
    "Storting", "Bundestag", "Bundesrat", "Majlis", "Shura",
    "Tribunal", "Court", "Staten", "Knesset", "Hural",
    "Sobranje", "Soviet", "Keneshom", "Folketing", "Fono",
    "Legislative Yuan", "Lagting", "Majilis",
    "Presidential Administration", "Group of Assistants",
    "Armed Forces", "KRAF",
]


def connect_db():
    return pyodbc.connect(CONN_STR)


# ============================================================
#  Dash normalization  (Rule 2)
# ============================================================
DASH_RE = re.compile(r'^(.+?)(?:--|(?<! )-)(.+)$')

def normalize_dashes(name):
    """Convert 'Economy-overview' or 'Economy--overview' to 'Economy - overview'."""
    m = DASH_RE.match(name)
    if m:
        left = m.group(1).strip()
        right = m.group(2).strip()
        return f"{left} - {right}"
    return None


# ============================================================
#  Noise detection  (Rule 6)
# ============================================================
NOISE_PHRASES = [
    "consists mainly of", "includes the following", "seat distribution",
    "coalition of", "made up of", "as follows", "countries have figures",
    "underdeveloped countries", "undeveloped countries", "search for",
    "mailing address", "were held at", "mutually supportive",
    "types of finished intelligence", "may be categorized",
    "pending acceptable definition", "one additional caution",
    "real output has remained", "party ruling coalition",
    "anti-market and", "union, two german", "factbook that may",
    "acceptable definition of the boundaries",
    "comments and queries are welcome",
]

# 1994-era sub-field labels that are fragments of parent fields.
# These appear as standalone field names due to how the 1994 HTML was parsed.
SUB_FIELD_LABELS = {
    "adjective", "arable land", "by occupation", "cabinet", "capacity",
    "chancery", "chief of mission", "chief of state",
    "chief of state and head of government",
    "commodities", "consulate(s)", "consulate(s) general",
    "consumption per capita", "conventional long form",
    "conventional short form", "donor", "eastern", "embassy",
    "expenditures", "female", "forest and woodland", "former",
    "international agreements", "local long form", "local short form",
    "male", "meadows and pastures", "noun", "other", "partners",
    "paved", "permanent crops", "production", "recipient", "revenues",
    "total", "total population", "unpaved", "usable", "western",
    "south", "southeast", "southwest", "north", "northeast", "northwest",
    "head of government", "election results", "elections", "water area",
    "branch office", "undifferentiated", "tatal population",
    "western-donor", "business organizations",
    "supreme leader and functional chief of state",
}

# Regional/sub-country entries from 1990s data (Cyprus Turkish area,
# Serbia splits, Malaysia state breakdowns, Netherlands Antilles islands, etc.)
REGIONAL_ENTRIES = {
    "Turkish Area", "Turkish area", "Turkish Cypriot area",
    "Turkish area - agriculture", "Turkish area - industry",
    "Turkish area - paved", "Turkish area - services",
    "Turkish area - total", "Turkish area - unpaved", "Turkish sector",
    "Serbia", "Serbia - 0-14 years", "Serbia - 15-64 years",
    "Serbia - 65 years and over", "Serbia - all ages",
    "Serbia - at birth", "Serbia - female", "Serbia - male",
    "Serbia - males age 15-49", "Serbia - males fit for military service",
    "Serbia - total population", "Serbia - under 15 years",
    "Sabah", "Sarawak", "Bonaire", "Sint Eustatius", "Sint Maarten",
    "Saba", "Wales", "Scotland", "Zanzibar", "West Island",
    "Republika Srpska", "Republic",
    "Swiss nationals",
    # Montenegro splits
    "Montenegro", "Montenegro - 0-14 years", "Montenegro - 15-64 years",
    "Montenegro - 65 years and over", "Montenegro - all ages",
    "Montenegro - at birth", "Montenegro - female", "Montenegro - male",
    "Montenegro - males age 15-49", "Montenegro - males fit for military service",
    "Montenegro - males reach military age (19) annually",
    "Montenegro - total population", "Montenegro - under 15 years",
    # Cyprus Greek area splits
    "Greek area", "Greek area - agriculture", "Greek area - industry",
    "Greek area - paved", "Greek area - recipient", "Greek area - services",
    "Greek area - total", "Greek area - unpaved", "Greek sector",
    "Greek Cypriot", "Cypriot area",
    # UK constituent countries
    "England", "Northern Ireland",
    # Germany / Herzegovina / Morocco
    "Germany", "Herzegovina", "Morocco",
    # Netherlands Antilles islands
    "Curacao",
    # Malaysia state breakdowns
    "Peninsular Malaysia", "Home Island",
    # Misc regional
    "Canadian dollars", "French francs", "German deutsche marks",
    "Italian lire", "Japanese yen", "British pounds",
    "Summer (January) population", "Summer only stations",
    "Summer-only stations", "Winter (July) population",
    "Year-round stations",
    "British pounds",
}

# Misc reference entries that are neither real fields nor noise
MISC_REFERENCE = {
    "Appendixes", "Antarctic Treaty Summary", "Terminology",
    "Telephone numbers", "Reference maps", "Transnational Issues",
    "Transportation", "United Nations System",
    "Web uniform resource locator (URL)", "Weights and measures",
    "ACIC M 49-1", "Abbreviation", "Abbreviations", "Affiliation",
    "Data code", "Digraph", "Years",
    "Shipyards and Ship Building", "World Cup 2022",
    "Dates of information", "Entities", "Money figures",
    "FIPS 10-4", "ISO 3166", "IHO 23-3rd", "IHO 23-4th",
    "DIAM 65-18", "ACIC M 49-1",
    "Country map", "Flag graphic", "Geographic names", "Maps",
    "Reference maps", "GDP methodology", "GNP/GDP methodology",
    "Gross domestic product", "Gross domestic product (GDP)",
    "Gross national product", "Gross national product (GNP)",
    "Gross world product", "Gross world product (GWP)",
    "GWP (gross world product)", "Economy",
    "Geography", "People", "Communications", "Military",
    "Introduction", "International organizations",
    "Mail", "Note", "Notes", "Historical perspective",
    "Data codes-country", "Data codes-hydrographic",
    "Digraphs", "Member",
    "Environmental Agreements and Appendix E",
    "Environmental agreements", "Other agreements",
}

def is_noise(name, use_count, first_year, last_year):
    """Identify parser artifacts and text fragments."""
    # Single or two-letter entries
    if len(name) <= 2 and name.isalpha():
        return True
    # Abbreviation/glossary entries like avdp., c.i.f., est.
    if name.endswith('.') and len(name) <= 6:
        return True
    # All-caps country codes appearing as field names (UAE, UK, US, etc.)
    if name.isupper() and len(name) <= 4 and use_count <= 5:
        return True
    # Starts with lowercase — almost certainly a fragment
    if name and name[0].islower() and use_count <= 10:
        return True
    # Very long descriptive fragments
    if len(name) > 80 and use_count <= 3:
        return True
    # Known noise phrases
    lower = name.lower()
    if any(p in lower for p in NOISE_PHRASES):
        return True
    # Runway sub-fields (parser artifacts from 1994)
    if name.startswith("with run"):
        return True
    if name.startswith("with permanent"):
        return True
    # Article sub-fields from Antarctic Treaty parsing
    if re.match(r'^Articles? \d', name):
        return True
    # Geographic fragments containing commas (e.g. province lists)
    if ',' in name and use_count <= 3 and len(name) > 40:
        return True
    # 1994 sub-field labels
    if name in SUB_FIELD_LABELS:
        return True
    # Political party/faction names from 1990s
    if last_year <= 2001 and use_count <= 10:
        party_kw = ["parties", "Bloc", "Rightist", "Leftist", "Populist",
                     "Resistance forces", "Ruling coalition", "umbrella group",
                     "Africans", "People's Army"]
        if any(kw.lower() in name.lower() for kw in party_kw):
            return True
    # Lowercase field names from 1994 with high counts (sub-field fragments)
    if name and name[0].islower() and first_year <= 1998:
        return True
    # Catch-all for very small entries ending before 2001
    if use_count <= 5 and last_year <= 2001 and len(name) < 40:
        return True
    # Specific noise patterns
    if name.startswith("US--") or name.startswith("US as "):
        return True
    if "includes" in name and use_count <= 5:
        return True
    if name.endswith(")") and use_count <= 3 and last_year <= 2001:
        return True
    return False


# ============================================================
#  Country-specific government body detection  (Rule 5)
# ============================================================
def is_gov_body(name, use_count, first_year, last_year):
    """Detect 1990s country-specific government body field names."""
    if last_year > 2001:
        return False
    if use_count > 100:
        return False
    for kw in GOV_BODY_KEYWORDS:
        if kw in name:
            return True
    return False


# ============================================================
#  Main mapping logic
# ============================================================
def build_mappings(cursor):
    """Build the complete mapping for all distinct field names."""
    # Step 1: Get all distinct field names with metadata
    cursor.execute("""
        SELECT cf.FieldName,
               MIN(c.Year) AS FirstYear,
               MAX(c.Year) AS LastYear,
               COUNT(*)    AS UseCount
        FROM CountryFields cf
        JOIN Countries c ON cf.CountryID = c.CountryID
        GROUP BY cf.FieldName
    """)
    all_fields = cursor.fetchall()

    # Step 2: Get the 2025 canonical field names (identity set)
    cursor.execute("""
        SELECT DISTINCT cf.FieldName
        FROM CountryFields cf
        JOIN Countries c ON cf.CountryID = c.CountryID
        WHERE c.Year = 2025
    """)
    canonical_2025 = {row[0] for row in cursor.fetchall()}

    # Also include 2024 for fields that may have been dropped in 2025
    cursor.execute("""
        SELECT DISTINCT cf.FieldName
        FROM CountryFields cf
        JOIN Countries c ON cf.CountryID = c.CountryID
        WHERE c.Year = 2024
    """)
    canonical_2024 = {row[0] for row in cursor.fetchall()}
    modern_names = canonical_2025 | canonical_2024

    mappings = []
    for original, first_year, last_year, use_count in all_fields:
        row = apply_rules(original, first_year, last_year, use_count,
                          modern_names)
        mappings.append(row)

    return mappings


def apply_rules(original, first_year, last_year, use_count, modern_names):
    """Apply mapping rules in priority order.  First match wins.

    Returns: (original, canonical, mapping_type, consolidated_to,
              is_noise, first_year, last_year, use_count, notes)
    """
    # Rule 1: Identity — field exists in current data
    if original in modern_names and original not in KNOWN_RENAMES:
        return (original, original, "identity", None,
                False, first_year, last_year, use_count, None)

    # Rule 2: Dash normalization (1998 single-dash, 1999 double-dash)
    normalized = normalize_dashes(original)
    if normalized:
        # Check if normalized form is itself a known rename
        if normalized in KNOWN_RENAMES:
            canon = KNOWN_RENAMES[normalized]
            return (original, canon, "dash_format", None,
                    False, first_year, last_year, use_count,
                    f"dash -> {normalized} -> {canon}")
        # Check if normalized form is a modern name
        if normalized in modern_names:
            return (original, normalized, "dash_format", None,
                    False, first_year, last_year, use_count,
                    f"dash -> {normalized}")
        # Check consolidation
        if normalized in CONSOLIDATION_MAP:
            return (original, normalized, "dash_format", CONSOLIDATION_MAP[normalized],
                    False, first_year, last_year, use_count,
                    f"dash -> {normalized} (consolidated)")

    # Rule 3: Known CIA renames
    if original in KNOWN_RENAMES:
        canon = KNOWN_RENAMES[original]
        return (original, canon, "rename", None,
                False, first_year, last_year, use_count, None)

    # Rule 4: Consolidation (sub-fields merged into parent)
    if original in CONSOLIDATION_MAP:
        return (original, original, "consolidation", CONSOLIDATION_MAP[original],
                False, first_year, last_year, use_count, None)

    # Rule 5: Country-specific government bodies
    if is_gov_body(original, use_count, first_year, last_year):
        return (original, "Legislative branch", "country_specific", None,
                False, first_year, last_year, use_count, None)

    # Rule 5b: Regional sub-entries (Cyprus Turkish area, Serbia splits, etc.)
    if original in REGIONAL_ENTRIES:
        return (original, original, "country_specific", None,
                False, first_year, last_year, use_count, "regional sub-entry")

    # Rule 5c: Misc reference entries (appendixes, glossary, etc.)
    if original in MISC_REFERENCE:
        return (original, original, "country_specific", None,
                False, first_year, last_year, use_count, "reference entry")

    # Rule 6: Noise / parser artifacts
    if is_noise(original, use_count, first_year, last_year):
        return (original, original, "noise", None,
                True, first_year, last_year, use_count, None)

    # Rule 7: Unmapped — keep original, flag for review
    return (original, original, "manual", None,
            False, first_year, last_year, use_count, None)


# ============================================================
#  Display
# ============================================================
def print_results(mappings):
    """Print mappings grouped by type."""
    by_type = {}
    for m in mappings:
        mtype = m[2]
        if mtype not in by_type:
            by_type[mtype] = []
        by_type[mtype].append(m)

    type_order = ["identity", "dash_format", "rename", "consolidation",
                  "country_specific", "noise", "manual"]
    for mtype in type_order:
        entries = by_type.get(mtype, [])
        if not entries:
            continue
        print(f"\n{'=' * 70}")
        print(f"  {mtype.upper()} ({len(entries)} fields)")
        print(f"{'=' * 70}")
        for (orig, canon, _, consol, noise, fy, ly, uc, notes) in sorted(entries, key=lambda x: x[0]):
            if mtype == "noise":
                print(f"  {orig[:55]:<55}  ({fy}-{ly}, n={uc})")
            elif mtype == "consolidation":
                print(f"  {orig[:45]:<45} -> {consol}")
            elif orig == canon:
                print(f"  {orig[:55]:<55}  ({fy}-{ly}, n={uc})")
            else:
                print(f"  {orig[:40]:<40} -> {canon}")
                if notes:
                    print(f"    {notes}")

    # Summary
    print(f"\n{'=' * 70}")
    print("  SUMMARY")
    print(f"{'=' * 70}")
    for mtype in type_order:
        count = len(by_type.get(mtype, []))
        if count:
            print(f"  {mtype:<20} {count:>5}")
    print(f"  {'TOTAL':<20} {len(mappings):>5}")


# ============================================================
#  Apply — create table and insert
# ============================================================
def apply_to_db(cursor, conn, mappings):
    """Create FieldNameMappings table and insert all rows."""
    print("\n--- Creating FieldNameMappings table ---")

    # Drop if exists, then create
    cursor.execute("""
        IF OBJECT_ID('FieldNameMappings', 'U') IS NOT NULL
            DROP TABLE FieldNameMappings
    """)
    cursor.execute("""
        CREATE TABLE FieldNameMappings (
            MappingID       INT IDENTITY(1,1) PRIMARY KEY,
            OriginalName    NVARCHAR(200)   NOT NULL,
            CanonicalName   NVARCHAR(200)   NOT NULL,
            MappingType     NVARCHAR(30)    NOT NULL,
            ConsolidatedTo  NVARCHAR(200)   NULL,
            IsNoise         BIT             NOT NULL DEFAULT 0,
            FirstYear       INT             NULL,
            LastYear        INT             NULL,
            UseCount        INT             NULL,
            Notes           NVARCHAR(500)   NULL,
            CONSTRAINT UQ_FieldNameMappings_OriginalName UNIQUE (OriginalName)
        )
    """)
    cursor.execute("""
        CREATE NONCLUSTERED INDEX IX_FieldNameMappings_CanonicalName
            ON FieldNameMappings (CanonicalName)
    """)

    # Insert all mappings
    inserted = 0
    for (orig, canon, mtype, consol, noise, fy, ly, uc, notes) in mappings:
        cursor.execute("""
            INSERT INTO FieldNameMappings
                (OriginalName, CanonicalName, MappingType, ConsolidatedTo,
                 IsNoise, FirstYear, LastYear, UseCount, Notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, orig, canon, mtype, consol, 1 if noise else 0, fy, ly, uc, notes)
        inserted += 1

    conn.commit()
    print(f"  Inserted {inserted} mapping rows.")


# ============================================================
#  Verification
# ============================================================
def verify(cursor):
    """Run verification checks after applying."""
    print("\n--- Verification ---")

    # Check 1: Every FieldName has a mapping
    cursor.execute("""
        SELECT COUNT(DISTINCT cf.FieldName) AS Total,
               COUNT(DISTINCT CASE WHEN fm.MappingID IS NOT NULL THEN cf.FieldName END) AS Mapped
        FROM CountryFields cf
        LEFT JOIN FieldNameMappings fm ON cf.FieldName = fm.OriginalName
    """)
    total, mapped = cursor.fetchone()
    status = "PASS" if total == mapped else "FAIL"
    print(f"  Coverage: {mapped}/{total} field names mapped  [{status}]")

    # Check 2: No duplicates
    cursor.execute("""
        SELECT OriginalName, COUNT(*) AS C
        FROM FieldNameMappings
        GROUP BY OriginalName
        HAVING COUNT(*) > 1
    """)
    dupes = cursor.fetchall()
    status = "PASS" if len(dupes) == 0 else "FAIL"
    print(f"  Duplicates: {len(dupes)}  [{status}]")

    # Check 3: Row count
    cursor.execute("SELECT COUNT(*) FROM FieldNameMappings")
    count = cursor.fetchone()[0]
    print(f"  Total rows in FieldNameMappings: {count}")

    # Check 4: Sample — US Population across years
    cursor.execute("""
        SELECT COUNT(DISTINCT c.Year) AS YearCount
        FROM CountryFields cf
        JOIN Countries c ON cf.CountryID = c.CountryID
        JOIN FieldNameMappings fm ON cf.FieldName = fm.OriginalName
        WHERE c.Name LIKE '%United States%'
          AND c.Name NOT LIKE '%Minor%'
          AND c.Name NOT LIKE '%Virgin%'
          AND fm.CanonicalName = 'Population'
    """)
    years = cursor.fetchone()[0]
    status = "PASS" if years >= 30 else "CHECK"
    print(f"  US Population years via mapping: {years}  [{status}]")

    # Check 5: Breakdown by type
    cursor.execute("""
        SELECT MappingType, COUNT(*) AS C
        FROM FieldNameMappings
        GROUP BY MappingType
        ORDER BY C DESC
    """)
    print(f"\n  By MappingType:")
    for mtype, c in cursor.fetchall():
        print(f"    {mtype:<20} {c:>5}")


# ============================================================
#  Main
# ============================================================
def main():
    apply_mode = "--apply" in sys.argv

    print("=" * 70)
    print("CIA FACTBOOK - FIELD NAME MAPPER")
    print("=" * 70)
    if apply_mode:
        print("MODE: APPLY (will create FieldNameMappings table)")
    else:
        print("MODE: REVIEW (read-only, run with --apply to write)")
    print()

    conn = connect_db()
    cursor = conn.cursor()

    mappings = build_mappings(cursor)
    print(f"Processed {len(mappings)} distinct field names.\n")

    print_results(mappings)

    if apply_mode:
        apply_to_db(cursor, conn, mappings)
        verify(cursor)
        print("\nDone! FieldNameMappings table created and populated.")
    else:
        print(f"\nReview the output above. If it looks good, run:")
        print(f"  py build_field_mappings.py --apply")

    cursor.close()
    conn.close()
    return 0


if __name__ == '__main__':
    exit(main())
