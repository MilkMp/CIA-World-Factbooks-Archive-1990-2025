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
