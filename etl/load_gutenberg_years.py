"""
CIA Factbook Archive - Load 1990s from Project Gutenberg
========================================================
Downloads plain-text CIA World Factbook editions from Project Gutenberg
and loads them into the database. Also handles 2001 (broken HTML fallback).

Four text format variants across the decade:
  1990:       "old"      - Country:  Name / - Section / Field: value
  1991-1992:  "tagged"   - _@_Name / _*_Section / _#_Field: value
  1993-1994:  "asterisk" - *Name, Section / Field:\n  value
  1995-2000:  "at-sign"  - @Name:Section / Field: value (inline)
  2001:       "equals"   - @Name / Name    Section / Field: value

Run:
  python load_gutenberg_years.py                  # Load all 1990-1999 + fix 2001
  python load_gutenberg_years.py --year 1995      # Load single year
  python load_gutenberg_years.py --dry-run        # Preview without DB writes
"""
import pyodbc
import sys
import os
import re
import urllib.request
import time

CONN_STR = (
    "DRIVER={ODBC Driver 18 for SQL Server};"
    "SERVER=localhost;"
    "DATABASE=CIA_WorldFactbook;"
    "Trusted_Connection=yes;"
    "TrustServerCertificate=yes;"
)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TEXT_DIR = os.path.join(SCRIPT_DIR, "text_samples")

# Project Gutenberg ebook numbers for each year
PG_EBOOKS = {
    1990: 14,
    1991: 25,
    1992: 48,
    1993: 87,
    1994: 180,
    1995: 571,
    1996: 27675,
    1997: 1662,
    1998: 2016,
    1999: 27676,
    2001: 27638,
}

# Format type for each year
YEAR_FORMATS = {
    1990: 'old',
    1991: 'tagged',
    1992: 'colon',
    1993: 'asterisk',
    1994: 'asterisk',
    1995: 'atsign',
    1996: 'atsign_bare',
    1997: 'atsign',
    1998: 'atsign',
    1999: 'atsign_bare',
    2001: 'equals',
}

# Known category names across all formats
KNOWN_CATEGORIES = {
    'Geography', 'People', 'Government', 'Economy', 'Communications',
    'Defense Forces', 'Transportation', 'Military', 'Transnational Issues',
    'Introduction', 'People and Society', 'Energy', 'Environment',
}


# ============================================================
# DOWNLOAD
# ============================================================

def download_text(year):
    """Download text file from Project Gutenberg, cache locally."""
    os.makedirs(TEXT_DIR, exist_ok=True)
    path = os.path.join(TEXT_DIR, f"{year}.txt")

    if os.path.exists(path) and os.path.getsize(path) > 10000:
        print(f"    Already have {year}.txt ({os.path.getsize(path):,} bytes)")
        return path

    ebook_id = PG_EBOOKS[year]
    url = f"https://www.gutenberg.org/cache/epub/{ebook_id}/pg{ebook_id}.txt"
    print(f"    Downloading {url}...")

    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'CIA-Factbook-Archive/1.0'})
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = resp.read()
        with open(path, 'wb') as f:
            f.write(data)
        print(f"    Saved {len(data):,} bytes to {path}")
        return path
    except Exception as e:
        print(f"    FAILED to download {year}: {e}")
        return None


def strip_pg_wrapper(text):
    """Remove Project Gutenberg header and footer."""
    # Find start marker
    start_match = re.search(r'\*\*\* START OF (?:THE )?PROJECT GUTENBERG EBOOK.*?\*\*\*', text)
    if start_match:
        text = text[start_match.end():]

    # Find end marker
    end_match = re.search(r'\*\*\* END OF (?:THE )?PROJECT GUTENBERG EBOOK.*?\*\*\*', text)
    if end_match:
        text = text[:end_match.start()]

    return text.strip()


# ============================================================
# PARSERS
# ============================================================

def parse_old_format(text):
    """
    1990 format:
      Country:  Afghanistan
      - Geography
      Total area: 647,500 km2
      ...
      - People
      Population: 15,862,293
    """
    countries = []
    # Split on "Country:  Name" lines
    entries = re.split(r'\n(?=Country:\s{2,})', text)

    for entry in entries:
        match = re.match(r'Country:\s{2,}(.+)', entry.strip())
        if not match:
            continue
        country_name = match.group(1).strip()

        # Split into sections by "- SectionName"
        sections = re.split(r'\n(?=- [A-Z])', entry[match.end():])
        categories = []

        for section in sections:
            sec_match = re.match(r'- (.+)', section.strip())
            if not sec_match:
                continue
            cat_name = sec_match.group(1).strip()

            # Extract fields: "FieldName: value" at start of line
            fields = extract_inline_fields(section[sec_match.end():])
            if fields:
                categories.append((cat_name, fields))

        if categories:
            countries.append((country_name, categories))

    return countries


def parse_tagged_format(text):
    """
    1991-1992 format:
      _@_Afghanistan
      _*_Geography
      _#_Total area: 647,500 km2
      _*_People
      _#_Population: 16,450,304
    """
    countries = []
    # Split on _@_ markers
    entries = re.split(r'\n_@_', text)

    for entry in entries:
        lines = entry.strip().split('\n')
        if not lines:
            continue
        country_name = lines[0].strip()
        if not country_name or len(country_name) > 100:
            continue
        # Skip preamble entries (dates, headers, etc.)
        if re.match(r'^\d', country_name) or country_name.startswith('*'):
            continue

        categories = []
        current_cat = None
        current_fields = []

        for line in lines[1:]:
            line = line.strip()
            if line.startswith('_*_'):
                # New section
                if current_cat and current_fields:
                    categories.append((current_cat, current_fields))
                current_cat = line[3:].strip()
                current_fields = []
            elif line.startswith('_#_'):
                # Field entry
                field_text = line[3:].strip()
                colon_pos = field_text.find(':')
                if colon_pos > 0:
                    fname = field_text[:colon_pos].strip()
                    fval = field_text[colon_pos + 1:].strip()
                    if fname and fval:
                        current_fields.append((fname, fval))
            elif current_fields and line and not line.startswith('_'):
                # Continuation of previous field value
                last_name, last_val = current_fields[-1]
                current_fields[-1] = (last_name, last_val + ' ' + line)

        if current_cat and current_fields:
            categories.append((current_cat, current_fields))

        if categories:
            countries.append((country_name, categories))

    return countries


def parse_asterisk_format(text):
    """
    1993-1994 format:
      *Afghanistan, Geography    (1993)
      @Afghanistan, Geography   (1994)
      Location:
        South Asia, between Iran and Pakistan
      Area:
       total area:
        647,500 km2
    """
    countries = []
    # Find all *Country, Section or @Country, Section markers
    # Only match known section names to avoid splitting country names with commas
    # (e.g., "Korea, North" should NOT be split into country="Korea" section="North")
    # Use greedy (.+) for country name so "Korea, North, Geography" captures
    # country="Korea, North" and section="Geography"
    known_pattern = '|'.join(re.escape(s) for s in sorted(KNOWN_CATEGORIES, key=len, reverse=True))
    markers = list(re.finditer(rf'^[\*@](.+),\s*({known_pattern})\s*$', text, re.MULTILINE))

    # Group markers by country
    country_sections = {}
    for i, marker in enumerate(markers):
        country_name = marker.group(1).strip()
        section_name = marker.group(2).strip()

        start = marker.end()
        end = markers[i + 1].start() if i + 1 < len(markers) else len(text)
        section_text = text[start:end]

        if country_name not in country_sections:
            country_sections[country_name] = {}
        # Merge sections with same name (1993 has duplicate section headers)
        if section_name in country_sections[country_name]:
            country_sections[country_name][section_name] += '\n' + section_text
        else:
            country_sections[country_name][section_name] = section_text

    for country_name, sections in country_sections.items():
        categories = []
        for section_name, section_text in sections.items():
            fields = extract_indented_fields(section_text)
            if fields:
                categories.append((section_name, fields))
        if categories:
            countries.append((country_name, categories))

    return countries


def parse_atsign_format(text):
    """
    1995-1999 format:
      @Afghanistan:Geography
       Location: Southern Asia, north of Pakistan
       Area:
       total area: 647,500 sq km
    """
    countries = []

    # Skip preamble: find first _____ separator line (marks start of country data)
    preamble_end = re.search(r'^_{20,}$', text, re.MULTILINE)
    if preamble_end:
        text = text[preamble_end.end():]

    # Find all @Country:Section markers
    markers = list(re.finditer(r'^@([^:\n]+):([A-Za-z][\w ]*)', text, re.MULTILINE))

    # Known bare section headers (appear without @ prefix in some years like 1997)
    bare_sections = {
        'Economy', 'Military', 'Transnational Issues', 'Defense Forces',
        'Introduction', 'People and Society',
    }

    country_sections = {}
    for i, marker in enumerate(markers):
        country_name = marker.group(1).strip()
        section_name = marker.group(2).strip()

        start = marker.end()
        end = markers[i + 1].start() if i + 1 < len(markers) else len(text)
        section_text = text[start:end]

        if country_name not in country_sections:
            country_sections[country_name] = []

        # Check for bare section headers within this block
        # (e.g., 1997 has Economy, Military, Transnational Issues as bare lines)
        parts = _split_bare_sections(section_text, bare_sections)
        country_sections[country_name].append((section_name, parts[0][1]))
        for bare_name, bare_text in parts[1:]:
            country_sections[country_name].append((bare_name, bare_text))

    for country_name, sections in country_sections.items():
        categories = []
        for section_name, section_text in sections:
            # 1995-1999 uses a mix of inline and indented fields
            fields = extract_mixed_fields(section_text)
            if fields:
                categories.append((section_name, fields))
        if categories:
            countries.append((country_name, categories))

    return countries


def _split_bare_sections(text, section_names):
    """Split text at bare section headers (lines matching known section names exactly).
    Returns list of (section_name, section_text) tuples.
    The first element uses None as section_name (belongs to the parent section)."""
    # Build regex pattern for bare section headers
    escaped = [re.escape(s) for s in section_names]
    pattern = re.compile(r'^(' + '|'.join(escaped) + r')\s*$', re.MULTILINE)

    splits = list(pattern.finditer(text))
    if not splits:
        return [(None, text)]

    result = [(None, text[:splits[0].start()])]
    for i, m in enumerate(splits):
        end = splits[i + 1].start() if i + 1 < len(splits) else len(text)
        result.append((m.group(1).strip(), text[m.end():end]))
    return result


def parse_colon_format(text):
    """
    1992 format:
      :Afghanistan Geography
      Total area:
          647,500 km2
      :Afghanistan People
      Population:
          16,095,664
    """
    countries = []
    # Find all :Country Section markers
    markers = list(re.finditer(r'^:([A-Za-z][\w\s,\'\.\-\(\)]+?)\s+(Geography|People|Government|Economy|Communications|Defense Forces|Transportation|Transnational Issues)\s*$',
                               text, re.MULTILINE))

    country_sections = {}
    for i, marker in enumerate(markers):
        country_name = marker.group(1).strip()
        section_name = marker.group(2).strip()

        start = marker.end()
        end = markers[i + 1].start() if i + 1 < len(markers) else len(text)
        section_text = text[start:end]

        if country_name not in country_sections:
            country_sections[country_name] = {}
        if section_name in country_sections[country_name]:
            country_sections[country_name][section_name] += '\n' + section_text
        else:
            country_sections[country_name][section_name] = section_text

    for country_name, sections in country_sections.items():
        categories = []
        for section_name, section_text in sections.items():
            fields = extract_indented_fields(section_text)
            if fields:
                categories.append((section_name, fields))
        if categories:
            countries.append((country_name, categories))

    return countries


def parse_atsign_bare_format(text):
    """
    1996 and 1999 format:
      =====================================================================
      @Afghanistan
      -----------
      Geography
      ---------
      Location: Southern Asia, north of Pakistan
      People
      ------
      Population: 21,251,821

    Country markers: @CountryName on its own line
    Section markers: bare section name (Geography, People, etc.) on its own line
    """
    countries = []
    # Find @Country markers
    country_markers = list(re.finditer(r"^@([A-Za-z][A-Za-z ,'\.\-\(\)]+)$", text, re.MULTILINE))

    # Known section names
    section_names = {
        'Geography', 'People', 'Government', 'Economy', 'Communications',
        'Transportation', 'Defense Forces', 'Military', 'Transnational Issues',
        'Introduction', 'People and Society',
    }

    for idx, marker in enumerate(country_markers):
        country_name = marker.group(1).strip()
        if not country_name or len(country_name) > 100:
            continue

        start = marker.end()
        end = country_markers[idx + 1].start() if idx + 1 < len(country_markers) else len(text)
        content = text[start:end]

        # Find section headers: bare names on their own line, often followed by ---
        lines = content.split('\n')
        sections = []
        current_section = None
        current_lines = []

        for line in lines:
            stripped = line.strip()
            # Skip dash-only lines (underlines)
            if re.match(r'^-+$', stripped):
                continue
            # Skip equals separator lines
            if re.match(r'^=+$', stripped):
                continue
            # Check if this is a section header
            if stripped in section_names:
                if current_section is not None:
                    sections.append((current_section, '\n'.join(current_lines)))
                current_section = stripped
                current_lines = []
            elif current_section is not None:
                current_lines.append(line)

        if current_section is not None:
            sections.append((current_section, '\n'.join(current_lines)))

        categories = []
        for section_name, section_text in sections:
            fields = extract_mixed_fields(section_text)
            if fields:
                categories.append((section_name, fields))

        if categories:
            countries.append((country_name, categories))

    return countries


def parse_equals_format(text):
    """
    2001 format:
      @Afghanistan

      Afghanistan    Introduction
      Background: long text...

      Afghanistan    Geography
      Location: Southern Asia
    """
    countries = []
    # Find all @CountryName markers (on their own line)
    country_markers = list(re.finditer(r"^@([A-Za-z][A-Za-z ,'\.\-\(\)]+)$", text, re.MULTILINE))

    for idx, marker in enumerate(country_markers):
        country_name = marker.group(1).strip()
        if not country_name or len(country_name) > 100:
            continue

        # Content is between this @marker and the next one
        start = marker.end()
        end = country_markers[idx + 1].start() if idx + 1 < len(country_markers) else len(text)
        content = text[start:end]

        # Find sections: "CountryName    SectionName"
        escaped_name = re.escape(country_name)
        section_pattern = rf'^{escaped_name}[ \t]{{4,}}(\w[\w ]*?)[ \t]*$'
        section_matches = list(re.finditer(section_pattern, content, re.MULTILINE))

        categories = []
        for j, sm in enumerate(section_matches):
            section_name = sm.group(1).strip()
            # Normalize junk suffixes (e.g., "Introduction Top of Page" -> "Introduction")
            for known in KNOWN_CATEGORIES:
                if section_name.startswith(known) and section_name != known:
                    section_name = known
                    break
            sec_start = sm.end()
            sec_end = section_matches[j + 1].start() if j + 1 < len(section_matches) else len(content)
            section_text = content[sec_start:sec_end]

            fields = extract_inline_fields(section_text)
            if fields:
                categories.append((section_name, fields))

        if categories:
            countries.append((country_name, categories))

    return countries


# ============================================================
# FIELD EXTRACTION HELPERS
# ============================================================

def extract_inline_fields(text):
    """
    Extract fields in 'FieldName: value' format (inline, single-line values).
    Used by 1990 and 2001 formats.
    Multi-line values: continuation lines that don't start a new field.
    """
    fields = []
    lines = text.split('\n')
    current_name = None
    current_value = None

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        # Skip separator lines
        if re.match(r'^[-=_]{10,}$', stripped):
            continue

        # Check for "FieldName: value" pattern at start
        field_match = re.match(r'^([A-Z][\w\s\-,()\/]+?):\s+(.+)', stripped)
        if field_match:
            # Save previous field
            if current_name and current_value:
                fields.append((current_name.strip(), current_value.strip()))
            current_name = field_match.group(1)
            current_value = field_match.group(2)
        elif current_name and current_value:
            # Continuation line - starts with lowercase or is indented
            if not re.match(r'^[A-Z][\w\s\-,()\/]+?:', stripped):
                current_value += ' ' + stripped

    # Don't forget the last field
    if current_name and current_value:
        fields.append((current_name.strip(), current_value.strip()))

    return fields


def extract_indented_fields(text):
    """
    Extract fields in indented format (1993-1994).
    FieldName:
      value on next line(s)
    Sub-fields also indented under parent.
    """
    fields = []
    lines = text.split('\n')
    current_name = None
    current_value_parts = []

    for line in lines:
        if not line.strip():
            continue

        # Skip separators
        if re.match(r'^[\*\-=_]{5,}', line.strip()):
            continue

        # Check if line starts at column 0 and ends with ':'  -> field name
        # Or has "FieldName: value" on same line
        if line and not line[0].isspace() and ':' in line:
            # Save previous field
            if current_name:
                val = ' | '.join(current_value_parts).strip()
                if val:
                    fields.append((current_name, val))
                current_value_parts = []

            colon_pos = line.index(':')
            current_name = line[:colon_pos].strip()
            remainder = line[colon_pos + 1:].strip()
            if remainder:
                current_value_parts = [remainder]
            else:
                current_value_parts = []
        elif line.startswith(' ') and current_name:
            # Indented line -> value or sub-field
            stripped = line.strip()
            # Check for sub-field pattern "sub_name: value" (indented)
            sub_match = re.match(r'^(\w[\w\s\-]*?):\s+(.+)', stripped)
            if sub_match:
                sub_name = sub_match.group(1).strip()
                sub_val = sub_match.group(2).strip()
                current_value_parts.append(f"{sub_name}: {sub_val}")
            elif re.match(r'^(\w[\w\s\-]*?):\s*$', stripped):
                # Sub-field name only, value on next line
                sub_match = re.match(r'^(\w[\w\s\-]*?):\s*$', stripped)
                current_value_parts.append(f"{sub_match.group(1)}:")
            else:
                current_value_parts.append(stripped)

    # Last field
    if current_name:
        val = ' | '.join(current_value_parts).strip()
        if val:
            fields.append((current_name, val))

    return fields


def extract_mixed_fields(text):
    """
    Extract fields from 1995-1999 format.
    Mix of inline 'Field: value' and indented sub-fields.
    Lines are often space-indented (1-2 spaces).
    """
    fields = []
    lines = text.split('\n')
    current_name = None
    current_value_parts = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        # Skip separator lines
        if re.match(r'^[-=_]{10,}$', stripped):
            continue

        # Check for field pattern: "FieldName: value" (may be indented 1 space)
        field_match = re.match(r'^\s{0,2}([A-Z][\w\s\-,()\/\.]+?):\s*(.*)', line)
        if field_match:
            fname = field_match.group(1).strip()
            fval = field_match.group(2).strip()
            # Make sure it's a real field name (not a sub-field like "total area:")
            if fname and fname[0].isupper():
                # Save previous
                if current_name:
                    val = ' | '.join(current_value_parts).strip()
                    if val:
                        fields.append((current_name, val))
                current_name = fname
                current_value_parts = [fval] if fval else []
                continue

        # Indented sub-field or continuation
        if current_name:
            # Sub-field: "sub_name: value"
            sub_match = re.match(r'^\s+(\w[\w\s\-]*?):\s+(.+)', line)
            if sub_match:
                sub_name = sub_match.group(1).strip()
                sub_val = sub_match.group(2).strip()
                current_value_parts.append(f"{sub_name}: {sub_val}")
            elif stripped:
                current_value_parts.append(stripped)

    # Last field
    if current_name:
        val = ' | '.join(current_value_parts).strip()
        if val:
            fields.append((current_name, val))

    return fields


# ============================================================
# NAME-TO-CODE MAPPING
# ============================================================

def build_name_to_master_map(cursor):
    """Build a mapping from various country names to MasterCountryID and code."""
    cursor.execute("SELECT MasterCountryID, CanonicalCode, CanonicalName FROM MasterCountries")
    name_map = {}
    code_map = {}
    for row in cursor.fetchall():
        mid, code, name = row
        name_map[name.lower().strip()] = (mid, code.lower())
        code_map[code.lower()] = mid

    # Add common historical name variants
    aliases = {
        'burma': 'myanmar',
        'ivory coast': "cote d'ivoire",
        'zaire': 'congo, democratic republic of the',
        'czech republic': 'czechia',
        'swaziland': 'eswatini',
        'Macedonia': 'north macedonia',
        'the bahamas': 'bahamas, the',
        'the gambia': 'gambia, the',
        'bahamas': 'bahamas, the',
        'gambia': 'gambia, the',
    }
    for alias, canonical in aliases.items():
        if canonical.lower() in name_map and alias.lower() not in name_map:
            name_map[alias.lower()] = name_map[canonical.lower()]

    return name_map, code_map


def find_master_match(country_name, name_map):
    """Find a MasterCountry match for a country name."""
    key = country_name.lower().strip()

    # Direct match
    if key in name_map:
        return name_map[key]

    # Try without "The" prefix
    if key.startswith('the '):
        without_the = key[4:]
        if without_the in name_map:
            return name_map[without_the]

    # Try fuzzy: strip common suffixes/prefixes
    for name, val in name_map.items():
        if key in name or name in key:
            return val

    return None, None


def make_code(country_name):
    """Generate a short code from a country name (fallback when no master match)."""
    # Use first 2 consonants + first vowel, or first 2 chars
    clean = re.sub(r'[^a-zA-Z]', '', country_name)
    return clean[:2].lower() if len(clean) >= 2 else country_name[:2].lower()


# ============================================================
# DATABASE OPERATIONS
# ============================================================

def snapshot_master_links(cursor, year):
    """Capture Code -> MasterCountryID mapping before deletion."""
    cursor.execute("""
        SELECT Code, MasterCountryID
        FROM Countries
        WHERE Year = ? AND MasterCountryID IS NOT NULL
    """, year)
    return {row[0]: row[1] for row in cursor.fetchall()}


def delete_year_data(cursor, conn, year):
    """Delete all data for a year, respecting FK constraints."""
    cursor.execute("SELECT CountryID FROM Countries WHERE Year = ?", year)
    country_ids = [row[0] for row in cursor.fetchall()]
    if not country_ids:
        return 0
    chunk_size = 50
    for i in range(0, len(country_ids), chunk_size):
        chunk = country_ids[i:i + chunk_size]
        placeholders = ','.join(['?'] * len(chunk))
        cursor.execute(f"DELETE FROM CountryFields WHERE CountryID IN ({placeholders})", chunk)
        cursor.execute(f"DELETE FROM CountryCategories WHERE CountryID IN ({placeholders})", chunk)
        cursor.execute(f"DELETE FROM Countries WHERE CountryID IN ({placeholders})", chunk)
        conn.commit()
    print(f"    Deleted {len(country_ids)} countries and all associated data")
    return len(country_ids)


def load_year(cursor, conn, year, countries, name_map, old_master_links):
    """Insert parsed countries into the database."""
    success = 0
    failed = 0
    unlinked = 0

    for country_name, categories in countries:
        try:
            # Find code and MasterCountryID
            master_id, code = find_master_match(country_name, name_map)
            if not code:
                code = make_code(country_name)

            # Check old master links by code
            if not master_id and code in old_master_links:
                master_id = old_master_links[code]

            # Insert country
            cursor.execute(
                "INSERT INTO Countries (Year, Code, Name, Source) OUTPUT INSERTED.CountryID VALUES (?, ?, ?, ?)",
                year, code, country_name, 'text'
            )
            country_id = cursor.fetchone()[0]

            # Set MasterCountryID
            if master_id:
                cursor.execute(
                    "UPDATE Countries SET MasterCountryID = ? WHERE CountryID = ?",
                    master_id, country_id
                )
            else:
                unlinked += 1

            # Insert categories and fields
            for cat_title, fields in categories:
                cursor.execute(
                    "INSERT INTO CountryCategories (CountryID, CategoryTitle) OUTPUT INSERTED.CategoryID VALUES (?, ?)",
                    country_id, cat_title[:200]
                )
                cat_id = cursor.fetchone()[0]
                for fname, content in fields:
                    cursor.execute(
                        "INSERT INTO CountryFields (CategoryID, CountryID, FieldName, Content) VALUES (?, ?, ?, ?)",
                        cat_id, country_id, fname[:200], content
                    )

            conn.commit()
            success += 1

        except Exception as e:
            conn.rollback()
            print(f"      ERROR [{country_name}]: {e}")
            failed += 1

    print(f"    Inserted: {success} countries, {failed} failed, {unlinked} unlinked to MasterCountries")
    return success, failed, unlinked


def verify_year(cursor, year):
    """Verify loaded year has reasonable data."""
    cursor.execute("SELECT COUNT(*) FROM Countries WHERE Year = ?", year)
    countries = cursor.fetchone()[0]
    cursor.execute("""
        SELECT COUNT(*) FROM CountryCategories cc
        JOIN Countries c ON cc.CountryID = c.CountryID WHERE c.Year = ?
    """, year)
    categories = cursor.fetchone()[0]
    cursor.execute("""
        SELECT COUNT(*) FROM CountryFields cf
        JOIN Countries c ON cf.CountryID = c.CountryID WHERE c.Year = ?
    """, year)
    fields = cursor.fetchone()[0]

    avg_cats = categories / max(countries, 1)
    avg_fields = fields / max(countries, 1)

    print(f"    {countries} countries | {categories:,} categories | {fields:,} fields")
    print(f"    Avg: {avg_cats:.1f} categories/country, {avg_fields:.1f} fields/country")

    warnings = []
    if countries < 180:
        warnings.append(f"Low country count: {countries}")
    if avg_cats < 3:
        warnings.append(f"Too few categories/country ({avg_cats:.1f})")
    if avg_fields < 10:
        warnings.append(f"Too few fields/country ({avg_fields:.1f})")

    cursor.execute("""
        SELECT COUNT(*) FROM Countries
        WHERE Year = ? AND MasterCountryID IS NULL
    """, year)
    null_master = cursor.fetchone()[0]
    if null_master > 0:
        warnings.append(f"{null_master} countries missing MasterCountryID (expected for dissolved states)")

    if warnings:
        for w in warnings:
            print(f"    NOTE: {w}")
    else:
        print(f"    OK")

    return len(warnings) == 0


# ============================================================
# MAIN
# ============================================================

def main():
    dry_run = '--dry-run' in sys.argv

    # Determine which years to load
    target_years = []
    for arg in sys.argv[1:]:
        if arg.startswith('--'):
            continue
        try:
            y = int(arg)
            if y in PG_EBOOKS:
                target_years.append(y)
            else:
                print(f"Year {y} not available. Options: {sorted(PG_EBOOKS.keys())}")
                return 1
        except ValueError:
            pass

    # Also support --year N
    for i, arg in enumerate(sys.argv[1:], 1):
        if arg == '--year' and i < len(sys.argv) - 1:
            try:
                y = int(sys.argv[i + 1])
                if y in PG_EBOOKS and y not in target_years:
                    target_years.append(y)
            except ValueError:
                pass

    if not target_years:
        target_years = sorted(PG_EBOOKS.keys())

    print("=" * 70)
    print("CIA FACTBOOK - LOAD PROJECT GUTENBERG EDITIONS")
    print("=" * 70)
    if dry_run:
        print("MODE: DRY RUN (no database changes)")
    print(f"Years to load: {sorted(target_years)}")
    print()

    # Connect to database
    conn = pyodbc.connect(CONN_STR)
    cursor = conn.cursor()
    print("Connected to database.")

    # Build name-to-master mapping
    name_map, code_map = build_name_to_master_map(cursor)
    print(f"Loaded {len(name_map)} name mappings from MasterCountries.\n")

    results = {}
    for year in sorted(target_years):
        fmt = YEAR_FORMATS[year]
        print(f"{'=' * 60}")
        print(f"  YEAR {year} (format: {fmt})")
        print(f"{'=' * 60}")

        # Step 1: Download text
        print(f"  Step 1: Downloading text...")
        path = download_text(year)
        if not path:
            results[year] = "DOWNLOAD FAILED"
            continue

        # Step 2: Parse
        print(f"  Step 2: Parsing...")
        with open(path, 'r', encoding='utf-8', errors='replace') as f:
            raw_text = f.read()

        text = strip_pg_wrapper(raw_text)

        if fmt == 'old':
            countries = parse_old_format(text)
        elif fmt == 'tagged':
            countries = parse_tagged_format(text)
        elif fmt == 'asterisk':
            countries = parse_asterisk_format(text)
        elif fmt == 'atsign':
            countries = parse_atsign_format(text)
        elif fmt == 'colon':
            countries = parse_colon_format(text)
        elif fmt == 'atsign_bare':
            countries = parse_atsign_bare_format(text)
        elif fmt == 'equals':
            countries = parse_equals_format(text)
        else:
            print(f"    Unknown format: {fmt}")
            results[year] = "UNKNOWN FORMAT"
            continue

        total_fields = sum(len(f) for _, cats in countries for _, f in cats)
        print(f"    Parsed {len(countries)} countries, {total_fields:,} total fields")

        if dry_run:
            # Show sample
            for cname, cats in countries[:3]:
                print(f"\n    {cname}: {len(cats)} categories")
                for cat_name, fields in cats[:2]:
                    print(f"      [{len(fields)} fields] {cat_name}")
                    for fn, fv in fields[:2]:
                        print(f"        {fn}: {fv[:80]}...")
            results[year] = f"dry-run ({len(countries)} countries, {total_fields:,} fields)"
            continue

        # Step 3: Check if year already exists
        cursor.execute("SELECT COUNT(*) FROM Countries WHERE Year = ?", year)
        existing = cursor.fetchone()[0]
        old_master_links = {}
        if existing > 0:
            print(f"  Step 3: Deleting existing {existing} countries for {year}...")
            old_master_links = snapshot_master_links(cursor, year)
            delete_year_data(cursor, conn, year)
        else:
            print(f"  Step 3: No existing data for {year}")

        # Step 4: Load
        print(f"  Step 4: Loading into database...")
        success, failed, unlinked = load_year(cursor, conn, year, countries, name_map, old_master_links)

        # Step 5: Verify
        print(f"  Step 5: Verifying...")
        ok = verify_year(cursor, year)
        results[year] = "OK" if ok else "WARNINGS"

        # Brief pause between years
        if year != sorted(target_years)[-1]:
            time.sleep(1)

    # Summary
    print(f"\n{'=' * 60}")
    print("LOAD SUMMARY")
    print(f"{'=' * 60}")
    for year in sorted(results.keys()):
        print(f"  {year}: {results[year]}")

    # Full database status
    if not dry_run:
        print(f"\n{'=' * 60}")
        print("FULL DATABASE STATUS")
        print(f"{'=' * 60}")
        cursor.execute("""
            SELECT c.Year, c.Source, COUNT(*) AS Countries
            FROM Countries c GROUP BY c.Year, c.Source ORDER BY c.Year
        """)
        year_rows = cursor.fetchall()
        print(f"  {'Year':<6} {'Countries':<12} {'Categories':<12} {'Fields':<12} {'Source'}")
        print(f"  {'-' * 5:<6} {'-' * 9:<12} {'-' * 10:<12} {'-' * 8:<12} {'-' * 6}")
        for yr, src, cnt in year_rows:
            cursor.execute("SELECT COUNT(*) FROM CountryCategories cc JOIN Countries c ON cc.CountryID = c.CountryID WHERE c.Year = ?", yr)
            cats = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM CountryFields cf JOIN Countries c ON cf.CountryID = c.CountryID WHERE c.Year = ?", yr)
            flds = cursor.fetchone()[0]
            print(f"  {yr:<6} {cnt:<12} {cats:<12} {flds:<12,} {src}")

    cursor.close()
    conn.close()
    print("\nDone!")
    return 0


if __name__ == '__main__':
    exit(main())
