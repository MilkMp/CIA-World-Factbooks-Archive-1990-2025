"""
Structured Field Parsing — Decompose CountryFields.Content into FieldValues
Reads from CIA_WorldFactbook, writes to CIA_WorldFactbook_Extended_Sub_Topics.
The original database is never modified.

Usage:
    python etl/structured_parsing/parse_field_values.py
"""
import pyodbc
import re
import sys
import time

# ============================================================
# DATABASE CONNECTIONS
# ============================================================
SOURCE_DB = "CIA_WorldFactbook"
TARGET_DB = "CIA_WorldFactbook_Extended_Sub_Topics"

CONN_STR_READ = (
    "DRIVER={ODBC Driver 18 for SQL Server};"
    "SERVER=localhost;"
    f"DATABASE={SOURCE_DB};"
    "Trusted_Connection=yes;"
    "TrustServerCertificate=yes;"
)
CONN_STR_WRITE = (
    "DRIVER={ODBC Driver 18 for SQL Server};"
    "SERVER=localhost;"
    f"DATABASE={TARGET_DB};"
    "Trusted_Connection=yes;"
    "TrustServerCertificate=yes;"
)

BATCH_SIZE = 10000

# ============================================================
# UTILITY FUNCTIONS
# ============================================================

def parse_number(s):
    """Parse a number string like '7,741,220' or '83.5' into a float."""
    if not s:
        return None
    s = s.strip().replace(',', '')
    try:
        return float(s)
    except ValueError:
        return None


def extract_date_est(s):
    """Extract '(2024 est.)' or '(FY93)' from a string."""
    m = re.search(r'\((\d{4}\s*est\.?)\)', s)
    if m:
        return m.group(1)
    m = re.search(r'\((FY\d{2,4}/?(?:\d{2})?)\)', s)
    if m:
        return m.group(1)
    m = re.search(r'\((\d{4})\)', s)
    if m:
        return m.group(1)
    return None


def extract_rank(s):
    """Extract 'country comparison to the world: N' as integer rank."""
    m = re.search(r'country comparison to the world:\s*(\d+)', s)
    if m:
        return int(m.group(1))
    return None


def normalize_content(content):
    """Normalize pipe delimiters and whitespace."""
    if not content:
        return ""
    # Remove 'country comparison to the world: N' before splitting
    content = re.sub(r'\s*\|?\s*country comparison to the world:\s*\d+', '', content)
    return content.strip()


def make_row(field_id, sub_field, numeric_val=None, units=None,
             text_val=None, date_est=None, rank=None):
    """Create a FieldValues row tuple."""
    return (field_id, sub_field, numeric_val, units, text_val, date_est, rank)


# ============================================================
# FIELD-SPECIFIC PARSERS
# Each returns a list of row tuples via make_row()
# ============================================================

def parse_area(field_id, content):
    """Area: total/land/water in sq km or km2."""
    rows = []
    rank = extract_rank(content)
    content = normalize_content(content)

    # Try labeled sub-fields: total/land/water/comparative
    for label in ['total area', 'total', 'land area', 'land', 'water']:
        pattern = re.escape(label) + r'\s*:?\s*([\d,]+)\s*(?:sq\s*km|km2)'
        m = re.search(pattern, content, re.IGNORECASE)
        if m:
            # Normalize label
            sub = label.replace(' area', '')
            rows.append(make_row(field_id, sub,
                                 numeric_val=parse_number(m.group(1)),
                                 units='sq km',
                                 date_est=extract_date_est(content),
                                 rank=rank if sub == 'total' else None))
    # Comparative area (text)
    m = re.search(r'comparative\s*(?:area)?\s*:?\s*(.+?)(?:\s*(?:note|$))', content, re.IGNORECASE)
    if m:
        rows.append(make_row(field_id, 'comparative', text_val=m.group(1).strip()))

    # Note
    m = re.search(r'note\s*:?\s*(.+)', content, re.IGNORECASE)
    if m:
        rows.append(make_row(field_id, 'note', text_val=m.group(1).strip()))

    return rows


def parse_population(field_id, content):
    """Population: total, male, female, growth_rate."""
    rows = []
    rank = extract_rank(content)
    content = normalize_content(content)
    date_est = extract_date_est(content)

    # Modern format (2025): "total: 338,016,259 (2025 est.) male: 167,543,554 female: 170,472,705"
    m = re.search(r'total\s*:\s*([\d,]+)', content)
    if m:
        rows.append(make_row(field_id, 'total',
                             numeric_val=parse_number(m.group(1)),
                             date_est=date_est, rank=rank))
        m2 = re.search(r'male\s*:\s*([\d,]+)', content)
        if m2:
            rows.append(make_row(field_id, 'male', numeric_val=parse_number(m2.group(1))))
        m2 = re.search(r'female\s*:\s*([\d,]+)', content)
        if m2:
            rows.append(make_row(field_id, 'female', numeric_val=parse_number(m2.group(1))))
        return rows

    # Legacy format: "123,642,461 (July 1990), growth rate 0.4% (1990)"
    m = re.search(r'([\d,]{5,})', content)
    if m:
        rows.append(make_row(field_id, 'total',
                             numeric_val=parse_number(m.group(1)),
                             date_est=date_est, rank=rank))
    m = re.search(r'growth rate\s*(-?[\d.]+)%', content)
    if m:
        rows.append(make_row(field_id, 'growth_rate',
                             numeric_val=float(m.group(1)), units='%'))
    return rows


def parse_life_exp(field_id, content):
    """Life expectancy at birth: total_population, male, female."""
    rows = []
    rank = extract_rank(content)
    content = normalize_content(content)
    date_est = extract_date_est(content)

    # Modern: "total population: 83.5 years (2024 est.) male: 81.3 years female: 85.7 years"
    m = re.search(r'total population:\s*([\d.]+)', content)
    if m:
        rows.append(make_row(field_id, 'total_population',
                             numeric_val=float(m.group(1)), units='years',
                             date_est=date_est, rank=rank))
    # Male/female
    m = re.search(r'male:\s*([\d.]+)\s*years', content)
    if m:
        rows.append(make_row(field_id, 'male',
                             numeric_val=float(m.group(1)), units='years'))
    m = re.search(r'female:\s*([\d.]+)\s*years', content)
    if m:
        rows.append(make_row(field_id, 'female',
                             numeric_val=float(m.group(1)), units='years'))

    # Legacy 1990: "76 years male, 82 years female (1990)"
    if not rows:
        m = re.search(r'([\d.]+)\s*years?\s*male\b.*?([\d.]+)\s*years?\s*female', content)
        if m:
            male_v = float(m.group(1))
            female_v = float(m.group(2))
            rows.append(make_row(field_id, 'male',
                                 numeric_val=male_v, units='years'))
            rows.append(make_row(field_id, 'female',
                                 numeric_val=female_v, units='years'))
            rows.append(make_row(field_id, 'total_population',
                                 numeric_val=round((male_v + female_v) / 2, 1),
                                 units='years', date_est=date_est, rank=rank))
        else:
            # Bare: "75.6 years"
            m = re.search(r'^([\d.]+)\s*years?', content.strip())
            if m:
                rows.append(make_row(field_id, 'total_population',
                                     numeric_val=float(m.group(1)), units='years',
                                     date_est=date_est, rank=rank))
    return rows


def parse_age_structure(field_id, content):
    """Age structure: brackets with percent, male count, female count."""
    rows = []
    content = normalize_content(content)
    date_est = extract_date_est(content)

    # Pattern: "0-14 years: 18.1% (male 31,618,532/female 30,254,223)"
    # Also: "0-14 years: 18.72% (male 2,457,418; female 2,309,706)"
    for m in re.finditer(
        r'(\d+[-–]\d+\s*years?|65\s*years?\s*and\s*over)\s*:\s*([\d.]+)%'
        r'(?:\s*\(?\s*(?:male\s*([\d,]+)\s*[/;]\s*female\s*([\d,]+)|'
        r'\(\d{4}\s*est\.\))\s*\(?(?:\s*\(male\s*([\d,]+)[/;]\s*female\s*([\d,]+)\))?)?',
        content
    ):
        bracket = m.group(1).strip().replace('–', '-')
        pct = float(m.group(2))
        rows.append(make_row(field_id, bracket + '_pct',
                             numeric_val=pct, units='%', date_est=date_est))
        male_v = m.group(3) or m.group(5)
        female_v = m.group(4) or m.group(6)
        if male_v:
            rows.append(make_row(field_id, bracket + '_male',
                                 numeric_val=parse_number(male_v)))
        if female_v:
            rows.append(make_row(field_id, bracket + '_female',
                                 numeric_val=parse_number(female_v)))

    # Simpler fallback: just grab percentage lines
    if not rows:
        for m in re.finditer(r'(\d+[-–]\d+\s*years?|65\s*years?\s*and\s*over)\s*:\s*([\d.]+)%', content):
            bracket = m.group(1).strip().replace('–', '-')
            rows.append(make_row(field_id, bracket + '_pct',
                                 numeric_val=float(m.group(2)), units='%', date_est=date_est))
    return rows


def parse_single_rate(field_id, content):
    """Birth rate, Death rate: single value per 1,000."""
    rows = []
    rank = extract_rank(content)
    content = normalize_content(content)
    date_est = extract_date_est(content)

    m = re.search(r'([\d.]+)\s*(?:births|deaths)\s*/\s*1,000', content)
    if m:
        rows.append(make_row(field_id, 'value',
                             numeric_val=float(m.group(1)), units='per 1,000',
                             date_est=date_est, rank=rank))
    elif content.strip():
        m = re.search(r'^([\d.]+)', content.strip())
        if m:
            rows.append(make_row(field_id, 'value',
                                 numeric_val=float(m.group(1)), units='per 1,000',
                                 date_est=date_est, rank=rank))
    return rows


def parse_infant_mortality(field_id, content):
    """Infant mortality rate: total, male, female deaths/1,000 live births."""
    rows = []
    rank = extract_rank(content)
    content = normalize_content(content)
    date_est = extract_date_est(content)

    m = re.search(r'total:\s*([\d.]+)\s*deaths', content)
    if m:
        rows.append(make_row(field_id, 'total',
                             numeric_val=float(m.group(1)),
                             units='deaths/1,000 live births',
                             date_est=date_est, rank=rank))
    m = re.search(r'male:\s*([\d.]+)\s*deaths', content)
    if m:
        rows.append(make_row(field_id, 'male',
                             numeric_val=float(m.group(1)),
                             units='deaths/1,000 live births'))
    m = re.search(r'female:\s*([\d.]+)\s*deaths', content)
    if m:
        rows.append(make_row(field_id, 'female',
                             numeric_val=float(m.group(1)),
                             units='deaths/1,000 live births'))

    # Legacy: just a number
    if not rows:
        m = re.search(r'([\d.]+)\s*(?:deaths|per)', content)
        if m:
            rows.append(make_row(field_id, 'total',
                                 numeric_val=float(m.group(1)),
                                 units='deaths/1,000 live births',
                                 date_est=date_est, rank=rank))
    return rows


def parse_single_value(field_id, content):
    """Total fertility rate and similar: just one number + units."""
    rows = []
    rank = extract_rank(content)
    content = normalize_content(content)
    date_est = extract_date_est(content)

    m = re.search(r'([\d.]+)\s*(children born/woman|%|years?|births)', content)
    if m:
        rows.append(make_row(field_id, 'value',
                             numeric_val=float(m.group(1)),
                             units=m.group(2).strip(),
                             date_est=date_est, rank=rank))
    else:
        m = re.search(r'^([\d.]+)', content.strip())
        if m:
            rows.append(make_row(field_id, 'value',
                                 numeric_val=float(m.group(1)),
                                 date_est=date_est, rank=rank))
    return rows


def parse_multi_year_dollar(field_id, content):
    """GDP variants, Exports, Imports: $X trillion/billion/million (YYYY est.)"""
    rows = []
    rank = extract_rank(content)
    content = normalize_content(content)

    # Match multiple "$N magnitude (YYYY est.)" entries
    for i, m in enumerate(re.finditer(
        r'\$([\d.,]+)\s*(trillion|billion|million)?\s*(?:\((\d{4})\s*est\.?\))?',
        content, re.IGNORECASE
    )):
        val_str = m.group(1).replace(',', '')
        try:
            val = float(val_str)
        except ValueError:
            continue

        mag = (m.group(2) or '').lower()
        if mag == 'trillion':
            val *= 1e12
        elif mag == 'billion':
            val *= 1e9
        elif mag == 'million':
            val *= 1e6

        year_est = m.group(3)
        sub = f'value_{year_est}' if year_est else ('value' if i == 0 else f'value_{i}')
        rows.append(make_row(field_id, sub,
                             numeric_val=val, units='USD',
                             date_est=f'{year_est} est.' if year_est else None,
                             rank=rank if i == 0 else None))

    # Note field
    m = re.search(r'note\s*:\s*(.+?)$', content, re.IGNORECASE)
    if m:
        rows.append(make_row(field_id, 'note', text_val=m.group(1).strip()))

    return rows


def parse_multi_year_pct_gdp(field_id, content):
    """Military expenditures: N% of GDP (YYYY est.) repeated."""
    rows = []
    rank = extract_rank(content)
    content = normalize_content(content)

    for i, m in enumerate(re.finditer(
        r'([\d.]+)%\s*(?:of\s*G[DN]P)?\s*(?:\((\d{4})\s*est\.?\))?',
        content
    )):
        pct = float(m.group(1))
        year_est = m.group(2)
        sub = f'pct_gdp_{year_est}' if year_est else ('pct_gdp' if i == 0 else f'pct_gdp_{i}')
        rows.append(make_row(field_id, sub,
                             numeric_val=pct, units='% of GDP',
                             date_est=f'{year_est} est.' if year_est else None,
                             rank=rank if i == 0 else None))
    return rows


def parse_multi_year_pct(field_id, content):
    """Unemployment rate, Inflation rate: N% (YYYY est.) repeated."""
    rows = []
    rank = extract_rank(content)
    content = normalize_content(content)

    for i, m in enumerate(re.finditer(
        r'(-?[\d.]+)%\s*(?:\((\d{4})\s*est\.?\))?',
        content
    )):
        pct = float(m.group(1))
        year_est = m.group(2)
        sub = f'value_{year_est}' if year_est else ('value' if i == 0 else f'value_{i}')
        rows.append(make_row(field_id, sub,
                             numeric_val=pct, units='%',
                             date_est=f'{year_est} est.' if year_est else None,
                             rank=rank if i == 0 else None))

    # Note
    m = re.search(r'note\s*:\s*(.+?)$', content, re.IGNORECASE)
    if m:
        rows.append(make_row(field_id, 'note', text_val=m.group(1).strip()))
    return rows


def parse_exports_imports(field_id, content):
    """Exports/Imports: dollar value, commodities list, partner percentages."""
    rows = []
    rank = extract_rank(content)
    content = normalize_content(content)

    # Dollar values (multi-year)
    for i, m in enumerate(re.finditer(
        r'\$([\d.,]+)\s*(trillion|billion|million)?\s*(?:\((\d{4})\s*est\.?\))?',
        content, re.IGNORECASE
    )):
        val_str = m.group(1).replace(',', '')
        try:
            val = float(val_str)
        except ValueError:
            continue
        mag = (m.group(2) or '').lower()
        if mag == 'trillion':
            val *= 1e12
        elif mag == 'billion':
            val *= 1e9
        elif mag == 'million':
            val *= 1e6
        year_est = m.group(3)
        sub = f'value_{year_est}' if year_est else ('value' if i == 0 else f'value_{i}')
        rows.append(make_row(field_id, sub,
                             numeric_val=val, units='USD',
                             date_est=f'{year_est} est.' if year_est else None,
                             rank=rank if i == 0 else None))

    # Commodities
    m = re.search(r'commodities\s*[-:]\s*(.+?)(?:\s*partners|\s*note|\s*$)', content, re.IGNORECASE)
    if m:
        rows.append(make_row(field_id, 'commodities', text_val=m.group(1).strip()))

    # Partners
    m = re.search(r'partners\s*[-:]\s*(.+?)(?:\s*note|\s*$)', content, re.IGNORECASE)
    if m:
        partner_text = m.group(1).strip()
        rows.append(make_row(field_id, 'partners', text_val=partner_text))
        # Also extract individual partner percentages
        for pm in re.finditer(r'([A-Z][\w\s,.\'-]+?)\s+([\d.]+)%', partner_text):
            name = pm.group(1).strip().rstrip(',')
            pct = float(pm.group(2))
            if pct > 0 and len(name) < 50:
                rows.append(make_row(field_id, f'partner_{name}',
                                     numeric_val=pct, units='%'))

    return rows


def parse_budget(field_id, content):
    """Budget: revenues and expenditures."""
    rows = []
    content = normalize_content(content)
    date_est = extract_date_est(content)

    for label in ['revenues', 'expenditures']:
        m = re.search(re.escape(label) + r'\s*:?\s*\$?([\d.,]+)\s*(trillion|billion|million)?',
                      content, re.IGNORECASE)
        if m:
            val_str = m.group(1).replace(',', '')
            try:
                val = float(val_str)
            except ValueError:
                continue
            mag = (m.group(2) or '').lower()
            if mag == 'trillion':
                val *= 1e12
            elif mag == 'billion':
                val *= 1e9
            elif mag == 'million':
                val *= 1e6
            rows.append(make_row(field_id, label,
                                 numeric_val=val, units='USD', date_est=date_est))
    return rows


def parse_land_use(field_id, content):
    """Land use: agricultural land, arable land, forest, other percentages."""
    rows = []
    content = normalize_content(content)
    date_est = extract_date_est(content)

    labels = ['agricultural land', 'arable land', 'permanent crops',
              'permanent pasture', 'forest', 'other']
    for label in labels:
        m = re.search(re.escape(label) + r'\s*:?\s*([\d.]+)%', content, re.IGNORECASE)
        if m:
            sub = label.replace(' ', '_')
            rows.append(make_row(field_id, sub,
                                 numeric_val=float(m.group(1)), units='%',
                                 date_est=date_est))
    return rows


def parse_electricity(field_id, content):
    """Electricity: capacity, consumption, exports, imports with various units."""
    rows = []
    content = normalize_content(content)

    patterns = [
        ('installed_generating_capacity', r'(?:installed\s+generating\s+)?capacity\s*:\s*([\d.,]+)\s*(billion|million|thousand)?\s*(kW)'),
        ('consumption', r'consumption\s*:\s*([\d.,]+)\s*(trillion|billion|million)?\s*(kWh)'),
        ('exports', r'exports\s*:\s*([\d.,]+)\s*(trillion|billion|million)?\s*(kWh)'),
        ('imports', r'imports\s*:\s*([\d.,]+)\s*(trillion|billion|million)?\s*(kWh)'),
        ('production', r'production\s*:\s*([\d.,]+)\s*(trillion|billion|million)?\s*(kWh)'),
    ]

    for sub_name, pattern in patterns:
        m = re.search(pattern, content, re.IGNORECASE)
        if m:
            val = float(m.group(1).replace(',', ''))
            mag = (m.group(2) or '').lower()
            unit = m.group(3)
            if mag == 'trillion':
                val *= 1e12
            elif mag == 'billion':
                val *= 1e9
            elif mag == 'million':
                val *= 1e6
            elif mag == 'thousand':
                val *= 1e3
            rows.append(make_row(field_id, sub_name,
                                 numeric_val=val, units=unit,
                                 date_est=extract_date_est(content)))

    # Legacy format: "191,000,000 kW capacity; 700,000 million kWh produced"
    if not rows:
        m = re.search(r'([\d,]+)\s*(?:million\s+)?kW\s+capacity', content)
        if m:
            val = parse_number(m.group(1))
            rows.append(make_row(field_id, 'installed_generating_capacity',
                                 numeric_val=val, units='kW'))
        m = re.search(r'([\d,]+)\s*(?:billion|million)?\s*kWh\s*(?:produced|production)', content)
        if m:
            val = parse_number(m.group(1))
            if 'billion' in content[:m.end()]:
                val *= 1e9
            elif 'million' in content[:m.end()]:
                val *= 1e6
            rows.append(make_row(field_id, 'production',
                                 numeric_val=val, units='kWh'))
    return rows


def parse_dependency_ratios(field_id, content):
    """Dependency ratios: total, youth, elderly, potential support ratio."""
    rows = []
    content = normalize_content(content)
    date_est = extract_date_est(content)

    for label, sub in [
        ('total dependency ratio', 'total'),
        ('youth dependency ratio', 'youth'),
        ('elderly dependency ratio', 'elderly'),
        ('potential support ratio', 'potential_support_ratio'),
    ]:
        m = re.search(re.escape(label) + r'\s*:?\s*([\d.]+)', content, re.IGNORECASE)
        if m:
            rows.append(make_row(field_id, sub,
                                 numeric_val=float(m.group(1)),
                                 date_est=date_est))
    return rows


def parse_urbanization(field_id, content):
    """Urbanization: urban population %, rate of urbanization."""
    rows = []
    content = normalize_content(content)
    date_est = extract_date_est(content)

    m = re.search(r'urban population\s*:\s*([\d.]+)%', content, re.IGNORECASE)
    if m:
        rows.append(make_row(field_id, 'urban_population',
                             numeric_val=float(m.group(1)), units='%',
                             date_est=date_est))
    m = re.search(r'rate of urbanization\s*:\s*([\d.]+)%', content, re.IGNORECASE)
    if m:
        rows.append(make_row(field_id, 'rate_of_urbanization',
                             numeric_val=float(m.group(1)), units='%'))
    return rows


def parse_elevation(field_id, content):
    """Elevation: highest point, lowest point, mean elevation."""
    rows = []
    content = normalize_content(content)

    m = re.search(r'mean elevation\s*:?\s*([\d,]+)\s*m', content, re.IGNORECASE)
    if m:
        rows.append(make_row(field_id, 'mean',
                             numeric_val=parse_number(m.group(1)), units='m'))
    m = re.search(r'highest point\s*:?\s*(.+?)\s+(-?[\d,]+)\s*m', content, re.IGNORECASE)
    if m:
        rows.append(make_row(field_id, 'highest',
                             numeric_val=parse_number(m.group(2)), units='m',
                             text_val=m.group(1).strip()))
    m = re.search(r'lowest point\s*:?\s*(.+?)\s+(-?[\d,]+)\s*m', content, re.IGNORECASE)
    if m:
        rows.append(make_row(field_id, 'lowest',
                             numeric_val=parse_number(m.group(2)), units='m',
                             text_val=m.group(1).strip()))
    return rows


def parse_gps(field_id, content):
    """Geographic coordinates: lat/lon degrees + minutes + hemisphere."""
    rows = []
    content = normalize_content(content)

    m = re.search(r'(\d+)\s+(\d+)\s*([NS])\s*,?\s*(\d+)\s+(\d+)\s*([EW])', content)
    if m:
        lat = int(m.group(1)) + int(m.group(2)) / 60
        if m.group(3) == 'S':
            lat = -lat
        lon = int(m.group(4)) + int(m.group(5)) / 60
        if m.group(6) == 'W':
            lon = -lon
        rows.append(make_row(field_id, 'latitude', numeric_val=round(lat, 4), units='degrees'))
        rows.append(make_row(field_id, 'longitude', numeric_val=round(lon, 4), units='degrees'))
    return rows


def parse_single_with_units(field_id, content):
    """Coastline, etc.: single number with units."""
    rows = []
    rank = extract_rank(content)
    content = normalize_content(content)
    date_est = extract_date_est(content)

    m = re.search(r'([\d,]+)\s*(sq\s*km|km2|km|nm|m|hectares)', content)
    if m:
        unit = m.group(2).replace('km2', 'sq km')
        rows.append(make_row(field_id, 'value',
                             numeric_val=parse_number(m.group(1)),
                             units=unit, date_est=date_est, rank=rank))
    return rows


def parse_median_age(field_id, content):
    """Median age: total, male, female in years."""
    rows = []
    rank = extract_rank(content)
    content = normalize_content(content)
    date_est = extract_date_est(content)

    m = re.search(r'total\s*:\s*([\d.]+)\s*years', content)
    if m:
        rows.append(make_row(field_id, 'total',
                             numeric_val=float(m.group(1)), units='years',
                             date_est=date_est, rank=rank))
    m = re.search(r'male\s*:\s*([\d.]+)\s*years', content)
    if m:
        rows.append(make_row(field_id, 'male',
                             numeric_val=float(m.group(1)), units='years'))
    m = re.search(r'female\s*:\s*([\d.]+)\s*years', content)
    if m:
        rows.append(make_row(field_id, 'female',
                             numeric_val=float(m.group(1)), units='years'))
    return rows


# ============================================================
# GENERIC FALLBACK PARSER
# ============================================================

def parse_generic(field_id, content):
    """Fallback: try key:value splitting, else store as single text/numeric."""
    rows = []
    rank = extract_rank(content)
    content = normalize_content(content)
    date_est = extract_date_est(content)

    if not content.strip():
        return rows

    # Try pipe-delimited splitting first (2015-2020 era)
    parts = [p.strip() for p in content.split(' | ')] if ' | ' in content else [content]

    for part in parts:
        # Try "label: value" pattern
        m = re.match(r'^([a-zA-Z][a-zA-Z\s\-/()]{1,60}):\s*(.+)', part)
        if m:
            label = m.group(1).strip().lower().replace(' ', '_')
            val_text = m.group(2).strip()

            # Try numeric extraction
            nm = re.search(r'^(-?[\d,]+\.?\d*)\s*(.*)', val_text)
            if nm:
                num = parse_number(nm.group(1))
                unit_text = nm.group(2).strip()
                # Extract units from remainder
                unit_m = re.match(r'^(%|sq\s*km|km|nm|m|years?|kW|kWh|bbl/day|liters|metric tonn?es?|USD|deaths|births)', unit_text)
                units = unit_m.group(1) if unit_m else None
                rows.append(make_row(field_id, label,
                                     numeric_val=num, units=units,
                                     date_est=extract_date_est(val_text)))
            else:
                # Check for dollar amount
                dm = re.search(r'\$([\d.,]+)\s*(trillion|billion|million)?', val_text, re.IGNORECASE)
                if dm:
                    val = float(dm.group(1).replace(',', ''))
                    mag = (dm.group(2) or '').lower()
                    if mag == 'trillion':
                        val *= 1e12
                    elif mag == 'billion':
                        val *= 1e9
                    elif mag == 'million':
                        val *= 1e6
                    rows.append(make_row(field_id, label,
                                         numeric_val=val, units='USD',
                                         date_est=extract_date_est(val_text)))
                # Check for percentage
                elif re.search(r'[\d.]+%', val_text):
                    pm = re.search(r'([\d.]+)%', val_text)
                    rows.append(make_row(field_id, label,
                                         numeric_val=float(pm.group(1)), units='%',
                                         date_est=extract_date_est(val_text)))
                else:
                    # Store as text
                    rows.append(make_row(field_id, label, text_val=val_text))
        elif not rows:
            # No label found — try bare numeric
            nm = re.search(r'^(-?[\d,]+\.?\d*)\s*(.*)', part.strip())
            if nm:
                num = parse_number(nm.group(1))
                if num is not None:
                    rows.append(make_row(field_id, 'value',
                                         numeric_val=num,
                                         date_est=date_est, rank=rank))

    # If nothing parsed, store whole content as text
    if not rows:
        rows.append(make_row(field_id, 'value', text_val=content.strip()[:4000],
                             date_est=date_est, rank=rank))

    return rows


# ============================================================
# PARSER DISPATCH TABLE
# ============================================================

FIELD_PARSERS = {
    'Area':                                     parse_area,
    'Population':                               parse_population,
    'Life expectancy at birth':                 parse_life_exp,
    'Age structure':                            parse_age_structure,
    'Birth rate':                               parse_single_rate,
    'Death rate':                               parse_single_rate,
    'Infant mortality rate':                    parse_infant_mortality,
    'Total fertility rate':                     parse_single_value,
    'Real GDP (purchasing power parity)':       parse_multi_year_dollar,
    'GDP (purchasing power parity)':            parse_multi_year_dollar,
    'Real GDP per capita':                      parse_multi_year_dollar,
    'GDP - per capita (PPP)':                   parse_multi_year_dollar,
    'GDP (official exchange rate)':             parse_multi_year_dollar,
    'Military expenditures':                    parse_multi_year_pct_gdp,
    'Exports':                                  parse_exports_imports,
    'Imports':                                  parse_exports_imports,
    'Budget':                                   parse_budget,
    'Land use':                                 parse_land_use,
    'Electricity':                              parse_electricity,
    'Unemployment rate':                        parse_multi_year_pct,
    'Inflation rate (consumer prices)':         parse_multi_year_pct,
    'Real GDP growth rate':                     parse_multi_year_pct,
    'GDP - real growth rate':                   parse_multi_year_pct,
    'Population growth rate':                   parse_multi_year_pct,
    'Dependency ratios':                        parse_dependency_ratios,
    'Urbanization':                             parse_urbanization,
    'Elevation':                                parse_elevation,
    'Geographic coordinates':                   parse_gps,
    'Coastline':                                parse_single_with_units,
    'Median age':                               parse_median_age,
    'Current account balance':                  parse_multi_year_dollar,
    'Reserves of foreign exchange and gold':    parse_multi_year_dollar,
    'Public debt':                              parse_multi_year_pct,
    'Industrial production growth rate':        parse_multi_year_pct,
}


# ============================================================
# MAIN PROCESSING
# ============================================================

def main():
    print("=" * 70)
    print("Structured Field Parsing")
    print(f"  Source: {SOURCE_DB} (read-only)")
    print(f"  Target: {TARGET_DB}")
    print("=" * 70)

    conn_read = pyodbc.connect(CONN_STR_READ)
    conn_write = pyodbc.connect(CONN_STR_WRITE, autocommit=False)
    cursor_write = conn_write.cursor()

    # Clear existing data
    cursor_write.execute("TRUNCATE TABLE FieldValues")
    conn_write.commit()
    print("Cleared existing FieldValues data.")

    # Build canonical name lookup from FieldNameMappings
    canonical_map = {}
    rows = conn_read.execute(
        "SELECT OriginalName, CanonicalName FROM FieldNameMappings WHERE IsNoise = 0"
    ).fetchall()
    for orig, canon in rows:
        canonical_map[orig] = canon
    print(f"Loaded {len(canonical_map)} field name mappings.")

    # Get years
    years = [r[0] for r in conn_read.execute(
        "SELECT DISTINCT Year FROM Countries ORDER BY Year"
    ).fetchall()]
    print(f"Processing {len(years)} years: {years[0]}-{years[-1]}")
    print()

    total_fields = 0
    total_values = 0
    insert_sql = """
        INSERT INTO FieldValues (FieldID, SubField, NumericVal, Units, TextVal, DateEst, Rank)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """
    batch = []
    t0 = time.time()

    for year in years:
        year_fields = 0
        year_values = 0

        # Read all fields for this year
        field_rows = conn_read.execute("""
            SELECT cf.FieldID, cf.FieldName, cf.Content
            FROM CountryFields cf
            JOIN Countries c ON cf.CountryID = c.CountryID
            WHERE c.Year = ?
        """, year).fetchall()

        for field_id, field_name, content in field_rows:
            if not content:
                continue

            year_fields += 1

            # Resolve canonical name
            canonical = canonical_map.get(field_name, field_name)

            # Get parser
            parser = FIELD_PARSERS.get(canonical, parse_generic)

            # Parse
            try:
                value_rows = parser(field_id, content)
            except Exception as e:
                # Fallback on error
                value_rows = [make_row(field_id, 'value', text_val=str(content)[:4000])]

            for row in value_rows:
                batch.append(row)
                year_values += 1

                if len(batch) >= BATCH_SIZE:
                    cursor_write.executemany(insert_sql, batch)
                    conn_write.commit()
                    batch = []

        total_fields += year_fields
        total_values += year_values
        ratio = year_values / year_fields if year_fields > 0 else 0
        elapsed = time.time() - t0
        print(f"  [{year}] {year_fields:>7,} fields -> {year_values:>9,} values "
              f"({ratio:.1f}x)  [{elapsed:.0f}s elapsed]")

    # Flush remaining batch
    if batch:
        cursor_write.executemany(insert_sql, batch)
        conn_write.commit()

    elapsed = time.time() - t0
    ratio = total_values / total_fields if total_fields > 0 else 0
    print()
    print("=" * 70)
    print(f"COMPLETE: {total_fields:,} fields -> {total_values:,} values ({ratio:.1f}x)")
    print(f"Time: {elapsed:.0f}s")
    print("=" * 70)

    conn_read.close()
    conn_write.close()


if __name__ == "__main__":
    main()
