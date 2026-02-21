"""Shared parsers for extracting structured data from Factbook text fields."""
import re


def extract_number(t):
    m = re.search(r'[\d,]{5,}', str(t))
    return int(m.group().replace(',', '')) if m else None


def extract_pct_gdp(t):
    t = str(t)
    # Modern format: "4.06% of GDP (2005 est.)" or "5.8% of GNP"
    m = re.search(r'([\d.]+)%\s*of\s*G[DN]P', t)
    if m:
        return float(m.group(1))
    # Legacy format (pre-2008): "3.2% (FY99 est.)" — no "of GDP" suffix
    m = re.search(r'([\d.]+)%', t)
    return float(m.group(1)) if m else None


def extract_pct(t):
    m = re.search(r'([\d.]+)%', str(t))
    return float(m.group(1)) if m else None


def extract_gdp_percap(t):
    m = re.search(r'\$([\d,]+)', str(t))
    return int(m.group(1).replace(',', '')) if m else None


def extract_dollar_billions(t):
    t = str(t).lower()
    m = re.search(r'\$([\d.]+)\s*trillion', t)
    if m:
        return float(m.group(1)) * 1000
    m = re.search(r'\$([\d.]+)\s*billion', t)
    if m:
        return float(m.group(1))
    m = re.search(r'\$([\d.]+)\s*million', t)
    if m:
        return float(m.group(1)) / 1000
    m = re.search(r'\$([\d,]+)', t)
    if m:
        v = float(m.group(1).replace(',', ''))
        if v > 1e9:
            return v / 1e9
    return None


def parse_life_exp(t):
    t = str(t)
    # Modern format (1993+): "total population: 73.5 years"
    m = re.search(r'total population:\s*([\d.]+)', t)
    if m:
        return float(m.group(1))
    # Older format (1990-1992): "42 years male, 46 years female"
    m = re.search(r'([\d.]+)\s*years?\s*male\b.*?([\d.]+)\s*years?\s*female', t)
    if m:
        return round((float(m.group(1)) + float(m.group(2))) / 2, 1)
    # Bare number: "75.6 years"
    m = re.search(r'^([\d.]+)\s*years?', t.strip())
    if m:
        return float(m.group(1))
    return None


def extract_rate(t):
    m = re.search(r'([\d.]+)\s*(?:births|deaths)\s*/\s*1,000', str(t))
    if m:
        return float(m.group(1))
    m = re.search(r'^([\d.]+)', str(t).strip())
    return float(m.group(1)) if m else None


def extract_growth_rate(t):
    m = re.search(r'(-?[\d.]+)%', str(t))
    return float(m.group(1)) if m else None


def extract_per_100(t):
    """Extract 'subscriptions per 100 inhabitants: 113' or 'per 100: 38'."""
    m = re.search(r'per 100[^:]*:\s*([\d.]+)', str(t))
    return float(m.group(1)) if m else None


def extract_total_subs(t):
    """Extract total subscriptions from 'total subscriptions: 391 million'."""
    t = str(t).lower()
    m = re.search(r'total[^:]*:\s*([\d.]+)\s*billion', t)
    if m:
        return float(m.group(1)) * 1e9
    m = re.search(r'total[^:]*:\s*([\d.]+)\s*million', t)
    if m:
        return float(m.group(1)) * 1e6
    m = re.search(r'total[^:]*:\s*([\d,]+)', t)
    if m:
        return int(m.group(1).replace(',', ''))
    return None


def extract_capital_name(t):
    """Extract city name from Capital field: 'name: Kabul geographic coordinates: ...'"""
    t = str(t)
    # Match up to geographic, time difference, or semicolon
    m = re.search(r'name\s*:\s*(.+?)(?:\s+geographic|\s+time\s+(?:difference|zone)|;)', t, re.IGNORECASE)
    if not m:
        m = re.search(r'name\s*:\s*(.+?)$', t, re.IGNORECASE)
    if m:
        name = m.group(1).strip().rstrip(',;')
        # Strip parenthetical notes
        name = re.split(r'\s*\(', name)[0].strip()
        return name if name else None
    return None


def extract_area(t):
    """Extract total area in sq km: 'total : 652,230 sq km land: ...'"""
    m = re.search(r'total\s*:?\s*([\d,]+)\s*sq\s*km', str(t), re.IGNORECASE)
    if m:
        return int(m.group(1).replace(',', ''))
    return None


def parse_trade_partners(t):
    """Parse trade partner text into list of {name, pct}.

    Formats handled:
      "Italy 29%, Spain 12%, US 5% (2023)"
      "China 27.5%, US 16.9%, Japan 6% (2022 est.)"
      "Germany 22%, Netherlands 10.1% (2021)"
    Returns list sorted by pct descending.
    """
    if not t:
        return []
    t = str(t)
    # Strip year parenthetical and "partners:" prefix
    t = re.sub(r'\([\d, est.]+\)\s*$', '', t, flags=re.IGNORECASE)
    t = re.sub(r'^.*?(?:partners|partner)\s*:\s*', '', t, flags=re.IGNORECASE)
    results = []
    for m in re.finditer(r'([A-Z][\w\s,.\'-]+?)\s+([\d.]+)%', t):
        name = m.group(1).strip().rstrip(',')
        pct = float(m.group(2))
        if pct > 0:
            results.append({'name': name, 'pct': pct})
    results.sort(key=lambda x: x['pct'], reverse=True)
    return results


def parse_org_memberships(t):
    """Parse international organization text into list of acronyms.

    Formats: "AU, IAEA, IBRD, UN, WHO" or "ACP, AfDB, AU, ..."
    Returns sorted list of unique acronyms.
    """
    if not t:
        return []
    t = str(t)
    # Strip parenthetical qualifiers like "(observer)" or "(associate)"
    t = re.sub(r'\([^)]*\)', '', t)
    parts = re.split(r'[,;\n]+', t)
    orgs = set()
    for part in parts:
        part = part.strip()
        if part and len(part) <= 30:
            orgs.add(part)
    return sorted(orgs)
