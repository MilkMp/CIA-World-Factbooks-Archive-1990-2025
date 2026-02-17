"""
CIA Factbook Archive - Repair Broken Years
===========================================
Deletes bad data for years where HTML parsing failed, re-downloads the
zips, and re-parses with fixed parsers.

Broken years:
  2001-2008: parse_classic fell back to "Full Content" (table-based HTML)
  2015-2017: parse_mid over-parsed or mis-categorized (expand/collapse HTML)

Run:
  python repair_broken_years.py                  # Repair all broken years
  python repair_broken_years.py --year 2003      # Repair single year
  python repair_broken_years.py --dry-run        # Show what would be done
  python repair_broken_years.py --keep-zips      # Don't delete zips after
"""
import pyodbc
import sys
import os
import re
import zipfile
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_archive as ba

CONN_STR = (
    "DRIVER={ODBC Driver 18 for SQL Server};"
    "SERVER=localhost;"
    "DATABASE=CIA_WorldFactbook;"
    "Trusted_Connection=yes;"
    "TrustServerCertificate=yes;"
)

BROKEN_YEARS = {
    2001: 'table',
    2002: 'table',
    2003: 'table',
    2004: 'table',
    2005: 'table',
    2006: 'table',
    2007: 'table',
    2008: 'table',
    2009: 'collapsiblepanel',
    2010: 'collapsiblepanel',
    2011: 'collapsiblepanel',
    2012: 'collapsiblepanel',
    2013: 'collapsiblepanel',
    2014: 'collapsiblepanel',
    2015: 'expandcollapse',
    2016: 'expandcollapse',
    2017: 'expandcollapse',
    2018: 'modern',
    2019: 'modern',
    2020: 'modern',
}


# ============================================================
# FIXED PARSERS
# ============================================================

def parse_table_format(soup, html):
    """
    Fixed parser for 2001-2008 HTML.

    Structure:
      Section headers: <a name="Geo">Geography</a> (same as 2000)
      Fields: <td class="FieldLabel"><div align="right">FieldName:</div></td>
              <td>content</td>
      Each field is a <tr> in a <table> within the section.
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

    # Find section anchors (same as classic parser)
    section_pattern = r'<a\s+name="([^"]+)"[^>]*>([^<]*)</a>'
    section_matches = list(re.finditer(section_pattern, text, re.IGNORECASE))

    # Filter to known sections only
    section_matches = [m for m in section_matches if m.group(1) in section_map]

    for i, match in enumerate(section_matches):
        section_id = match.group(1)
        section_name = section_map.get(section_id, section_id)

        # Get HTML between this section and the next
        start = match.end()
        end = section_matches[i + 1].start() if i + 1 < len(section_matches) else len(text)
        section_html = text[start:end]

        # Parse with BeautifulSoup to find FieldLabel elements
        section_soup = BeautifulSoup(section_html, 'html.parser')
        field_labels = section_soup.find_all('td', class_='FieldLabel')

        fields = []
        for label_td in field_labels:
            # Get field name from the label cell
            fname = label_td.get_text(strip=True).rstrip(':').strip()
            if not fname:
                continue

            # Get content from the next <td> sibling
            content_td = label_td.find_next_sibling('td')
            if content_td:
                # Remove icon links (definition, field listing) before getting text
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

    # Last resort fallback
    if not categories:
        full_text = soup.get_text(separator='\n')
        full_text = re.sub(r'\n\s*\n', '\n', full_text).strip()
        if full_text:
            categories.append(('Full Content', [('Text', full_text[:100000])]))

    return categories


def parse_expandcollapse_format(soup, html):
    """
    Fixed parser for 2015-2017 HTML.

    Structure:
      Sections: <h2 class='question' sectiontitle='Geography'>Geography :: COUNTRY</h2>
      Fields:   <div id='field' class='category noa_light'>
                  <a href='...'>FieldName:</a>
                </div>
      Values:   <div class=category_data>value</div>  (immediately after field div)
      Sub-fields: <span class=category>label</span>
                  <span class=category_data>value</span>
    """
    categories = []

    # Find all section headers
    section_headers = soup.find_all('h2', class_='question')

    if not section_headers:
        # Try alternative: look for sectiontitle attribute on any h2
        section_headers = soup.find_all('h2', attrs={'sectiontitle': True})

    for sh_idx, sh in enumerate(section_headers):
        section_title = sh.get('sectiontitle', '')
        if not section_title:
            # Try parsing from text: "Geography :: UNITED STATES"
            text = sh.get_text(strip=True)
            if '::' in text:
                section_title = text.split('::')[0].strip()
            else:
                section_title = text
        if not section_title:
            continue

        # Find all field divs between this section header and the next
        # Field divs have id='field' and class contains 'category' and 'noa_light'
        fields = []
        current = sh

        # Walk through siblings/following elements until next section header
        while True:
            current = current.find_next()
            if current is None:
                break
            # Stop at the next section header
            if current.name == 'h2' and ('question' in current.get('class', [])
                                          or current.get('sectiontitle')):
                break

            # Check if this is a field container
            classes = current.get('class', [])
            if (current.name == 'div' and current.get('id') == 'field'
                    and 'category' in classes):
                # Extract field name from the <a> tag inside
                link = current.find('a')
                if link:
                    fname = link.get_text(strip=True).rstrip(':').strip()
                else:
                    fname = current.get_text(strip=True).rstrip(':').strip()
                if not fname:
                    continue

                # Collect all content until the next field div or section header
                content_parts = []
                content_el = current.find_next_sibling()

                while content_el:
                    # Stop if we hit another field div
                    el_classes = content_el.get('class', [])
                    if (content_el.name == 'div' and content_el.get('id') == 'field'
                            and 'category' in el_classes):
                        break
                    # Stop if we hit a section header (li > h2)
                    if content_el.name == 'li' and content_el.find('h2', class_='question'):
                        break
                    if content_el.name == 'h2' and 'question' in el_classes:
                        break

                    # Check for category_data div (main value)
                    if 'category_data' in el_classes:
                        text = content_el.get_text(strip=True)
                        if text:
                            content_parts.append(text)
                    # Check for sub-field divs containing span pairs
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
                            # Check for nested category_data
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

    # Fallback if no section headers found
    if not categories:
        # Try finding field divs directly
        field_divs = soup.find_all('div', id='field', class_='category')
        if field_divs:
            fields = []
            for fd in field_divs:
                link = fd.find('a')
                fname = link.get_text(strip=True).rstrip(':').strip() if link else ''
                if not fname:
                    continue
                # Get next sibling category_data
                next_div = fd.find_next_sibling('div')
                if next_div:
                    content = next_div.get_text(strip=True)
                    if content:
                        fields.append((fname, content))
            if fields:
                categories.append(('General', fields))

    # Last resort
    if not categories:
        full_text = soup.get_text(separator='\n')
        full_text = re.sub(r'\n\s*\n', '\n', full_text).strip()
        if full_text:
            categories.append(('Full Content', [('Text', full_text[:100000])]))

    return categories


def parse_collapsiblepanel_format(soup, html):
    """
    Fixed parser for 2009-2014 HTML.

    Structure:
      Sections: <div class="CollapsiblePanel" id="CollapsiblePanel1_Geo">
                  Tab: <span class="category">Geography::Country</span>
                  Content: table (class="CollapsiblePanelContent" in 2009-2012,
                           or first table inside div.answer in 2013-2014)
      Field rows: <tr class="na_light"> (2009-2010) or <tr class="noa_light"> (2011-2014)
                  containing <div class="category"><a>FieldName</a></div>
      Data rows:  following <tr> with <div class="category_data">value</div>
                  and inline <span class="category">label</span> (e.g. "country comparison")

    The original parse_mid() broke because it treated ALL <span class="category">
    elements as section headers, including ~50+ inline "country comparison to the world:"
    labels per country.
    """
    categories = []

    panels = soup.find_all('div', class_='CollapsiblePanel')

    for panel in panels:
        # Get section name from the tab
        tab = panel.find('td', class_='CollapsiblePanelTab')
        if tab:
            cat_span = tab.find('span', class_='category')
            section_name = cat_span.get_text(strip=True) if cat_span else ''
        else:
            # 2013-2014: section name in h2.question
            h2 = panel.find('h2', class_='question')
            section_name = h2.get('sectiontitle', h2.get_text(strip=True)) if h2 else ''

        # Strip "::CountryName" suffix
        if '::' in section_name:
            section_name = section_name.split('::')[0].strip()
        if not section_name:
            continue

        # Find the content table
        content_table = panel.find('table', class_='CollapsiblePanelContent')
        if not content_table:
            # 2013-2014: content is in div.answer > ... > table
            answer_div = panel.find('div', class_='answer')
            if answer_div:
                content_table = answer_div.find('table')
        if not content_table:
            continue

        # Find field rows — class name varies by region and year:
        #   2009-2010: af_light, eu_light, ca_light, na_light, etc. (region-based)
        #   2011-2014: noa_light (uniform)
        field_rows = content_table.find_all('tr', class_=re.compile(r'_light$'))

        fields = []
        for fr in field_rows:
            # Get field name from div.category > a
            cat_div = fr.find('div', class_='category')
            if cat_div:
                link = cat_div.find('a')
                fname = link.get_text(strip=True) if link else cat_div.get_text(strip=True)
            else:
                fname = fr.get_text(strip=True)
            fname = fname.rstrip(':').strip()
            if not fname:
                continue

            # Collect data from subsequent non-field rows
            content_parts = []
            next_tr = fr.find_next_sibling('tr')
            while next_tr:
                tr_classes = next_tr.get('class', []) or []
                if any(c.endswith('_light') for c in tr_classes if isinstance(c, str)):
                    break  # Hit next field

                # Extract category_data divs and span pairs
                data_divs = next_tr.find_all('div', class_='category_data')
                data_spans = next_tr.find_all('span', class_='category_data')

                if data_divs or data_spans:
                    # Walk direct children of the <td> to build content
                    td = next_tr.find('td')
                    if not td:
                        td = next_tr
                    for child in td.children:
                        if not hasattr(child, 'name') or not child.name:
                            continue
                        child_classes = child.get('class', []) or []
                        if child.name == 'div' and 'category' in child_classes and 'category_data' not in child_classes:
                            # Sub-label div like "total:" — extract label text only
                            # (exclude nested span.category_data to avoid duplication)
                            label_text = ''
                            for part in child.children:
                                if isinstance(part, str):
                                    label_text += part
                                elif hasattr(part, 'name') and part.name == 'em':
                                    label_text += part.get_text()
                            label_text = label_text.strip()
                            if label_text:
                                content_parts.append(label_text)
                            # Then get the value from span.category_data inside
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
                            # "country comparison to the world:" — include as context
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

    # Fallback
    if not categories:
        full_text = soup.get_text(separator='\n')
        full_text = re.sub(r'\n\s*\n', '\n', full_text).strip()
        if full_text:
            categories.append(('Full Content', [('Text', full_text[:100000])]))

    return categories


def parse_modern_format(soup, html):
    """
    Fixed parser for 2018-2020 HTML.

    Structure:
      Category anchors: <li id="geography-category-section-anchor">
                          <a class="tabHead">Geography ::Albania</a>
      Field anchors:    <div class="category eur_light" id="field-anchor-geography-location">
                          <a>Location</a>
      Field data:       <div id="field-location">
                          <div class="category_data subfield text">value</div>

    The original parse_modern() had two bugs:
    1. Named all categories as the country name instead of Geography, Economy, etc.
    2. Never stopped at section boundaries — each category accumulated ALL subsequent fields.
    """
    categories = []

    cat_anchors = soup.find_all(id=re.compile(r'-category-section-anchor$'))

    for i, ca in enumerate(cat_anchors):
        # Get category name from the id or tabHead link
        cat_id = ca.get('id', '')
        cat_name = cat_id.replace('-category-section-anchor', '').replace('-', ' ').title()

        tab_head = ca.find('a', class_='tabHead')
        if tab_head:
            text = tab_head.get_text(strip=True)
            if '::' in text:
                cat_name = text.split('::')[0].strip()

        # Find all field-* data divs (not field-anchor-*) scoped to this section
        next_anchor = cat_anchors[i + 1] if i + 1 < len(cat_anchors) else None

        fields = []
        current = ca
        while True:
            current = current.find_next(id=re.compile(r'^field-(?!anchor)'))
            if current is None:
                break
            # Stop if we've passed into the next category section
            if next_anchor and current.find_previous(id=re.compile(r'-category-section-anchor$')) != ca:
                break

            field_id = current.get('id', '')
            field_name = field_id.replace('field-', '').replace('-', ' ').title()

            # Try to get proper field name from the preceding anchor div
            anchor_div = current.find_previous(id=re.compile(r'^field-anchor-'))
            if anchor_div:
                link = anchor_div.find('a')
                if link:
                    fname = link.get_text(strip=True).rstrip(':').strip()
                    if fname:
                        field_name = fname

            # Extract content from category_data divs
            data_divs = current.find_all(class_=re.compile(r'category_data'))
            content_parts = []
            for dd in data_divs:
                subfield_name = dd.find(class_='subfield-name')
                subfield_num = dd.find(class_='subfield-number')
                subfield_note = dd.find(class_='subfield-note')

                parts = []
                if subfield_name:
                    parts.append(subfield_name.get_text(strip=True))
                if subfield_num:
                    parts.append(subfield_num.get_text(strip=True))
                if subfield_note:
                    parts.append(subfield_note.get_text(strip=True))

                if parts:
                    content_parts.append(' '.join(parts))
                else:
                    text = dd.get_text(strip=True)
                    if text:
                        content_parts.append(text)

            content = ' | '.join(content_parts) if content_parts else ''
            if not content:
                content = current.get_text(strip=True)

            if content and field_name:
                fields.append((field_name, content))

        if fields:
            categories.append((cat_name, fields))

    # Fallback
    if not categories:
        full_text = soup.get_text(separator='\n')
        full_text = re.sub(r'\n\s*\n', '\n', full_text).strip()
        if full_text:
            categories.append(('Full Content', [('Text', full_text[:100000])]))

    return categories


def parse_country_fixed(html, fix_type):
    """Parse a country HTML page using the appropriate fixed parser."""
    soup = BeautifulSoup(html, 'html.parser')
    name = ba.get_country_name(soup, html)

    if fix_type == 'table':
        categories = parse_table_format(soup, html)
    elif fix_type == 'expandcollapse':
        categories = parse_expandcollapse_format(soup, html)
    elif fix_type == 'collapsiblepanel':
        categories = parse_collapsiblepanel_format(soup, html)
    elif fix_type == 'modern':
        categories = parse_modern_format(soup, html)
    else:
        # Fallback to original parser
        _, categories = ba.parse_country_html(html)

    return name, categories


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
    return {row[0].upper(): row[1] for row in cursor.fetchall()}


def delete_year_data(cursor, conn, year):
    """Delete all data for a year, respecting FK constraints."""
    cursor.execute("SELECT CountryID FROM Countries WHERE Year = ?", year)
    country_ids = [row[0] for row in cursor.fetchall()]

    if not country_ids:
        print(f"    No data to delete for {year}")
        return 0

    # Batch delete in chunks
    chunk_size = 50
    for i in range(0, len(country_ids), chunk_size):
        chunk = country_ids[i:i + chunk_size]
        placeholders = ','.join(['?'] * len(chunk))

        # 1. CountryFields
        cursor.execute(f"DELETE FROM CountryFields WHERE CountryID IN ({placeholders})", chunk)
        # 2. CountryCategories
        cursor.execute(f"DELETE FROM CountryCategories WHERE CountryID IN ({placeholders})", chunk)
        # 3. Countries
        cursor.execute(f"DELETE FROM Countries WHERE CountryID IN ({placeholders})", chunk)

        conn.commit()

    print(f"    Deleted {len(country_ids)} countries and all associated data")
    return len(country_ids)


def get_country_files(zf):
    """Extract list of country HTML files from a zip (same logic as process_zip)."""
    all_files = zf.namelist()
    geos = sorted([f for f in all_files if '/geos/' in f and f.endswith('.html')])

    seen_codes = set()
    unique_geos = []
    skip_patterns = ['template', 'print', 'summary', 'notes', 'appendix', 'index', 'wfb']
    for g in geos:
        basename = os.path.basename(g)
        code = os.path.splitext(basename)[0].lower()
        if len(code) > 5:
            continue
        if any(p in code for p in skip_patterns):
            continue
        if code not in seen_codes:
            seen_codes.add(code)
            unique_geos.append(g)

    return unique_geos


def reparse_year(cursor, conn, year, fix_type, master_links):
    """Download zip, parse with fixed parser, insert data, restore master links."""
    print(f"    Downloading {year} zip...")
    zip_path = ba.download_zip(year)
    if not zip_path:
        raise RuntimeError(f"Failed to download {year}")

    success = 0
    failed = 0
    fallback_count = 0

    with zipfile.ZipFile(zip_path) as zf:
        country_files = get_country_files(zf)
        print(f"    Found {len(country_files)} country files in zip")

        for gf in country_files:
            code = os.path.splitext(os.path.basename(gf))[0].lower()
            try:
                html = zf.read(gf).decode('utf-8', errors='replace')
                name, categories = parse_country_fixed(html, fix_type)

                # Check if we fell back to Full Content
                if len(categories) == 1 and categories[0][0] == 'Full Content':
                    fallback_count += 1

                # Insert country
                cursor.execute(
                    "INSERT INTO Countries (Year, Code, Name, Source) OUTPUT INSERTED.CountryID VALUES (?, ?, ?, ?)",
                    year, code, name, 'html'
                )
                country_id = cursor.fetchone()[0]

                # Restore MasterCountryID from snapshot
                master_id = master_links.get(code.upper())
                if not master_id:
                    # Fallback: look up by code in MasterCountries
                    cursor.execute(
                        "SELECT MasterCountryID FROM MasterCountries WHERE CanonicalCode = ?",
                        code.upper()
                    )
                    row = cursor.fetchone()
                    if row:
                        master_id = row[0]

                if master_id:
                    cursor.execute(
                        "UPDATE Countries SET MasterCountryID = ? WHERE CountryID = ?",
                        master_id, country_id
                    )

                # Insert categories and fields
                total_fields = 0
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
                        total_fields += 1

                conn.commit()
                success += 1

            except Exception as e:
                conn.rollback()
                print(f"      ERROR [{code}]: {e}")
                failed += 1

    print(f"    Parsed: {success} countries, {failed} failed, {fallback_count} fell back to Full Content")

    # Clean up zip
    if '--keep-zips' not in sys.argv:
        try:
            os.remove(zip_path)
            print(f"    Deleted zip")
        except:
            pass

    return success, failed, fallback_count


def verify_year(cursor, year):
    """Verify repaired year has reasonable data."""
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

    # Sanity checks
    warnings = []
    if countries < 250 or countries > 280:
        warnings.append(f"Country count {countries} outside expected range 250-280")
    if avg_cats < 5:
        warnings.append(f"Too few categories/country ({avg_cats:.1f}) — parser may still be failing")
    if avg_fields < 20:
        warnings.append(f"Too few fields/country ({avg_fields:.1f})")
    if avg_fields > 10000:
        warnings.append(f"Too many fields/country ({avg_fields:.1f}) — possible over-parsing")

    # Check MasterCountryID
    cursor.execute("""
        SELECT COUNT(*) FROM Countries
        WHERE Year = ? AND MasterCountryID IS NULL
    """, year)
    unlinked = cursor.fetchone()[0]
    if unlinked > 0:
        warnings.append(f"{unlinked} countries missing MasterCountryID")

    if warnings:
        for w in warnings:
            print(f"    WARNING: {w}")
        return False
    else:
        print(f"    OK")
        return True


# ============================================================
# MAIN
# ============================================================

def main():
    dry_run = '--dry-run' in sys.argv

    # Determine which years to repair
    target_years = {}
    for arg in sys.argv[1:]:
        if arg.startswith('--year='):
            y = int(arg.split('=')[1])
            if y in BROKEN_YEARS:
                target_years[y] = BROKEN_YEARS[y]
            else:
                print(f"Year {y} is not in the broken years list: {sorted(BROKEN_YEARS.keys())}")
                return 1
        elif arg == '--year' and sys.argv.index(arg) + 1 < len(sys.argv):
            y = int(sys.argv[sys.argv.index(arg) + 1])
            if y in BROKEN_YEARS:
                target_years[y] = BROKEN_YEARS[y]
            else:
                print(f"Year {y} is not in the broken years list: {sorted(BROKEN_YEARS.keys())}")
                return 1

    if not target_years:
        target_years = BROKEN_YEARS.copy()

    print("=" * 70)
    print("CIA FACTBOOK - REPAIR BROKEN YEARS")
    print("=" * 70)
    if dry_run:
        print("MODE: DRY RUN (no changes will be made)")
    print(f"Years to repair: {sorted(target_years.keys())}")
    print()

    conn = pyodbc.connect(CONN_STR)
    cursor = conn.cursor()
    print("Connected to database.\n")

    results = {}
    for year in sorted(target_years.keys()):
        fix_type = target_years[year]
        print(f"{'='*60}")
        print(f"  YEAR {year} (fix: {fix_type})")
        print(f"{'='*60}")

        if dry_run:
            cursor.execute("""
                SELECT COUNT(DISTINCT c.CountryID),
                       COUNT(DISTINCT cc.CategoryID),
                       COUNT(cf.FieldID)
                FROM Countries c
                LEFT JOIN CountryCategories cc ON c.CountryID = cc.CountryID
                LEFT JOIN CountryFields cf ON c.CountryID = cf.CountryID
                WHERE c.Year = ?
            """, year)
            row = cursor.fetchone()
            print(f"  Current: {row[0]} countries, {row[1]:,} categories, {row[2]:,} fields")
            print(f"  Would delete and re-parse with '{fix_type}' parser")
            results[year] = "dry-run"
            continue

        # Step 1: Snapshot MasterCountryID links
        print(f"  Step 1: Snapshotting MasterCountryID links...")
        master_links = snapshot_master_links(cursor, year)
        print(f"    Captured {len(master_links)} links")

        # Step 2: Delete bad data
        print(f"  Step 2: Deleting bad data...")
        delete_year_data(cursor, conn, year)

        # Step 3: Re-download and re-parse
        print(f"  Step 3: Re-downloading and re-parsing...")
        success, failed, fallbacks = reparse_year(cursor, conn, year, fix_type, master_links)

        # Step 4: Verify
        print(f"  Step 4: Verifying...")
        ok = verify_year(cursor, year)
        results[year] = "OK" if ok else "WARNINGS"

        # Brief pause between years to be nice to Wayback Machine
        if year != sorted(target_years.keys())[-1]:
            time.sleep(2)

    # Summary
    print(f"\n{'='*60}")
    print("REPAIR SUMMARY")
    print(f"{'='*60}")
    for year in sorted(results.keys()):
        print(f"  {year}: {results[year]}")

    # Final full verification
    if not dry_run:
        print(f"\n{'='*60}")
        print("FULL DATABASE STATUS")
        print(f"{'='*60}")
        cursor.execute("""
            SELECT c.Year, c.Source, COUNT(*) AS Countries
            FROM Countries c GROUP BY c.Year, c.Source ORDER BY c.Year
        """)
        year_rows = cursor.fetchall()
        print(f"  {'Year':<6} {'Countries':<12} {'Categories':<12} {'Fields':<12} {'Source'}")
        print(f"  {'-'*5:<6} {'-'*9:<12} {'-'*10:<12} {'-'*8:<12} {'-'*6}")
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
