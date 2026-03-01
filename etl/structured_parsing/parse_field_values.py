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
MAX_FRAG_LEN = 500

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
             text_val=None, date_est=None, rank=None, source_frag=None):
    """Create a FieldValues row tuple."""
    if source_frag and len(source_frag) > MAX_FRAG_LEN:
        source_frag = source_frag[:MAX_FRAG_LEN]
    return (field_id, sub_field, numeric_val, units, text_val, date_est, rank, source_frag)


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
                                 rank=rank if sub == 'total' else None,
                                 source_frag=m.group(0)))
    # Comparative area (text)
    m = re.search(r'comparative\s*(?:area)?\s*:?\s*(.+?)(?:\s*(?:note|$))', content, re.IGNORECASE)
    if m:
        rows.append(make_row(field_id, 'comparative', text_val=m.group(1).strip(),
                             source_frag=m.group(0)))

    # Note
    m = re.search(r'note\s*:?\s*(.+)', content, re.IGNORECASE)
    if m:
        rows.append(make_row(field_id, 'note', text_val=m.group(1).strip(),
                             source_frag=m.group(0)))

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
                             date_est=date_est, rank=rank,
                             source_frag=m.group(0)))
        m2 = re.search(r'male\s*:\s*([\d,]+)', content)
        if m2:
            rows.append(make_row(field_id, 'male', numeric_val=parse_number(m2.group(1)),
                                 source_frag=m2.group(0)))
        m2 = re.search(r'female\s*:\s*([\d,]+)', content)
        if m2:
            rows.append(make_row(field_id, 'female', numeric_val=parse_number(m2.group(1)),
                                 source_frag=m2.group(0)))
        return rows

    # Legacy format: "123,642,461 (July 1990), growth rate 0.4% (1990)"
    m = re.search(r'([\d,]{5,})', content)
    if m:
        rows.append(make_row(field_id, 'total',
                             numeric_val=parse_number(m.group(1)),
                             date_est=date_est, rank=rank,
                             source_frag=m.group(0)))
    m = re.search(r'growth rate\s*(-?[\d.]+)%', content)
    if m:
        rows.append(make_row(field_id, 'growth_rate',
                             numeric_val=float(m.group(1)), units='%',
                             source_frag=m.group(0)))
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
                             date_est=date_est, rank=rank,
                             source_frag=m.group(0)))
    # Male/female
    m = re.search(r'male:\s*([\d.]+)\s*years', content)
    if m:
        rows.append(make_row(field_id, 'male',
                             numeric_val=float(m.group(1)), units='years',
                             source_frag=m.group(0)))
    m = re.search(r'female:\s*([\d.]+)\s*years', content)
    if m:
        rows.append(make_row(field_id, 'female',
                             numeric_val=float(m.group(1)), units='years',
                             source_frag=m.group(0)))

    # Legacy 1990: "76 years male, 82 years female (1990)"
    if not rows:
        m = re.search(r'([\d.]+)\s*years?\s*male\b.*?([\d.]+)\s*years?\s*female', content)
        if m:
            male_v = float(m.group(1))
            female_v = float(m.group(2))
            frag = m.group(0)
            rows.append(make_row(field_id, 'male',
                                 numeric_val=male_v, units='years',
                                 source_frag=frag))
            rows.append(make_row(field_id, 'female',
                                 numeric_val=female_v, units='years',
                                 source_frag=frag))
            rows.append(make_row(field_id, 'total_population',
                                 numeric_val=round((male_v + female_v) / 2, 1),
                                 units='years', date_est=date_est, rank=rank,
                                 source_frag=frag))
        else:
            # Bare: "75.6 years"
            m = re.search(r'^([\d.]+)\s*years?', content.strip())
            if m:
                rows.append(make_row(field_id, 'total_population',
                                     numeric_val=float(m.group(1)), units='years',
                                     date_est=date_est, rank=rank,
                                     source_frag=m.group(0)))
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
                             numeric_val=pct, units='%', date_est=date_est,
                             source_frag=m.group(0)))
        male_v = m.group(3) or m.group(5)
        female_v = m.group(4) or m.group(6)
        if male_v:
            rows.append(make_row(field_id, bracket + '_male',
                                 numeric_val=parse_number(male_v),
                                 source_frag=m.group(0)))
        if female_v:
            rows.append(make_row(field_id, bracket + '_female',
                                 numeric_val=parse_number(female_v),
                                 source_frag=m.group(0)))

    # Simpler fallback: just grab percentage lines
    if not rows:
        for m in re.finditer(r'(\d+[-–]\d+\s*years?|65\s*years?\s*and\s*over)\s*:\s*([\d.]+)%', content):
            bracket = m.group(1).strip().replace('–', '-')
            rows.append(make_row(field_id, bracket + '_pct',
                                 numeric_val=float(m.group(2)), units='%', date_est=date_est,
                                 source_frag=m.group(0)))
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
                             date_est=date_est, rank=rank,
                             source_frag=m.group(0)))
    elif content.strip():
        m = re.search(r'^([\d.]+)', content.strip())
        if m:
            rows.append(make_row(field_id, 'value',
                                 numeric_val=float(m.group(1)), units='per 1,000',
                                 date_est=date_est, rank=rank,
                                 source_frag=m.group(0)))
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
                             date_est=date_est, rank=rank,
                             source_frag=m.group(0)))
    m = re.search(r'male:\s*([\d.]+)\s*deaths', content)
    if m:
        rows.append(make_row(field_id, 'male',
                             numeric_val=float(m.group(1)),
                             units='deaths/1,000 live births',
                             source_frag=m.group(0)))
    m = re.search(r'female:\s*([\d.]+)\s*deaths', content)
    if m:
        rows.append(make_row(field_id, 'female',
                             numeric_val=float(m.group(1)),
                             units='deaths/1,000 live births',
                             source_frag=m.group(0)))

    # Legacy: just a number
    if not rows:
        m = re.search(r'([\d.]+)\s*(?:deaths|per)', content)
        if m:
            rows.append(make_row(field_id, 'total',
                                 numeric_val=float(m.group(1)),
                                 units='deaths/1,000 live births',
                                 date_est=date_est, rank=rank,
                                 source_frag=m.group(0)))
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
                             date_est=date_est, rank=rank,
                             source_frag=m.group(0)))
    else:
        m = re.search(r'^([\d.]+)', content.strip())
        if m:
            rows.append(make_row(field_id, 'value',
                                 numeric_val=float(m.group(1)),
                                 date_est=date_est, rank=rank,
                                 source_frag=m.group(0)))
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
                             rank=rank if i == 0 else None,
                             source_frag=m.group(0)))

    # Note field
    m = re.search(r'note\s*:\s*(.+?)$', content, re.IGNORECASE)
    if m:
        rows.append(make_row(field_id, 'note', text_val=m.group(1).strip(),
                             source_frag=m.group(0)))

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
                             rank=rank if i == 0 else None,
                             source_frag=m.group(0)))
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
                             rank=rank if i == 0 else None,
                             source_frag=m.group(0)))

    # Note
    m = re.search(r'note\s*:\s*(.+?)$', content, re.IGNORECASE)
    if m:
        rows.append(make_row(field_id, 'note', text_val=m.group(1).strip(),
                             source_frag=m.group(0)))
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
                             rank=rank if i == 0 else None,
                             source_frag=m.group(0)))

    # Commodities
    m = re.search(r'commodities\s*[-:]\s*(.+?)(?:\s*partners|\s*note|\s*$)', content, re.IGNORECASE)
    if m:
        rows.append(make_row(field_id, 'commodities', text_val=m.group(1).strip(),
                             source_frag=m.group(0)))

    # Partners
    m = re.search(r'partners\s*[-:]\s*(.+?)(?:\s*note|\s*$)', content, re.IGNORECASE)
    if m:
        partner_text = m.group(1).strip()
        rows.append(make_row(field_id, 'partners', text_val=partner_text,
                             source_frag=m.group(0)))
        # Also extract individual partner percentages
        for pm in re.finditer(r'([A-Z][\w\s,.\'-]+?)\s+([\d.]+)%', partner_text):
            name = pm.group(1).strip().rstrip(',')
            pct = float(pm.group(2))
            if pct > 0 and len(name) < 50:
                rows.append(make_row(field_id, f'partner_{name}',
                                     numeric_val=pct, units='%',
                                     source_frag=pm.group(0)))

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
                                 numeric_val=val, units='USD', date_est=date_est,
                                 source_frag=m.group(0)))
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
                                 date_est=date_est,
                                 source_frag=m.group(0)))
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
                                 date_est=extract_date_est(content),
                                 source_frag=m.group(0)))

    # Legacy format: "191,000,000 kW capacity; 700,000 million kWh produced"
    if not rows:
        m = re.search(r'([\d,]+)\s*(?:million\s+)?kW\s+capacity', content)
        if m:
            val = parse_number(m.group(1))
            rows.append(make_row(field_id, 'installed_generating_capacity',
                                 numeric_val=val, units='kW',
                                 source_frag=m.group(0)))
        m = re.search(r'([\d,]+)\s*(?:billion|million)?\s*kWh\s*(?:produced|production)', content)
        if m:
            val = parse_number(m.group(1))
            if 'billion' in content[:m.end()]:
                val *= 1e9
            elif 'million' in content[:m.end()]:
                val *= 1e6
            rows.append(make_row(field_id, 'production',
                                 numeric_val=val, units='kWh',
                                 source_frag=m.group(0)))
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
                                 date_est=date_est,
                                 source_frag=m.group(0)))
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
                             date_est=date_est,
                             source_frag=m.group(0)))
    m = re.search(r'rate of urbanization\s*:\s*([\d.]+)%', content, re.IGNORECASE)
    if m:
        rows.append(make_row(field_id, 'rate_of_urbanization',
                             numeric_val=float(m.group(1)), units='%',
                             source_frag=m.group(0)))
    return rows


def parse_elevation(field_id, content):
    """Elevation: highest point, lowest point, mean elevation."""
    rows = []
    content = normalize_content(content)

    m = re.search(r'mean elevation\s*:?\s*([\d,]+)\s*m', content, re.IGNORECASE)
    if m:
        rows.append(make_row(field_id, 'mean',
                             numeric_val=parse_number(m.group(1)), units='m',
                             source_frag=m.group(0)))
    m = re.search(r'highest point\s*:?\s*(.+?)\s+(-?[\d,]+)\s*m', content, re.IGNORECASE)
    if m:
        rows.append(make_row(field_id, 'highest',
                             numeric_val=parse_number(m.group(2)), units='m',
                             text_val=m.group(1).strip(),
                             source_frag=m.group(0)))
    m = re.search(r'lowest point\s*:?\s*(.+?)\s+(-?[\d,]+)\s*m', content, re.IGNORECASE)
    if m:
        rows.append(make_row(field_id, 'lowest',
                             numeric_val=parse_number(m.group(2)), units='m',
                             text_val=m.group(1).strip(),
                             source_frag=m.group(0)))
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
        frag = m.group(0)
        rows.append(make_row(field_id, 'latitude', numeric_val=round(lat, 4), units='degrees',
                             source_frag=frag))
        rows.append(make_row(field_id, 'longitude', numeric_val=round(lon, 4), units='degrees',
                             source_frag=frag))
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
                             units=unit, date_est=date_est, rank=rank,
                             source_frag=m.group(0)))
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
                             date_est=date_est, rank=rank,
                             source_frag=m.group(0)))
    m = re.search(r'male\s*:\s*([\d.]+)\s*years', content)
    if m:
        rows.append(make_row(field_id, 'male',
                             numeric_val=float(m.group(1)), units='years',
                             source_frag=m.group(0)))
    m = re.search(r'female\s*:\s*([\d.]+)\s*years', content)
    if m:
        rows.append(make_row(field_id, 'female',
                             numeric_val=float(m.group(1)), units='years',
                             source_frag=m.group(0)))
    return rows


# ============================================================
# NEW DEDICATED PARSERS (v3.2)
# ============================================================

def parse_sex_ratio(field_id, content):
    """Sex ratio: male(s)/female for each age bracket + total."""
    rows = []
    rank = extract_rank(content)
    content = normalize_content(content)
    date_est = extract_date_est(content)

    # Brackets: "at birth: 1.05 male(s)/female"
    #           "0-14 years: 1.06 male(s)/female"
    #           "15-64 years: 1.00 male(s)/female"
    #           "65 years and over: 0.79 male(s)/female"
    #           "total population: 0.97 male(s)/female"
    bracket_pattern = re.compile(
        r'(at birth|total population|\d+[-–]\d+\s*years?|65\s*years?\s*and\s*over)\s*:\s*'
        r'([\d.]+)\s*male\(s\)/female',
        re.IGNORECASE
    )
    for m in bracket_pattern.finditer(content):
        label = m.group(1).strip().lower()
        label = label.replace('–', '-').replace(' ', '_').replace('and_over', 'and_over')
        val = float(m.group(2))
        rows.append(make_row(field_id, label,
                             numeric_val=val, units='male(s)/female',
                             date_est=date_est if label == 'total_population' else None,
                             rank=rank if label == 'total_population' else None,
                             source_frag=m.group(0)))

    # Legacy fallback: bare ratio
    if not rows:
        m = re.search(r'([\d.]+)\s*male', content)
        if m:
            rows.append(make_row(field_id, 'total_population',
                                 numeric_val=float(m.group(1)), units='male(s)/female',
                                 date_est=date_est, rank=rank,
                                 source_frag=m.group(0)))
    return rows


def parse_literacy(field_id, content):
    """Literacy: definition (text), total population %, male %, female %."""
    rows = []
    content = normalize_content(content)
    date_est = extract_date_est(content)

    # Definition text
    m = re.search(r'definition\s*:\s*(.+?)(?=\s*total population\s*:|\s*$)', content, re.IGNORECASE)
    if m:
        rows.append(make_row(field_id, 'definition', text_val=m.group(1).strip(),
                             source_frag=m.group(0)))

    # total population: NN.N%
    m = re.search(r'total population\s*:\s*([\d.]+)%', content, re.IGNORECASE)
    if m:
        rows.append(make_row(field_id, 'total_population',
                             numeric_val=float(m.group(1)), units='%',
                             date_est=date_est,
                             source_frag=m.group(0)))

    # male: NN.N%
    m = re.search(r'male\s*:\s*([\d.]+)%', content, re.IGNORECASE)
    if m:
        rows.append(make_row(field_id, 'male',
                             numeric_val=float(m.group(1)), units='%',
                             source_frag=m.group(0)))

    # female: NN.N%
    m = re.search(r'female\s*:\s*([\d.]+)%', content, re.IGNORECASE)
    if m:
        rows.append(make_row(field_id, 'female',
                             numeric_val=float(m.group(1)), units='%',
                             source_frag=m.group(0)))

    # Legacy: single percentage "99% (2003 est.)"
    if not rows:
        m = re.search(r'([\d.]+)%', content)
        if m:
            rows.append(make_row(field_id, 'total_population',
                                 numeric_val=float(m.group(1)), units='%',
                                 date_est=date_est,
                                 source_frag=m.group(0)))
    return rows


def parse_maritime_claims(field_id, content):
    """Maritime claims: territorial sea, EEZ, contiguous zone, continental shelf."""
    rows = []
    content = normalize_content(content)

    claims = [
        ('territorial sea', 'territorial_sea'),
        ('exclusive economic zone', 'exclusive_economic_zone'),
        ('contiguous zone', 'contiguous_zone'),
        ('continental shelf', 'continental_shelf'),
        ('exclusive fishing zone', 'exclusive_fishing_zone'),
    ]
    for label, sub in claims:
        m = re.search(re.escape(label) + r'\s*:\s*([\d.]+)\s*(nm|km)', content, re.IGNORECASE)
        if m:
            rows.append(make_row(field_id, sub,
                                 numeric_val=float(m.group(1)),
                                 units=m.group(2),
                                 source_frag=m.group(0)))
        else:
            # Continental shelf can have text like "200-m depth" or "to depth of exploitation"
            m = re.search(re.escape(label) + r'\s*:\s*(.+?)(?=\s+\w+\s*(?:sea|zone|shelf|fishing)\s*:|$)',
                          content, re.IGNORECASE)
            if m and sub == 'continental_shelf':
                text = m.group(1).strip()
                # Try to extract numeric from "200 m depth"
                nm = re.search(r'(\d+)[\s-]*m(?:\s+depth)?', text)
                if nm:
                    rows.append(make_row(field_id, sub,
                                         numeric_val=float(nm.group(1)), units='m depth',
                                         text_val=text,
                                         source_frag=m.group(0)))
                else:
                    rows.append(make_row(field_id, sub, text_val=text,
                                         source_frag=m.group(0)))
    return rows


def parse_natural_gas(field_id, content):
    """Natural gas: production, consumption, exports, imports, proven reserves."""
    rows = []
    content = normalize_content(content)

    labels = [
        ('production', 'production'),
        ('consumption', 'consumption'),
        ('exports', 'exports'),
        ('imports', 'imports'),
        ('proven reserves', 'proven_reserves'),
    ]
    for label, sub in labels:
        m = re.search(
            re.escape(label) + r'\s*:\s*([\d.,]+)\s*(trillion|billion|million)?\s*cubic\s*meters',
            content, re.IGNORECASE
        )
        if m:
            val = float(m.group(1).replace(',', ''))
            mag = (m.group(2) or '').lower()
            if mag == 'trillion':
                val *= 1e12
            elif mag == 'billion':
                val *= 1e9
            elif mag == 'million':
                val *= 1e6
            rows.append(make_row(field_id, sub,
                                 numeric_val=val, units='cu m',
                                 date_est=extract_date_est(content),
                                 source_frag=m.group(0)))

    # Legacy: bare numbers with "cu m"
    if not rows:
        m = re.search(r'([\d,]+)\s*(?:million|billion)?\s*cu\s*m', content)
        if m:
            val = parse_number(m.group(1))
            if 'billion' in content[:m.end()]:
                val *= 1e9
            elif 'million' in content[:m.end()]:
                val *= 1e6
            rows.append(make_row(field_id, 'production',
                                 numeric_val=val, units='cu m',
                                 date_est=extract_date_est(content),
                                 source_frag=m.group(0)))
    return rows


def parse_internet_users(field_id, content):
    """Internet users: total count and percent of population."""
    rows = []
    content = normalize_content(content)
    date_est = extract_date_est(content)

    # Total: "total: 312.8 million" or "total: 301665983"
    m = re.search(r'total\s*:\s*([\d.,]+)\s*(million|billion)?', content, re.IGNORECASE)
    if m:
        val = float(m.group(1).replace(',', ''))
        mag = (m.group(2) or '').lower()
        if mag == 'million':
            val *= 1e6
        elif mag == 'billion':
            val *= 1e9
        rows.append(make_row(field_id, 'total',
                             numeric_val=val,
                             date_est=extract_date_est(m.group(0)) or date_est,
                             source_frag=m.group(0)))

    # Percent: "percent of population: 93%"
    m = re.search(r'percent of population\s*:\s*([\d.]+)%?', content, re.IGNORECASE)
    if m:
        rows.append(make_row(field_id, 'percent_of_population',
                             numeric_val=float(m.group(1)), units='%',
                             date_est=extract_date_est(m.group(0)) or date_est,
                             source_frag=m.group(0)))

    # Legacy: bare number
    if not rows:
        m = re.search(r'([\d,]{5,})', content)
        if m:
            rows.append(make_row(field_id, 'total',
                                 numeric_val=parse_number(m.group(1)),
                                 date_est=date_est,
                                 source_frag=m.group(0)))
    return rows


def parse_telephones(field_id, content):
    """Telephones (fixed/mobile): total subscriptions and per 100 inhabitants."""
    rows = []
    content = normalize_content(content)
    date_est = extract_date_est(content)

    # Total subscriptions: "total subscriptions: 87.987 million" or "total subscriptions: 107667642"
    m = re.search(r'total\s*(?:subscriptions)?\s*:\s*([\d.,]+)\s*(million|billion)?',
                  content, re.IGNORECASE)
    if m:
        val = float(m.group(1).replace(',', ''))
        mag = (m.group(2) or '').lower()
        if mag == 'million':
            val *= 1e6
        elif mag == 'billion':
            val *= 1e9
        rows.append(make_row(field_id, 'total_subscriptions',
                             numeric_val=val,
                             date_est=extract_date_est(m.group(0)) or date_est,
                             source_frag=m.group(0)))

    # Subscriptions per 100 inhabitants
    m = re.search(r'subscriptions per 100 inhabitants\s*:\s*([\d.]+)',
                  content, re.IGNORECASE)
    if m:
        rows.append(make_row(field_id, 'subscriptions_per_100',
                             numeric_val=float(m.group(1)),
                             date_est=extract_date_est(m.group(0)) or date_est,
                             source_frag=m.group(0)))

    # Legacy: bare number
    if not rows:
        m = re.search(r'([\d,]{5,})', content)
        if m:
            rows.append(make_row(field_id, 'total_subscriptions',
                                 numeric_val=parse_number(m.group(1)),
                                 date_est=date_est,
                                 source_frag=m.group(0)))
    return rows


# ============================================================
# NEW DEDICATED PARSERS (v3.2)
# ============================================================

def parse_gdp_composition(field_id, content):
    """GDP composition by sector of origin: agriculture, industry, services %."""
    rows = []
    rank = extract_rank(content)
    content = normalize_content(content)
    date_est = extract_date_est(content)

    for label in ['agriculture', 'industry', 'services']:
        m = re.search(re.escape(label) + r'\s*:\s*([\d.]+)%', content, re.IGNORECASE)
        if m:
            rows.append(make_row(field_id, label,
                                 numeric_val=float(m.group(1)), units='%',
                                 date_est=extract_date_est(m.group(0)) or date_est,
                                 rank=rank if label == 'agriculture' else None,
                                 source_frag=m.group(0)))

    # Note
    m = re.search(r'note\s*:\s*(.+?)$', content, re.IGNORECASE)
    if m:
        rows.append(make_row(field_id, 'note', text_val=m.group(1).strip(),
                             source_frag=m.group(0)))
    return rows


def parse_household_income(field_id, content):
    """Household income or consumption: lowest 10%, highest 10%."""
    rows = []
    content = normalize_content(content)
    date_est = extract_date_est(content)

    m = re.search(r'lowest 10%\s*:\s*([\d.]+)%', content, re.IGNORECASE)
    if m:
        rows.append(make_row(field_id, 'lowest_10pct',
                             numeric_val=float(m.group(1)), units='%',
                             date_est=extract_date_est(m.group(0)) or date_est,
                             source_frag=m.group(0)))

    m = re.search(r'highest 10%\s*:\s*([\d.]+)%', content, re.IGNORECASE)
    if m:
        rows.append(make_row(field_id, 'highest_10pct',
                             numeric_val=float(m.group(1)), units='%',
                             date_est=extract_date_est(m.group(0)) or date_est,
                             source_frag=m.group(0)))

    # Note
    m = re.search(r'note\s*:\s*(.+?)$', content, re.IGNORECASE)
    if m:
        rows.append(make_row(field_id, 'note', text_val=m.group(1).strip(),
                             source_frag=m.group(0)))
    return rows


def parse_school_life_expectancy(field_id, content):
    """School life expectancy: total, male, female in years."""
    rows = []
    content = normalize_content(content)
    date_est = extract_date_est(content)

    m = re.search(r'total\s*:\s*(\d+)\s*years?', content)
    if m:
        rows.append(make_row(field_id, 'total',
                             numeric_val=float(m.group(1)), units='years',
                             date_est=extract_date_est(m.group(0)) or date_est,
                             source_frag=m.group(0)))

    m = re.search(r'male\s*:\s*(\d+)\s*years?', content)
    if m:
        rows.append(make_row(field_id, 'male',
                             numeric_val=float(m.group(1)), units='years',
                             date_est=extract_date_est(m.group(0)) or date_est,
                             source_frag=m.group(0)))

    m = re.search(r'female\s*:\s*(\d+)\s*years?', content)
    if m:
        rows.append(make_row(field_id, 'female',
                             numeric_val=float(m.group(1)), units='years',
                             date_est=extract_date_est(m.group(0)) or date_est,
                             source_frag=m.group(0)))
    return rows


def parse_youth_unemployment(field_id, content):
    """Youth unemployment: total, male, female percentages."""
    rows = []
    rank = extract_rank(content)
    content = normalize_content(content)
    date_est = extract_date_est(content)

    m = re.search(r'total\s*:\s*([\d.]+)%', content)
    if m:
        rows.append(make_row(field_id, 'total',
                             numeric_val=float(m.group(1)), units='%',
                             date_est=extract_date_est(m.group(0)) or date_est,
                             rank=rank,
                             source_frag=m.group(0)))

    m = re.search(r'male\s*:\s*([\d.]+)%', content)
    if m:
        rows.append(make_row(field_id, 'male',
                             numeric_val=float(m.group(1)), units='%',
                             date_est=extract_date_est(m.group(0)) or date_est,
                             source_frag=m.group(0)))

    m = re.search(r'female\s*:\s*([\d.]+)%', content)
    if m:
        rows.append(make_row(field_id, 'female',
                             numeric_val=float(m.group(1)), units='%',
                             date_est=extract_date_est(m.group(0)) or date_est,
                             source_frag=m.group(0)))

    # Note
    m = re.search(r'note\s*:\s*(.+?)$', content, re.IGNORECASE)
    if m:
        rows.append(make_row(field_id, 'note', text_val=m.group(1).strip(),
                             source_frag=m.group(0)))
    return rows


def parse_co2_emissions(field_id, content):
    """Carbon dioxide emissions: total + from coal, petroleum, natural gas."""
    rows = []
    rank = extract_rank(content)
    content = normalize_content(content)
    date_est = extract_date_est(content)

    co2_val_re = r'([\d.,]+)\s*(trillion|billion|million)?\s*(?:metric\s+)?(?:tonn?es?\s*(?:of\s*CO2)?|Mt)'

    # Total comes first (no label) — grab everything before the first "from" sub-label
    total_text = re.split(r'\bfrom\s+(?:coal|petroleum|consumed)', content, maxsplit=1)[0]
    total_m = re.search(co2_val_re, total_text, re.IGNORECASE)
    if total_m:
        val = float(total_m.group(1).replace(',', ''))
        mag = (total_m.group(2) or '').lower()
        if mag == 'trillion':
            val *= 1e12
        elif mag == 'billion':
            val *= 1e9
        elif mag == 'million':
            val *= 1e6
        rows.append(make_row(field_id, 'total',
                             numeric_val=val, units='metric tonnes CO2',
                             date_est=extract_date_est(total_text) or date_est,
                             rank=rank,
                             source_frag=total_m.group(0)))

    # Sub-categories
    sub_labels = [
        (r'from\s+coal\s+and\s+metallurgical\s+coke\s*:\s*' + co2_val_re, 'from_coal'),
        (r'from\s+petroleum\s+and\s+other\s+liquids\s*:\s*' + co2_val_re, 'from_petroleum'),
        (r'from\s+consumed\s+natural\s+gas\s*:\s*' + co2_val_re, 'from_natural_gas'),
    ]
    for pattern, sub in sub_labels:
        m = re.search(pattern, content, re.IGNORECASE)
        if m:
            val = float(m.group(1).replace(',', ''))
            mag = (m.group(2) or '').lower()
            if mag == 'trillion':
                val *= 1e12
            elif mag == 'billion':
                val *= 1e9
            elif mag == 'million':
                val *= 1e6
            rows.append(make_row(field_id, sub,
                                 numeric_val=val, units='metric tonnes CO2',
                                 date_est=extract_date_est(m.group(0)) or date_est,
                                 source_frag=m.group(0)))
    return rows


def parse_water_withdrawal(field_id, content):
    """Total water withdrawal: municipal, industrial, agricultural."""
    rows = []
    content = normalize_content(content)
    date_est = extract_date_est(content)

    # Modern format (2012+): "municipal: 58.39 billion cubic meters ..."
    for label, sub in [('municipal', 'municipal'), ('industrial', 'industrial'),
                       ('agricultural', 'agricultural')]:
        m = re.search(
            re.escape(label) + r'\s*:\s*([\d.,]+)\s*(trillion|billion|million)?\s*cubic\s*meters',
            content, re.IGNORECASE
        )
        if m:
            val = float(m.group(1).replace(',', ''))
            mag = (m.group(2) or '').lower()
            if mag == 'trillion':
                val *= 1e12
            elif mag == 'billion':
                val *= 1e9
            elif mag == 'million':
                val *= 1e6
            rows.append(make_row(field_id, sub,
                                 numeric_val=val, units='cu m',
                                 date_est=extract_date_est(m.group(0)) or date_est,
                                 source_frag=m.group(0)))

    # Old format (2008-2011): "total: 59.3 cu km/yr (20%/18%/62%)"
    if not rows:
        m = re.search(r'total\s*:\s*([\d.,]+)\s*cu\s*km/yr', content, re.IGNORECASE)
        if m:
            val = float(m.group(1).replace(',', '')) * 1e9  # cu km -> cu m
            rows.append(make_row(field_id, 'total',
                                 numeric_val=val, units='cu m',
                                 date_est=date_est,
                                 source_frag=m.group(0)))

        # Percentage breakdown: (20%/18%/62%) = domestic/industrial/agricultural
        pm = re.search(r'\((\d+)%/(\d+)%/(\d+)%\)', content)
        if pm:
            rows.append(make_row(field_id, 'domestic_pct',
                                 numeric_val=float(pm.group(1)), units='%',
                                 source_frag=pm.group(0)))
            rows.append(make_row(field_id, 'industrial_pct',
                                 numeric_val=float(pm.group(2)), units='%',
                                 source_frag=pm.group(0)))
            rows.append(make_row(field_id, 'agricultural_pct',
                                 numeric_val=float(pm.group(3)), units='%',
                                 source_frag=pm.group(0)))

        # Per capita
        m = re.search(r'per capita\s*:\s*([\d.,]+)\s*cu\s*m/yr', content, re.IGNORECASE)
        if m:
            rows.append(make_row(field_id, 'per_capita',
                                 numeric_val=float(m.group(1).replace(',', '')),
                                 units='cu m/yr', date_est=date_est,
                                 source_frag=m.group(0)))
    return rows


def parse_broadband(field_id, content):
    """Broadband fixed subscriptions: total and per 100 inhabitants."""
    rows = []
    content = normalize_content(content)
    date_est = extract_date_est(content)

    # Total: "total: 131 million" or "total: 28,670,016"
    m = re.search(r'total\s*:\s*([\d.,]+)\s*(million|billion)?', content, re.IGNORECASE)
    if m:
        val = float(m.group(1).replace(',', ''))
        mag = (m.group(2) or '').lower()
        if mag == 'million':
            val *= 1e6
        elif mag == 'billion':
            val *= 1e9
        rows.append(make_row(field_id, 'total',
                             numeric_val=val,
                             date_est=extract_date_est(m.group(0)) or date_est,
                             source_frag=m.group(0)))

    # Subscriptions per 100 inhabitants
    m = re.search(r'subscriptions per 100 inhabitants\s*:\s*([\d.]+)',
                  content, re.IGNORECASE)
    if m:
        rows.append(make_row(field_id, 'subscriptions_per_100',
                             numeric_val=float(m.group(1)),
                             date_est=extract_date_est(m.group(0)) or date_est,
                             source_frag=m.group(0)))
    return rows


def parse_water_sanitation(field_id, content):
    """Drinking water source / Sanitation facility access: improved/unimproved."""
    rows = []
    content = normalize_content(content)
    date_est = extract_date_est(content)

    # Format 1 (2011-2024): "improved: urban: 99.9% of population rural: ..."
    if re.search(r'\bimproved\s*:', content, re.IGNORECASE):
        # Split content at improved/unimproved labels
        sections = re.split(r'\b(unimproved|improved)\s*:', content, flags=re.IGNORECASE)
        current_cat = None
        for section in sections:
            stripped = section.strip().lower()
            if stripped in ('improved', 'unimproved'):
                current_cat = stripped
                continue
            if current_cat:
                for loc in ['urban', 'rural', 'total']:
                    m = re.search(
                        re.escape(loc) + r'\s*:\s*([\d.]+)%\s*of\s*population',
                        section, re.IGNORECASE
                    )
                    if m:
                        rows.append(make_row(
                            field_id, f'{current_cat}_{loc}',
                            numeric_val=float(m.group(1)),
                            units='% of population', date_est=date_est,
                            source_frag=m.group(0)))
    else:
        # Format 2 (2025 flat): 6 values in sequence — first 3 improved, last 3 unimproved
        all_pcts = list(re.finditer(
            r'(urban|rural|total)\s*:\s*([\d.]+)%\s*of\s*population',
            content, re.IGNORECASE
        ))
        if len(all_pcts) == 6:
            cats = ['improved'] * 3 + ['unimproved'] * 3
            for i, m in enumerate(all_pcts):
                loc = m.group(1).lower()
                rows.append(make_row(
                    field_id, f'{cats[i]}_{loc}',
                    numeric_val=float(m.group(2)),
                    units='% of population',
                    date_est=extract_date_est(m.group(0)) or date_est,
                    source_frag=m.group(0)))
        elif len(all_pcts) == 3:
            for m in all_pcts:
                loc = m.group(1).lower()
                rows.append(make_row(
                    field_id, f'improved_{loc}',
                    numeric_val=float(m.group(2)),
                    units='% of population',
                    date_est=extract_date_est(m.group(0)) or date_est,
                    source_frag=m.group(0)))
    return rows


def parse_waste_recycling(field_id, content):
    """Waste and recycling: generated, recycled, percent recycled."""
    rows = []
    content = normalize_content(content)

    # "municipal solid waste generated annually: 265.225 million tons (2024 est.)"
    m = re.search(
        r'municipal solid waste generated annually\s*:\s*([\d.,]+)\s*(million|billion)?\s*tons?',
        content, re.IGNORECASE
    )
    if m:
        val = float(m.group(1).replace(',', ''))
        mag = (m.group(2) or '').lower()
        if mag == 'million':
            val *= 1e6
        elif mag == 'billion':
            val *= 1e9
        rows.append(make_row(field_id, 'generated_annually',
                             numeric_val=val, units='tons',
                             date_est=extract_date_est(m.group(0)),
                             source_frag=m.group(0)))

    # "municipal solid waste recycled annually: 89.268 million tons ..."
    m = re.search(
        r'municipal solid waste recycled annually\s*:\s*([\d.,]+)\s*(million|billion)?\s*tons?',
        content, re.IGNORECASE
    )
    if m:
        val = float(m.group(1).replace(',', ''))
        mag = (m.group(2) or '').lower()
        if mag == 'million':
            val *= 1e6
        elif mag == 'billion':
            val *= 1e9
        rows.append(make_row(field_id, 'recycled_annually',
                             numeric_val=val, units='tons',
                             date_est=extract_date_est(m.group(0)),
                             source_frag=m.group(0)))

    # "percent of municipal solid waste recycled: 14.8% (2022 est.)"
    m = re.search(
        r'percent of municipal solid waste recycled\s*:\s*([\d.]+)%',
        content, re.IGNORECASE
    )
    if m:
        rows.append(make_row(field_id, 'percent_recycled',
                             numeric_val=float(m.group(1)), units='%',
                             date_est=extract_date_est(m.group(0)),
                             source_frag=m.group(0)))
    return rows


def parse_forest_revenue(field_id, content):
    """Revenue from forest resources: % of GDP."""
    rows = []
    content = normalize_content(content)
    date_est = extract_date_est(content)

    # "forest revenues: 0.04% of GDP (2018 est.)" or just "0.04% of GDP"
    m = re.search(r'(?:forest revenues\s*:\s*)?([\d.]+)%\s*of\s*GDP', content, re.IGNORECASE)
    if m:
        rows.append(make_row(field_id, 'value',
                             numeric_val=float(m.group(1)), units='% of GDP',
                             date_est=date_est,
                             source_frag=m.group(0)))
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
                                     date_est=extract_date_est(val_text),
                                     source_frag=part))
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
                                         date_est=extract_date_est(val_text),
                                         source_frag=part))
                # Check for percentage
                elif re.search(r'[\d.]+%', val_text):
                    pm = re.search(r'([\d.]+)%', val_text)
                    rows.append(make_row(field_id, label,
                                         numeric_val=float(pm.group(1)), units='%',
                                         date_est=extract_date_est(val_text),
                                         source_frag=part))
                else:
                    # Store as text
                    rows.append(make_row(field_id, label, text_val=val_text,
                                         source_frag=part))
        elif not rows:
            # No label found — try bare numeric
            nm = re.search(r'^(-?[\d,]+\.?\d*)\s*(.*)', part.strip())
            if nm:
                num = parse_number(nm.group(1))
                if num is not None:
                    rows.append(make_row(field_id, 'value',
                                         numeric_val=num,
                                         date_est=date_est, rank=rank,
                                         source_frag=part))

    # If nothing parsed, store whole content as text
    if not rows:
        rows.append(make_row(field_id, 'value', text_val=content.strip()[:4000],
                             date_est=date_est, rank=rank,
                             source_frag=content.strip()[:MAX_FRAG_LEN]))

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
    # v3.2 — new dedicated parsers
    'Sex ratio':                                parse_sex_ratio,
    'Literacy':                                 parse_literacy,
    'Maritime claims':                          parse_maritime_claims,
    'Natural gas':                              parse_natural_gas,
    'Internet users':                           parse_internet_users,
    'Telephones - fixed lines':                 parse_telephones,
    'Telephones - mobile cellular':             parse_telephones,
    'Debt - external':                          parse_multi_year_dollar,
    # v3.2 — expanded parsers (batch 2)
    'GDP - composition, by sector of origin':               parse_gdp_composition,
    'Household income or consumption by percentage share':  parse_household_income,
    'School life expectancy (primary to tertiary education)': parse_school_life_expectancy,
    'Youth unemployment rate (ages 15-24)':                 parse_youth_unemployment,
    'Unemployment, youth ages 15-24':                       parse_youth_unemployment,
    'Carbon dioxide emissions':                             parse_co2_emissions,
    'Carbon dioxide emissions from consumption of energy':  parse_co2_emissions,
    'Total water withdrawal':                               parse_water_withdrawal,
    'Freshwater withdrawal (domestic/industrial/agricultural)': parse_water_withdrawal,
    'Broadband - fixed subscriptions':                      parse_broadband,
    'Drinking water source':                                parse_water_sanitation,
    'Sanitation facility access':                           parse_water_sanitation,
    'Waste and recycling':                                  parse_waste_recycling,
    'Revenue from forest resources':                        parse_forest_revenue,
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
        INSERT INTO FieldValues (FieldID, SubField, NumericVal, Units, TextVal, DateEst, Rank, SourceFragment)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
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
                value_rows = [make_row(field_id, 'value', text_val=str(content)[:4000],
                                       source_frag=str(content)[:MAX_FRAG_LEN])]

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
