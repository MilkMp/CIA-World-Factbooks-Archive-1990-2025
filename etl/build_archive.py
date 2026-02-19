"""
CIA World Factbook - Complete Historical Archive Builder
Downloads all factbook zips (2000-2020), parses HTML, loads into SQL Server.
Also loads JSON data for 2021-2025.

Parser history:
  The CIA changed their HTML format several times across 2000-2020.
  Year 2000 uses classic <b>FieldName:</b> format (parse_classic).
  Years 2001-2008 use table-based <td class="FieldLabel"> format (parse_table_format).
  Years 2009-2014 use CollapsiblePanel divs (parse_collapsiblepanel_format).
  Years 2015-2017 use expand/collapse h2 sections (parse_expandcollapse_format).
  Years 2018-2020 use modern field-anchor divs (parse_modern_format).
"""
import pyodbc
import json
import os
import sys
import re
import zipfile
import urllib.request
import urllib.error
from bs4 import BeautifulSoup

# ============================================================
# CONFIGURATION
# ============================================================
WORK_DIR = r"./work"
DB = "CIA_WorldFactbook"
CONN_STR = (
    "DRIVER={ODBC Driver 18 for SQL Server};"
    "SERVER=localhost;"
    f"DATABASE={DB};"
    "Trusted_Connection=yes;"
    "TrustServerCertificate=yes;"
)

# Known-good Wayback Machine timestamps for each year
WAYBACK_TIMESTAMPS = {
    2000: "20210115043153",
    2001: "20210115043222",
    2002: "20210115043238",
    2003: "20210115043307",
    2004: "20210115043330",
    2005: "20210115043355",
    2006: "20210115043418",
    2007: "20210115043445",
    2008: "20201028120645",
    2009: "20210115043527",
    2010: "20210115043556",
    2011: "20210115043622",
    2012: "20201028120347",
    2013: "20210115043720",
    2014: "20210115043803",
    2015: "20201028121353",
    2016: "20210115043915",
    2017: "20210115043959",
    2018: "20210115044100",
    2019: "20201028120752",
    2020: "20210115044405",
}

# ============================================================
# SQL SCHEMA
# ============================================================
def create_schema(conn):
    """Create the database schema with Year support"""
    cursor = conn.cursor()
    cursor.execute("""
    IF OBJECT_ID('CountryMedia', 'U') IS NOT NULL DROP TABLE CountryMedia;
    IF OBJECT_ID('CountryFields', 'U') IS NOT NULL DROP TABLE CountryFields;
    IF OBJECT_ID('CountryCategories', 'U') IS NOT NULL DROP TABLE CountryCategories;
    IF OBJECT_ID('Countries', 'U') IS NOT NULL DROP TABLE Countries;

    CREATE TABLE Countries (
        CountryID INT IDENTITY(1,1) PRIMARY KEY,
        Year INT NOT NULL,
        Code NVARCHAR(10) NOT NULL,
        Name NVARCHAR(200) NOT NULL,
        Source NVARCHAR(50) DEFAULT 'html'
    );

    CREATE TABLE CountryCategories (
        CategoryID INT IDENTITY(1,1) PRIMARY KEY,
        CountryID INT NOT NULL REFERENCES Countries(CountryID),
        CategoryTitle NVARCHAR(200)
    );

    CREATE TABLE CountryFields (
        FieldID INT IDENTITY(1,1) PRIMARY KEY,
        CategoryID INT NOT NULL REFERENCES CountryCategories(CategoryID),
        CountryID INT NOT NULL REFERENCES Countries(CountryID),
        FieldName NVARCHAR(200),
        Content NVARCHAR(MAX)
    );

    CREATE INDEX IX_Countries_Year ON Countries(Year);
    CREATE INDEX IX_Countries_Code ON Countries(Code);
    CREATE INDEX IX_Fields_Country ON CountryFields(CountryID);
    CREATE INDEX IX_Fields_Category ON CountryFields(CategoryID);
    CREATE INDEX IX_Categories_Country ON CountryCategories(CountryID);
    """)
    conn.commit()
    print("  Schema created.")

# ============================================================
# DOWNLOAD
# ============================================================
def is_valid_zip(path):
    """Check if a file is a valid zip"""
    try:
        with zipfile.ZipFile(path) as zf:
            return len(zf.namelist()) > 0
    except:
        return False

def cdx_lookup(year):
    """Use Wayback Machine CDX API to find a good timestamp for the zip"""
    target = f"www.cia.gov/the-world-factbook/about/archives/download/factbook-{year}.zip"
    cdx_url = f"https://web.archive.org/cdx/search/cdx?url={target}&output=json&fl=timestamp,statuscode,length&limit=10"
    try:
        req = urllib.request.Request(cdx_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
        # Skip header row, find entries with status 200 and large file size
        for row in data[1:]:
            ts, status, length = row
            if status == '200' and int(length) > 1000000:
                return ts
    except Exception as e:
        print(f"    CDX lookup failed: {e}")
    return None

def download_file(url, dest_path, label=""):
    """Download a file with chunked reads and retries"""
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=300) as resp:
        with open(dest_path, "wb") as f:
            while True:
                chunk = resp.read(1024 * 1024)
                if not chunk:
                    break
                f.write(chunk)
                mb = f.tell() // (1024 * 1024)
                print(f"    {label}{mb} MB...", end="\r")
    size_mb = os.path.getsize(dest_path) // (1024 * 1024)
    print(f"    {label}Downloaded: {size_mb} MB        ")

def download_zip(year):
    """Download a factbook zip from Wayback Machine"""
    os.makedirs(WORK_DIR, exist_ok=True)
    zip_path = os.path.join(WORK_DIR, f"factbook-{year}.zip")

    # Check if we already have a valid zip
    if os.path.exists(zip_path) and is_valid_zip(zip_path):
        print(f"  Already have valid {year} zip ({os.path.getsize(zip_path) // (1024*1024)} MB)")
        return zip_path

    # Try with known timestamp first
    timestamps_to_try = []
    ts = WAYBACK_TIMESTAMPS.get(year)
    if ts:
        timestamps_to_try.append(ts)

    for attempt, ts in enumerate(timestamps_to_try):
        url = f"https://web.archive.org/web/{ts}id_/https://www.cia.gov/the-world-factbook/about/archives/download/factbook-{year}.zip"
        print(f"  Downloading {year} (ts={ts})...")
        try:
            download_file(url, zip_path, f"[{year}] ")
            if is_valid_zip(zip_path):
                return zip_path
            else:
                print(f"    Invalid zip, trying CDX lookup...")
                os.remove(zip_path)
        except Exception as e:
            print(f"    Failed: {e}")
            if os.path.exists(zip_path):
                os.remove(zip_path)

    # Fallback: CDX lookup for alternative timestamp
    print(f"  Trying CDX lookup for {year}...")
    cdx_ts = cdx_lookup(year)
    if cdx_ts and cdx_ts not in timestamps_to_try:
        url = f"https://web.archive.org/web/{cdx_ts}id_/https://www.cia.gov/the-world-factbook/about/archives/download/factbook-{year}.zip"
        print(f"  Downloading {year} (CDX ts={cdx_ts})...")
        try:
            download_file(url, zip_path, f"[{year}] ")
            if is_valid_zip(zip_path):
                return zip_path
            else:
                print(f"    CDX download also invalid")
                os.remove(zip_path)
        except Exception as e:
            print(f"    CDX download failed: {e}")
            if os.path.exists(zip_path):
                os.remove(zip_path)

    # Last resort: try without id_ modifier
    ts = WAYBACK_TIMESTAMPS.get(year, cdx_ts or "20210115044000")
    url = f"https://web.archive.org/web/{ts}/https://www.cia.gov/the-world-factbook/about/archives/download/factbook-{year}.zip"
    print(f"  Last attempt for {year} (no id_ modifier)...")
    try:
        download_file(url, zip_path, f"[{year}] ")
        if is_valid_zip(zip_path):
            return zip_path
        else:
            os.remove(zip_path)
    except Exception as e:
        print(f"    Failed: {e}")
        if os.path.exists(zip_path):
            os.remove(zip_path)

    return None

# ============================================================
# HTML PARSING
# ============================================================
def _normalize_country_case(name):
    """Title-case names that are ALL CAPS (e.g. 'UNITED STATES' -> 'United States')."""
    if name and name == name.upper() and any(c.isalpha() for c in name):
        return name.title()
    return name

def get_country_name(soup, html):
    """Extract country name from page title.

    Title formats across years:
      2000-2005: "CIA -- The World Factbook 2000 -- Aruba"
      2006-2009: "CIA - The World Factbook"  (no country name in title!)
      2010-2012: "CIA - The World Factbook"  (same)
      2013-2015: "The World Factbook"        (no country name)
      2016-2017: "The World Factbook — Central Intelligence Agency"
      2018-2020: "North America :: United States — The World Factbook - CIA"
    """
    title = soup.find('title')
    if title:
        text = title.get_text()
        # Normalize em-dashes to regular dashes for consistent splitting
        text = text.replace('\u2014', ' - ').replace('\u2013', ' - ')

        # Common patterns - try splitting on separators
        for sep in ['--', '::', ' - ']:
            if sep in text:
                parts = [p.strip() for p in text.split(sep)]
                # Try each part (reverse order — country is usually last or second-to-last)
                for part in reversed(parts):
                    name = re.sub(r'The World Factbook.*', '', part).strip()
                    name = re.sub(r'Central Intelligence Agency', '', name).strip()
                    name = re.sub(r'^CIA$', '', name).strip()
                    # Strip trailing/leading dashes left by em-dash normalization
                    name = name.strip(' -')
                    if name and len(name) > 1 and name not in ('CIA', 'The World Factbook'):
                        return _normalize_country_case(name)

        # Fallback: just clean up the title
        name = re.sub(r'CIA|Central Intelligence Agency|The World Factbook|\d{4}|--|-|::', ' ', text).strip()
        name = re.sub(r'\s+', ' ', name).strip()
        if name and name not in ('CIA',):
            return _normalize_country_case(name)

    # Second fallback: countryName class (2013-2017)
    tag = soup.find(class_='countryName')
    if tag:
        candidate = tag.get_text().strip()
        if candidate and len(candidate) > 1:
            return _normalize_country_case(candidate)

    # Third fallback: look for country name in breadcrumb or heading
    # 2009-2017 have <span class="category">Geography::CountryName</span> or
    # <a class="tabHead">Geography ::CountryName</a>
    for tag in soup.find_all(['span', 'a'], class_=['category', 'tabHead']):
        tag_text = tag.get_text()
        if '::' in tag_text:
            parts = tag_text.split('::')
            candidate = parts[-1].strip()
            if candidate and len(candidate) > 1:
                return _normalize_country_case(candidate)

    # Fourth fallback: h2 with sectiontitle attribute (2015-2017)
    h2 = soup.find('h2', attrs={'sectiontitle': True})
    if h2:
        text = h2.get_text()
        if '::' in text:
            candidate = text.split('::')[-1].strip()
            if candidate and len(candidate) > 1:
                return _normalize_country_case(candidate)

    return "Unknown"

def parse_classic(soup, html):
    """Parse 2000-2007 format HTML"""
    categories = []
    current_cat = None
    current_fields = []

    # In classic format, sections are marked by <a name="Intro">, <a name="Geo">, etc.
    # Fields are marked by <b>FieldName:</b>
    section_map = {
        'Intro': 'Introduction',
        'Geo': 'Geography',
        'People': 'People',
        'Govt': 'Government',
        'Econ': 'Economy',
        'Comm': 'Communications',
        'Trans': 'Transportation',
        'Military': 'Military',
        'Issues': 'Transnational Issues',
    }

    # Get all text, processing element by element
    body = soup.find('body')
    if not body:
        return categories

    # Strategy: walk through all elements, track sections and fields
    text = str(body)

    # Split by section anchors
    section_pattern = r'<a\s+name="([^"]+)"[^>]*>([^<]*)</a>'
    section_matches = list(re.finditer(section_pattern, text, re.IGNORECASE))

    for i, match in enumerate(section_matches):
        section_id = match.group(1)
        section_name = match.group(2).strip() or section_map.get(section_id, section_id)

        # Get text between this section and the next
        start = match.end()
        end = section_matches[i + 1].start() if i + 1 < len(section_matches) else len(text)
        section_html = text[start:end]

        # Find fields within section: <b>FieldName:</b> or <b>Field Name:</b>
        field_pattern = r'<b>([^<]+?):</b>\s*(.*?)(?=<b>[^<]+?:</b>|<p><center><table|$)'
        field_matches = list(re.finditer(field_pattern, section_html, re.DOTALL | re.IGNORECASE))

        fields = []
        for fm in field_matches:
            fname = fm.group(1).strip()
            fcontent = fm.group(2).strip()
            # Strip HTML from content
            clean = re.sub(r'<[^>]+>', ' ', fcontent)
            clean = re.sub(r'&[a-zA-Z]+;', ' ', clean)
            clean = re.sub(r'\s+', ' ', clean).strip()
            if clean and fname:
                fields.append((fname, clean))

        if fields:
            categories.append((section_name, fields))

    # If no structured parsing worked, get full text
    if not categories:
        full_text = soup.get_text(separator='\n')
        full_text = re.sub(r'\n\s*\n', '\n', full_text).strip()
        if full_text:
            categories.append(('Full Content', [('Text', full_text[:100000])]))

    return categories

def parse_table_format(soup, html):
    """Parse 2001-2008 table-based HTML.

    Structure:
      Section headers: <a name="Geo">Geography</a>
      Fields: <td class="FieldLabel"><div align="right">FieldName:</div></td>
              <td>content</td>
    """
    categories = []

    section_map = {
        'Intro': 'Introduction', 'Introduction': 'Introduction',
        'Geo': 'Geography', 'Geography': 'Geography',
        'People': 'People', 'People and Society': 'People and Society',
        'Govt': 'Government', 'Government': 'Government',
        'Econ': 'Economy', 'Economy': 'Economy',
        'Comm': 'Communications', 'Communications': 'Communications',
        'Trans': 'Transportation', 'Transportation': 'Transportation',
        'Military': 'Military',
        'Issues': 'Transnational Issues', 'Transnational Issues': 'Transnational Issues',
    }

    body = soup.find('body')
    if not body:
        return categories

    text = str(body)

    section_pattern = r'<a\s+name="([^"]+)"[^>]*>([^<]*)</a>'
    section_matches = list(re.finditer(section_pattern, text, re.IGNORECASE))
    section_matches = [m for m in section_matches if m.group(1) in section_map]

    for i, match in enumerate(section_matches):
        section_id = match.group(1)
        section_name = section_map.get(section_id, section_id)

        start = match.end()
        end = section_matches[i + 1].start() if i + 1 < len(section_matches) else len(text)
        section_html = text[start:end]

        section_soup = BeautifulSoup(section_html, 'html.parser')
        field_labels = section_soup.find_all('td', class_='FieldLabel')

        fields = []
        for label_td in field_labels:
            fname = label_td.get_text(strip=True).rstrip(':').strip()
            if not fname:
                continue

            content_td = label_td.find_next_sibling('td')
            if content_td:
                for img_link in content_td.find_all('a'):
                    if img_link.find('img'):
                        img_link.decompose()
                content = content_td.get_text(separator=' ', strip=True)
                content = re.sub(r'\s+', ' ', content).strip()
            else:
                content = ""

            if fname and content:
                fields.append((fname, content))

        if fields:
            categories.append((section_name, fields))

    # Fallback: if no sections found, try finding FieldLabel anywhere
    if not categories:
        all_labels = soup.find_all('td', class_='FieldLabel')
        if all_labels:
            fields = []
            for label_td in all_labels:
                fname = label_td.get_text(strip=True).rstrip(':').strip()
                content_td = label_td.find_next_sibling('td')
                if content_td and fname:
                    for img_link in content_td.find_all('a'):
                        if img_link.find('img'):
                            img_link.decompose()
                    content = content_td.get_text(separator=' ', strip=True)
                    content = re.sub(r'\s+', ' ', content).strip()
                    if content:
                        fields.append((fname, content))
            if fields:
                categories.append(('General', fields))

    if not categories:
        full_text = soup.get_text(separator='\n')
        full_text = re.sub(r'\n\s*\n', '\n', full_text).strip()
        if full_text:
            categories.append(('Full Content', [('Text', full_text[:100000])]))

    return categories


def parse_collapsiblepanel_format(soup, html):
    """Parse 2009-2014 CollapsiblePanel HTML.

    Structure:
      Sections: <div class="CollapsiblePanel" id="CollapsiblePanel1_Geo">
                  Tab: <span class="category">Geography::Country</span>
                  Content: table with class CollapsiblePanelContent
      Field rows: <tr class="na_light"> or <tr class="noa_light">
                  containing <div class="category"><a>FieldName</a></div>
      Data rows:  following <tr> with <div class="category_data">value</div>
    """
    categories = []

    panels = soup.find_all('div', class_='CollapsiblePanel')

    for panel in panels:
        tab = panel.find('td', class_='CollapsiblePanelTab')
        if tab:
            cat_span = tab.find('span', class_='category')
            section_name = cat_span.get_text(strip=True) if cat_span else ''
        else:
            h2 = panel.find('h2', class_='question')
            section_name = h2.get('sectiontitle', h2.get_text(strip=True)) if h2 else ''

        if '::' in section_name:
            section_name = section_name.split('::')[0].strip()
        if not section_name:
            continue

        content_table = panel.find('table', class_='CollapsiblePanelContent')
        if not content_table:
            answer_div = panel.find('div', class_='answer')
            if answer_div:
                content_table = answer_div.find('table')
        if not content_table:
            continue

        field_rows = content_table.find_all('tr', class_=re.compile(r'_light$'))

        fields = []
        for fr in field_rows:
            cat_div = fr.find('div', class_='category')
            if cat_div:
                link = cat_div.find('a')
                fname = link.get_text(strip=True) if link else cat_div.get_text(strip=True)
            else:
                fname = fr.get_text(strip=True)
            fname = fname.rstrip(':').strip()
            if not fname:
                continue

            content_parts = []
            next_tr = fr.find_next_sibling('tr')
            while next_tr:
                tr_classes = next_tr.get('class', []) or []
                if any(c.endswith('_light') for c in tr_classes if isinstance(c, str)):
                    break

                data_divs = next_tr.find_all('div', class_='category_data')
                data_spans = next_tr.find_all('span', class_='category_data')

                if data_divs or data_spans:
                    td = next_tr.find('td')
                    if not td:
                        td = next_tr
                    for child in td.children:
                        if not hasattr(child, 'name') or not child.name:
                            continue
                        child_classes = child.get('class', []) or []
                        if child.name == 'div' and 'category' in child_classes and 'category_data' not in child_classes:
                            label_text = ''
                            for part in child.children:
                                if isinstance(part, str):
                                    label_text += part
                                elif hasattr(part, 'name') and part.name == 'em':
                                    label_text += part.get_text()
                            label_text = label_text.strip()
                            if label_text:
                                content_parts.append(label_text)
                            inner_data = child.find('span', class_='category_data')
                            if inner_data:
                                val = inner_data.get_text(strip=True)
                                if val:
                                    content_parts.append(val)
                        elif child.name == 'div' and 'category_data' in child_classes:
                            val = child.get_text(strip=True)
                            if val:
                                content_parts.append(val)
                        elif child.name == 'span' and 'category' in child_classes and 'category_data' not in child_classes:
                            label = child.get_text(strip=True)
                            if label:
                                content_parts.append(label)
                        elif child.name == 'span' and 'category_data' in child_classes:
                            val = child.get_text(strip=True)
                            if val:
                                content_parts.append(val)

                next_tr = next_tr.find_next_sibling('tr')

            content = ' '.join(content_parts)
            content = re.sub(r'\s+', ' ', content).strip()
            if fname and content:
                fields.append((fname, content))

        if fields:
            categories.append((section_name, fields))

    if not categories:
        full_text = soup.get_text(separator='\n')
        full_text = re.sub(r'\n\s*\n', '\n', full_text).strip()
        if full_text:
            categories.append(('Full Content', [('Text', full_text[:100000])]))

    return categories

def parse_expandcollapse_format(soup, html):
    """Parse 2015-2017 expand/collapse HTML.

    Structure:
      Sections: <h2 class='question' sectiontitle='Geography'>Geography :: COUNTRY</h2>
      Fields:   <div id='field' class='category noa_light'>
                  <a href='...'>FieldName:</a>
                </div>
      Values:   <div class=category_data>value</div>
    """
    categories = []

    section_headers = soup.find_all('h2', class_='question')
    if not section_headers:
        section_headers = soup.find_all('h2', attrs={'sectiontitle': True})

    for sh_idx, sh in enumerate(section_headers):
        section_title = sh.get('sectiontitle', '')
        if not section_title:
            text = sh.get_text(strip=True)
            if '::' in text:
                section_title = text.split('::')[0].strip()
            else:
                section_title = text
        if not section_title:
            continue

        fields = []
        current = sh

        while True:
            current = current.find_next()
            if current is None:
                break
            if current.name == 'h2' and ('question' in current.get('class', [])
                                          or current.get('sectiontitle')):
                break

            classes = current.get('class', [])
            if (current.name == 'div' and current.get('id') == 'field'
                    and 'category' in classes):
                link = current.find('a')
                if link:
                    fname = link.get_text(strip=True).rstrip(':').strip()
                else:
                    fname = current.get_text(strip=True).rstrip(':').strip()
                if not fname:
                    continue

                content_parts = []
                content_el = current.find_next_sibling()

                while content_el:
                    el_classes = content_el.get('class', [])
                    if (content_el.name == 'div' and content_el.get('id') == 'field'
                            and 'category' in el_classes):
                        break
                    if content_el.name == 'li' and content_el.find('h2', class_='question'):
                        break
                    if content_el.name == 'h2' and 'question' in el_classes:
                        break

                    if 'category_data' in el_classes:
                        text = content_el.get_text(strip=True)
                        if text:
                            content_parts.append(text)
                    elif content_el.name == 'div':
                        sub_cat = content_el.find('span', class_='category')
                        sub_data = content_el.find('span', class_='category_data')
                        if sub_cat and sub_data:
                            label = sub_cat.get_text(strip=True)
                            value = sub_data.get_text(strip=True)
                            if label and value:
                                content_parts.append(f"{label} {value}")
                            elif value:
                                content_parts.append(value)
                        elif 'category_data' in el_classes:
                            text = content_el.get_text(strip=True)
                            if text:
                                content_parts.append(text)
                        else:
                            nested = content_el.find(class_='category_data')
                            if nested:
                                text = nested.get_text(strip=True)
                                if text:
                                    content_parts.append(text)

                    content_el = content_el.find_next_sibling()

                content = ' | '.join(content_parts) if content_parts else ''
                if content and fname:
                    fields.append((fname, content))

        if fields:
            categories.append((section_title, fields))

    if not categories:
        field_divs = soup.find_all('div', id='field', class_='category')
        if field_divs:
            fields = []
            for fd in field_divs:
                link = fd.find('a')
                fname = link.get_text(strip=True).rstrip(':').strip() if link else ''
                if not fname:
                    continue
                next_div = fd.find_next_sibling('div')
                if next_div:
                    content = next_div.get_text(strip=True)
                    if content:
                        fields.append((fname, content))
            if fields:
                categories.append(('General', fields))

    if not categories:
        full_text = soup.get_text(separator='\n')
        full_text = re.sub(r'\n\s*\n', '\n', full_text).strip()
        if full_text:
            categories.append(('Full Content', [('Text', full_text[:100000])]))

    return categories


def parse_modern_format(soup, html):
    """Parse 2018-2020 modern HTML.

    Structure:
      Category anchors: <li id="geography-category-section-anchor">
                          <a class="tabHead">Geography ::Albania</a>
      Field anchors:    <div class="category eur_light" id="field-anchor-geography-location">
                          <a>Location</a>
      Field data:       <div id="field-location">
                          <div class="category_data subfield text">value</div>
    """
    categories = []

    cat_anchors = soup.find_all(id=re.compile(r'-category-section-anchor$'))

    for i, ca in enumerate(cat_anchors):
        cat_id = ca.get('id', '')
        cat_name = cat_id.replace('-category-section-anchor', '').replace('-', ' ').title()

        tab_head = ca.find('a', class_='tabHead')
        if tab_head:
            text = tab_head.get_text(strip=True)
            if '::' in text:
                cat_name = text.split('::')[0].strip()

        next_anchor = cat_anchors[i + 1] if i + 1 < len(cat_anchors) else None

        fields = []
        current = ca
        while True:
            current = current.find_next(id=re.compile(r'^field-(?!anchor)'))
            if current is None:
                break
            if next_anchor and current.find_previous(id=re.compile(r'-category-section-anchor$')) != ca:
                break

            field_id = current.get('id', '')
            field_name = field_id.replace('field-', '').replace('-', ' ').title()

            anchor_div = current.find_previous(id=re.compile(r'^field-anchor-'))
            if anchor_div:
                link = anchor_div.find('a')
                if link:
                    fname = link.get_text(strip=True).rstrip(':').strip()
                    if fname:
                        field_name = fname

            data_divs = current.find_all(class_=re.compile(r'category_data'))
            content_parts = []
            for dd in data_divs:
                # Skip bare ranking divs (class=category_data only, contains rank link)
                classes = dd.get('class', [])
                if 'subfield' not in classes and dd.find('a', href=re.compile(r'rank\.html')):
                    continue
                # Use full text of the div — captures spans AND loose text nodes
                text = ' '.join(dd.get_text(separator=' ').split())
                if text:
                    content_parts.append(text)

            content = ' | '.join(content_parts) if content_parts else ''
            if not content:
                content = current.get_text(strip=True)

            if content and field_name:
                fields.append((field_name, content))

        if fields:
            categories.append((cat_name, fields))

    if not categories:
        full_text = soup.get_text(separator='\n')
        full_text = re.sub(r'\n\s*\n', '\n', full_text).strip()
        if full_text:
            categories.append(('Full Content', [('Text', full_text[:100000])]))

    return categories


# Year-to-parser mapping (determined by CIA HTML format changes)
YEAR_PARSERS = {
    2000: 'classic',           # <b>FieldName:</b> format
    2001: 'table',             # <td class="FieldLabel"> format
    2002: 'table',
    2003: 'table',
    2004: 'table',
    2005: 'table',
    2006: 'table',
    2007: 'table',
    2008: 'table',
    2009: 'collapsiblepanel',  # CollapsiblePanel divs
    2010: 'collapsiblepanel',
    2011: 'collapsiblepanel',
    2012: 'collapsiblepanel',
    2013: 'collapsiblepanel',
    2014: 'collapsiblepanel',
    2015: 'expandcollapse',    # h2.question expand/collapse
    2016: 'expandcollapse',
    2017: 'expandcollapse',
    2018: 'modern',            # field-anchor divs
    2019: 'modern',
    2020: 'modern',
}


def parse_country_html(html, year=2000):
    """Parse a country HTML page using the correct parser for that year."""
    soup = BeautifulSoup(html, 'html.parser')
    name = get_country_name(soup, html)

    parser_type = YEAR_PARSERS.get(year, 'classic')

    if parser_type == 'table':
        categories = parse_table_format(soup, html)
    elif parser_type == 'collapsiblepanel':
        categories = parse_collapsiblepanel_format(soup, html)
    elif parser_type == 'expandcollapse':
        categories = parse_expandcollapse_format(soup, html)
    elif parser_type == 'modern':
        categories = parse_modern_format(soup, html)
    else:
        categories = parse_classic(soup, html)

    return name, categories

# ============================================================
# PROCESS ZIP FILE
# ============================================================
def process_zip(zip_path, year, cursor, conn):
    """Parse all country files from a zip and insert into SQL"""
    success = 0
    failed = 0

    with zipfile.ZipFile(zip_path) as zf:
        # Find country HTML files
        all_files = zf.namelist()
        geos = sorted([f for f in all_files if '/geos/' in f and f.endswith('.html')])

        # Filter out templates, print pages, and non-country files
        # Country codes are 2-3 chars (like "us", "uk", "xq")
        seen_codes = set()
        unique_geos = []
        skip_patterns = ['template', 'print', 'summary', 'notes', 'appendix', 'index', 'wfb']
        for g in geos:
            basename = os.path.basename(g)
            code = os.path.splitext(basename)[0].lower()
            # Skip if code is too long (templates like "countrytemplate_us")
            if len(code) > 5:
                continue
            # Skip known non-country patterns
            if any(p in code for p in skip_patterns):
                continue
            if code not in seen_codes:
                seen_codes.add(code)
                unique_geos.append(g)

        print(f"  {len(unique_geos)} countries in {year} zip")

        for gf in unique_geos:
            try:
                code = os.path.splitext(os.path.basename(gf))[0].lower()
                html = zf.read(gf).decode('utf-8', errors='replace')

                name, categories = parse_country_html(html, year)

                # Insert country
                cursor.execute(
                    "INSERT INTO Countries (Year, Code, Name, Source) OUTPUT INSERTED.CountryID VALUES (?, ?, ?, ?)",
                    year, code, name, 'html'
                )
                country_id = cursor.fetchone()[0]

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
                print(f"    ERROR [{code}]: {e}")
                failed += 1

    return success, failed

# ============================================================
# MAIN
# ============================================================
def main():
    os.makedirs(WORK_DIR, exist_ok=True)

    # Connect to SQL Server
    print("=== Connecting to SQL Server ===")
    conn = pyodbc.connect(CONN_STR)
    cursor = conn.cursor()
    print("  Connected.")

    # Create schema
    print("\n=== Creating schema ===")
    create_schema(conn)

    # Process each year
    total_countries = 0
    total_fields = 0

    failed_years = []
    for year in range(2000, 2021):
        print(f"\n{'='*50}")
        print(f"=== Year {year} ===")
        print(f"{'='*50}")

        try:
            # Download
            zip_path = download_zip(year)
            if not zip_path:
                print(f"  FAILED to download {year}, skipping")
                failed_years.append(year)
                continue

            # Parse and load
            print(f"  Parsing and loading...")
            success, failed = process_zip(zip_path, year, cursor, conn)
            print(f"  Loaded: {success} countries, Failed: {failed}")
            total_countries += success

            # Delete zip to save space
            try:
                os.remove(zip_path)
                print(f"  Deleted zip ({os.path.basename(zip_path)})")
            except:
                pass

        except Exception as e:
            print(f"  CRITICAL ERROR for {year}: {e}")
            failed_years.append(year)
            try:
                conn.rollback()
            except:
                pass
            # Reconnect if needed
            try:
                cursor.execute("SELECT 1")
            except:
                print("  Reconnecting to SQL Server...")
                conn = pyodbc.connect(CONN_STR)
                cursor = conn.cursor()

    if failed_years:
        print(f"\n  Failed years: {failed_years}")

    # Summary
    print(f"\n{'='*50}")
    print(f"=== FINAL SUMMARY ===")
    print(f"{'='*50}")

    cursor.execute("SELECT Year, COUNT(*) FROM Countries GROUP BY Year ORDER BY Year")
    for row in cursor.fetchall():
        print(f"  {row[0]}: {row[1]} countries")

    cursor.execute("SELECT COUNT(*) FROM Countries")
    print(f"\n  Total Countries: {cursor.fetchone()[0]}")
    cursor.execute("SELECT COUNT(*) FROM CountryCategories")
    print(f"  Total Categories: {cursor.fetchone()[0]}")
    cursor.execute("SELECT COUNT(*) FROM CountryFields")
    total_fields = cursor.fetchone()[0]
    print(f"  Total Fields: {total_fields}")

    conn.close()

    # Cleanup work dir
    try:
        os.rmdir(WORK_DIR)
    except:
        pass

    print("\nDone!")

if __name__ == '__main__':
    main()
