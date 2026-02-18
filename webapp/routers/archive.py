from fastapi import APIRouter, Request, Query
from fastapi.templating import Jinja2Templates
from pathlib import Path
import re
import difflib
from webapp.database import sql, sql_one

router = APIRouter()
templates = Jinja2Templates(directory=Path(__file__).resolve().parent.parent / "templates")


# ── Boolean Query Parser (Library of Congress / Z39.58 conventions) ──
#
# Operators:  AND, OR, NOT, "exact phrase", ( ) grouping, ? truncation
# Precedence: OR evaluated first, then AND / NOT (left-to-right)
#   per LC Catalog standard: https://catalog.loc.gov/vwebv/ui/en_US/htdocs/help/searchBoolean.html
#
# Grammar:
#   expression → and_group ( AND and_group )*
#   and_group  → or_group ( OR or_group )*
#   or_group   → NOT? atom
#   atom       → '(' expression ')' | "phrase" | word

class _Parser:
    """Recursive descent parser for LC-style boolean queries."""

    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0

    def peek(self):
        if self.pos < len(self.tokens):
            return self.tokens[self.pos]
        return None, None

    def advance(self):
        tok = self.tokens[self.pos]
        self.pos += 1
        return tok

    def parse(self):
        node = self._expression()
        return node

    def _expression(self):
        """expression → or_group ( (AND | implicit) or_group )*"""
        left = self._or_group()
        while True:
            kind, val = self.peek()
            if kind is None:
                break
            if kind == 'PAREN' and val == ')':
                break
            if kind == 'WORD' and val.upper() == 'AND':
                self.advance()  # consume AND
                right = self._or_group()
                left = ('AND', left, right)
            elif kind == 'WORD' and val.upper() in ('OR', 'NOT'):
                # Don't consume — let _or_group or _atom handle
                if val.upper() == 'OR':
                    # This shouldn't happen at this level since _or_group handles OR
                    right = self._or_group()
                    left = ('AND', left, right)
                else:
                    right = self._or_group()
                    left = ('AND', left, right)
            else:
                # Implicit AND
                right = self._or_group()
                left = ('AND', left, right)
        return left

    def _or_group(self):
        """or_group → atom ( OR atom )*"""
        left = self._atom()
        while True:
            kind, val = self.peek()
            if kind == 'WORD' and val.upper() == 'OR':
                self.advance()  # consume OR
                right = self._atom()
                left = ('OR', left, right)
            else:
                break
        return left

    def _atom(self):
        """atom → NOT atom | -word | '(' expression ')' | "phrase" | word"""
        kind, val = self.peek()

        if kind is None:
            return ('TERM', '')

        # NOT operator
        if kind == 'WORD' and val.upper() == 'NOT':
            self.advance()
            inner = self._atom()
            return ('NOT', inner)

        # -prefix negation
        if kind == 'WORD' and val.startswith('-') and len(val) > 1:
            self.advance()
            return ('NOT', ('TERM', val[1:]))

        # Parenthesized sub-expression
        if kind == 'PAREN' and val == '(':
            self.advance()  # consume (
            inner = self._expression()
            pk, pv = self.peek()
            if pk == 'PAREN' and pv == ')':
                self.advance()  # consume )
            return inner

        # Quoted phrase or plain word
        if kind in ('PHRASE', 'WORD'):
            self.advance()
            return ('TERM', val)

        # Skip unexpected tokens
        self.advance()
        return ('TERM', '')


def _tokenize_query(q):
    """Split a search query into tokens, respecting quoted phrases and parentheses."""
    tokens = []
    i = 0
    q = q.strip()
    while i < len(q):
        if q[i] in ' \t':
            i += 1
            continue
        if q[i] == '"':
            end = q.find('"', i + 1)
            if end == -1:
                end = len(q)
            phrase = q[i + 1:end].strip()
            if phrase:
                tokens.append(('PHRASE', phrase))
            i = end + 1
        elif q[i] in '()':
            tokens.append(('PAREN', q[i]))
            i += 1
        else:
            end = i
            while end < len(q) and q[end] not in ' \t"()':
                end += 1
            word = q[i:end]
            if word:
                tokens.append(('WORD', word))
            i = end
    return tokens


def _ast_to_fts(node):
    """Convert a parsed AST node into an FTS5 MATCH expression fragment."""
    if node[0] == 'TERM':
        term = node[1]
        if not term:
            return ''
        # FTS5 wildcard: trailing * for prefix search
        fts_term = term.replace('?', '*')
        # Quote the term to handle special chars safely
        safe = fts_term.replace('"', '""')
        return f'"{safe}"'
    elif node[0] == 'NOT':
        inner = _ast_to_fts(node[1])
        return f'NOT {inner}' if inner else ''
    elif node[0] == 'AND':
        left = _ast_to_fts(node[1])
        # FTS5 uses "x NOT y" as a binary operator — no "AND" before NOT
        right_node = node[2]
        if right_node[0] == 'NOT':
            right_inner = _ast_to_fts(right_node[1])
            if left and right_inner:
                return f'({left} NOT {right_inner})'
            return left or ''
        right = _ast_to_fts(right_node)
        if left and right:
            return f'({left} AND {right})'
        return left or right
    elif node[0] == 'OR':
        left = _ast_to_fts(node[1])
        right = _ast_to_fts(node[2])
        if left and right:
            return f'({left} OR {right})'
        return left or right
    return ''


def parse_boolean_query(q):
    """Parse a Library of Congress-style boolean query into SQL conditions.

    Operators: AND (default), OR, NOT, -prefix, "exact phrase", ( ) grouping,
               ? or * for truncation.
    Precedence: OR binds tighter than AND/NOT (per LC Z39.58 convention).

    Returns (sql_conditions, params) or (None, []) if empty.
    """
    tokens = _tokenize_query(q)
    if not tokens:
        return None, []
    # Filter out empty terms
    tokens = [(k, v) for k, v in tokens if v]
    if not tokens:
        return None, []
    parser = _Parser(tokens)
    ast = parser.parse()
    if not ast:
        return None, []
    fts_expr = _ast_to_fts(ast)
    if not fts_expr:
        return None, []
    # FTS5 cannot handle standalone NOT (e.g. "-nuclear") — needs a positive term
    if fts_expr.lstrip().startswith('NOT '):
        return None, []
    return fts_expr, [fts_expr]


# ── HTML Pages ──────────────────────────────────────────────

@router.get("/archive")
async def archive_index(request: Request):
    years = sql("""
        SELECT c.Year, COUNT(DISTINCT c.CountryID) AS CountryCount,
               c.Source, COUNT(cf.FieldID) AS FieldCount
        FROM Countries c
        LEFT JOIN CountryFields cf ON c.CountryID = cf.CountryID
        GROUP BY c.Year, c.Source
        ORDER BY c.Year DESC
    """)
    return templates.TemplateResponse("archive/browse.html", {
        "request": request, "years": years,
    })


@router.get("/archive/library")
async def archive_library(request: Request):
    entities = sql("""
        SELECT mc.MasterCountryID, mc.CanonicalName, mc.ISOAlpha2,
               mc.CanonicalCode, mc.EntityType,
               MIN(c.Year) AS FirstYear, MAX(c.Year) AS LastYear,
               COUNT(DISTINCT c.Year) AS YearCount
        FROM MasterCountries mc
        JOIN Countries c ON mc.MasterCountryID = c.MasterCountryID
        GROUP BY mc.MasterCountryID, mc.CanonicalName, mc.ISOAlpha2,
                 mc.CanonicalCode, mc.EntityType
        ORDER BY mc.CanonicalName
    """)

    entity_groups = {}
    for e in entities:
        t = e['EntityType'] or 'Other'
        entity_groups.setdefault(t, []).append(e)

    stats = sql_one("""
        SELECT (SELECT COUNT(*) FROM MasterCountries) AS total_entities,
               (SELECT COUNT(DISTINCT Year) FROM Countries) AS total_years,
               (SELECT COUNT(*) FROM CountryFields) AS total_fields
    """)

    return templates.TemplateResponse("archive/library.html", {
        "request": request,
        "entity_groups": entity_groups,
        "stats": stats,
        "total": len(entities),
    })


@router.get("/archive/{year}")
async def archive_year(request: Request, year: int):
    countries = sql("""
        SELECT c.CountryID, c.Name, c.Code, c.Source,
               mc.CanonicalName, mc.ISOAlpha2, mc.CanonicalCode, mc.EntityType,
               COUNT(cf.FieldID) AS FieldCount
        FROM Countries c
        JOIN MasterCountries mc ON c.MasterCountryID = mc.MasterCountryID
        LEFT JOIN CountryFields cf ON c.CountryID = cf.CountryID
        WHERE c.Year = ?
        GROUP BY c.CountryID, c.Name, c.Code, c.Source,
                 mc.CanonicalName, mc.ISOAlpha2, mc.CanonicalCode, mc.EntityType
        ORDER BY mc.CanonicalName
    """, [year])

    # Get list of all years for navigation
    all_years = sql("SELECT DISTINCT Year FROM Countries ORDER BY Year")

    return templates.TemplateResponse("archive/browse.html", {
        "request": request,
        "selected_year": year,
        "countries": countries,
        "all_years": [r['Year'] for r in all_years],
        "years": None,
    })


@router.get("/archive/{year}/{code}")
async def country_profile(request: Request, year: int, code: str):
    # Find the country
    country = sql_one("""
        SELECT c.CountryID, c.Year, c.Name, c.Code, c.Source,
               mc.CanonicalName, mc.ISOAlpha2,
               mc.EntityType, mc.MasterCountryID
        FROM Countries c
        JOIN MasterCountries mc ON c.MasterCountryID = mc.MasterCountryID
        WHERE c.Year = ? AND (mc.CanonicalCode = ? OR mc.ISOAlpha2 = ?)
    """, [year, code.upper(), code.upper()])

    if not country:
        return templates.TemplateResponse("archive/country.html", {
            "request": request, "country": None, "year": year, "code": code,
            "categories": [], "other_years": [],
        })

    # Get all categories and fields
    fields = sql("""
        SELECT cc.CategoryTitle, cf.FieldName, cf.Content,
               fm.CanonicalName
        FROM CountryFields cf
        JOIN CountryCategories cc ON cf.CategoryID = cc.CategoryID
        LEFT JOIN FieldNameMappings fm ON cf.FieldName = fm.OriginalName
        WHERE cf.CountryID = ?
        ORDER BY cc.CategoryTitle, cf.FieldName
    """, [country['CountryID']])

    # Organize by category
    categories = {}
    for f in fields:
        cat = f['CategoryTitle'] or 'Uncategorized'
        categories.setdefault(cat, []).append(f)

    # Other years for this country
    other_years = sql("""
        SELECT c.Year FROM Countries c
        WHERE c.MasterCountryID = ?
        ORDER BY c.Year
    """, [country['MasterCountryID']])

    return templates.TemplateResponse("archive/country.html", {
        "request": request,
        "country": country,
        "year": year,
        "code": code,
        "categories": categories,
        "other_years": [r['Year'] for r in other_years],
    })


@router.get("/archive/field/{code}/{field_name:path}")
async def field_time_series(request: Request, code: str, field_name: str):
    # Find master country
    master = sql_one("""
        SELECT MasterCountryID, CanonicalName, ISOAlpha2
        FROM MasterCountries
        WHERE CanonicalCode = ? OR ISOAlpha2 = ?
    """, [code.upper(), code.upper()])

    if not master:
        return templates.TemplateResponse("archive/field.html", {
            "request": request, "master": None, "field_name": field_name,
            "records": [], "code": code,
        })

    # Get field across all years
    records = sql("""
        SELECT c.Year, cf.Content
        FROM CountryFields cf
        JOIN Countries c ON cf.CountryID = c.CountryID
        LEFT JOIN FieldNameMappings fm ON cf.FieldName = fm.OriginalName
        WHERE c.MasterCountryID = ?
          AND (fm.CanonicalName = ? OR cf.FieldName = ?)
        ORDER BY c.Year
    """, [master['MasterCountryID'], field_name, field_name])

    return templates.TemplateResponse("archive/field.html", {
        "request": request,
        "master": master,
        "field_name": field_name,
        "records": records,
        "code": code,
    })


def _year_filter(year_start, year_end):
    """Build SQL year clause and params for search endpoints."""
    clause = ""
    params = []
    if year_start and year_end:
        clause = " AND c.Year BETWEEN ? AND ?"
        params = [year_start, year_end]
    elif year_start:
        clause = " AND c.Year >= ?"
        params = [year_start]
    elif year_end:
        clause = " AND c.Year <= ?"
        params = [year_end]
    return clause, params


PER_PAGE = 50

def _build_search_query(q, year_start, year_end):
    """Build the search WHERE clause from a boolean query string.
    Returns (base_where, params) or (None, None) if query is empty."""
    fts_expr, fts_params = parse_boolean_query(q)
    if not fts_expr:
        return None, None

    yr_clause, yr_params = _year_filter(year_start, year_end)

    base_where = f"""
        FROM CountryFieldsFTS fts
        JOIN CountryFields cf ON cf.FieldID = fts.rowid
        JOIN Countries c ON cf.CountryID = c.CountryID
        JOIN CountryCategories cc ON cf.CategoryID = cc.CategoryID
        JOIN MasterCountries mc ON c.MasterCountryID = mc.MasterCountryID
        LEFT JOIN FieldNameMappings fm ON cf.FieldName = fm.OriginalName
        WHERE CountryFieldsFTS MATCH ?
          {yr_clause}
          AND (fm.IsNoise = 0 OR fm.IsNoise IS NULL)"""

    params = fts_params + yr_params
    return base_where, params


@router.get("/search")
async def search_page(request: Request, q: str = "",
                      year_start: int = 0, year_end: int = 0, page: int = 1):
    results = []
    total = 0
    if page < 1:
        page = 1

    base_where, params = _build_search_query(q, year_start, year_end) \
        if q else (None, None)

    search_error = None
    if base_where:
        try:
            count_row = sql_one(f"SELECT COUNT(*) AS cnt {base_where}", params)
            total = count_row['cnt'] if count_row else 0

            offset = (page - 1) * PER_PAGE
            results = sql(f"""
                SELECT c.Year, c.Name, c.Code, cc.CategoryTitle,
                    cf.FieldName, SUBSTR(cf.Content, 1, 400) AS ContentPreview,
                    mc.CanonicalCode, mc.ISOAlpha2
                {base_where}
                ORDER BY c.Year DESC, c.Name
                LIMIT ? OFFSET ?
            """, params + [PER_PAGE, offset])
        except Exception:
            search_error = "Search syntax not supported. Try simpler terms or remove special characters."

    all_years = sql("SELECT DISTINCT Year FROM Countries ORDER BY Year DESC")
    total_pages = max(1, (total + PER_PAGE - 1) // PER_PAGE) if total else 1

    return templates.TemplateResponse("archive/search.html", {
        "request": request,
        "q": q,
        "year_start": year_start,
        "year_end": year_end,
        "results": results,
        "all_years": [r['Year'] for r in all_years],
        "page": page,
        "total": total,
        "total_pages": total_pages,
        "per_page": PER_PAGE,
        "search_error": search_error,
    })


# ── JSON APIs ───────────────────────────────────────────────

@router.get("/api/years")
async def api_years():
    return sql("""
        SELECT c.Year, COUNT(DISTINCT c.CountryID) AS CountryCount,
               c.Source, COUNT(cf.FieldID) AS FieldCount
        FROM Countries c
        LEFT JOIN CountryFields cf ON c.CountryID = cf.CountryID
        GROUP BY c.Year, c.Source
        ORDER BY c.Year
    """)


@router.get("/api/archive/fields/{code}")
async def api_country_fields(code: str):
    """Return list of canonical field names available for a country."""
    master = sql_one("""
        SELECT MasterCountryID FROM MasterCountries
        WHERE CanonicalCode = ? OR ISOAlpha2 = ?
    """, [code.upper(), code.upper()])
    if not master:
        return []
    rows = sql("""
        SELECT DISTINCT fm.CanonicalName
        FROM CountryFields cf
        JOIN Countries c ON cf.CountryID = c.CountryID
        JOIN FieldNameMappings fm ON cf.FieldName = fm.OriginalName
        WHERE c.MasterCountryID = ? AND fm.IsNoise = 0
        ORDER BY fm.CanonicalName
    """, [master['MasterCountryID']])
    return [r['CanonicalName'] for r in rows]


@router.get("/api/archive/{year}")
async def api_archive_year(year: int):
    return sql("""
        SELECT c.CountryID, c.Name, c.Code,
               mc.CanonicalName, mc.ISOAlpha2, mc.EntityType
        FROM Countries c
        JOIN MasterCountries mc ON c.MasterCountryID = mc.MasterCountryID
        WHERE c.Year = ?
        ORDER BY mc.CanonicalName
    """, [year])


@router.get("/api/archive/{year}/{code}")
async def api_archive_country(year: int, code: str):
    country = sql_one("""
        SELECT c.CountryID, c.Year, c.Name, c.Code,
               mc.CanonicalName, mc.ISOAlpha2
        FROM Countries c
        JOIN MasterCountries mc ON c.MasterCountryID = mc.MasterCountryID
        WHERE c.Year = ? AND (mc.CanonicalCode = ? OR mc.ISOAlpha2 = ?)
    """, [year, code.upper(), code.upper()])

    if not country:
        return {"error": "Not found"}

    fields = sql("""
        SELECT cc.CategoryTitle, cf.FieldName, cf.Content,
               fm.CanonicalName
        FROM CountryFields cf
        JOIN CountryCategories cc ON cf.CategoryID = cc.CategoryID
        LEFT JOIN FieldNameMappings fm ON cf.FieldName = fm.OriginalName
        WHERE cf.CountryID = ?
        ORDER BY cc.CategoryTitle, cf.FieldName
    """, [country['CountryID']])

    return {"country": country, "fields": fields}


@router.get("/api/field/{code}/{field_name:path}")
async def api_field_series(code: str, field_name: str):
    master = sql_one("""
        SELECT MasterCountryID, CanonicalName
        FROM MasterCountries
        WHERE CanonicalCode = ? OR ISOAlpha2 = ?
    """, [code.upper(), code.upper()])

    if not master:
        return {"error": "Country not found"}

    records = sql("""
        SELECT c.Year, cf.Content
        FROM CountryFields cf
        JOIN Countries c ON cf.CountryID = c.CountryID
        LEFT JOIN FieldNameMappings fm ON cf.FieldName = fm.OriginalName
        WHERE c.MasterCountryID = ?
          AND (fm.CanonicalName = ? OR cf.FieldName = ?)
        ORDER BY c.Year
    """, [master['MasterCountryID'], field_name, field_name])

    return {"country": master['CanonicalName'], "field": field_name, "series": records}


@router.get("/api/search")
async def api_search(q: str = "", year_start: int = 0, year_end: int = 0, page: int = 1):
    if not q:
        return {"results": [], "total": 0, "page": 1, "total_pages": 0}
    if page < 1:
        page = 1

    base_where, params = _build_search_query(q, year_start, year_end) \
        if q else (None, None)

    if not base_where:
        return {"results": [], "total": 0, "page": 1, "total_pages": 0}

    try:
        count_row = sql_one(f"SELECT COUNT(*) AS cnt {base_where}", params)
        total = count_row['cnt'] if count_row else 0

        offset = (page - 1) * PER_PAGE
        results = sql(f"""
            SELECT c.Year, c.Name, c.Code, cc.CategoryTitle,
                cf.FieldName, SUBSTR(cf.Content, 1, 400) AS ContentPreview,
                mc.CanonicalCode, mc.ISOAlpha2
            {base_where}
            ORDER BY c.Year DESC, c.Name
            LIMIT ? OFFSET ?
        """, params + [PER_PAGE, offset])
    except Exception:
        return {"results": [], "total": 0, "page": 1, "total_pages": 0,
                "error": "Search syntax not supported"}

    total_pages = max(1, (total + PER_PAGE - 1) // PER_PAGE) if total else 0
    return {"results": results, "total": total, "page": page, "total_pages": total_pages}


@router.get("/api/fields")
async def api_fields():
    return sql("""
        SELECT CanonicalName, COUNT(*) AS Variants
        FROM FieldNameMappings
        WHERE IsNoise = 0
        GROUP BY CanonicalName
        ORDER BY CanonicalName
    """)


# ══════════════════════════════════════════════════════════════════════
#  FEATURE: TEXT DIFF
# ══════════════════════════════════════════════════════════════════════

def _get_field_content(master_id, year, canonical_field):
    """Fetch the raw Content string for a specific country/year/field."""
    row = sql_one("""
        SELECT cf.Content
        FROM CountryFields cf
        JOIN Countries c ON cf.CountryID = c.CountryID
        JOIN FieldNameMappings fm ON cf.FieldName = fm.OriginalName
        WHERE c.MasterCountryID = ? AND c.Year = ?
          AND fm.CanonicalName = ? AND fm.IsNoise = 0
        LIMIT 1
    """, [master_id, year, canonical_field])
    return row['Content'] if row else None


def _compute_diff(text_a, text_b):
    """Compute a sentence-level diff between two texts.

    Returns list of {'tag': equal|replace|insert|delete,
                     'a': old_text, 'b': new_text}
    """
    if text_a is None:
        text_a = ''
    if text_b is None:
        text_b = ''

    # Split on sentence boundaries ('; ' or '. ') for granularity
    def split_sentences(t):
        parts = re.split(r'(?<=[;.])\s+', t)
        return [p for p in parts if p.strip()]

    a_parts = split_sentences(text_a)
    b_parts = split_sentences(text_b)

    sm = difflib.SequenceMatcher(None, a_parts, b_parts)
    diff = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        diff.append({
            'tag': tag,
            'a': ' '.join(a_parts[i1:i2]),
            'b': ' '.join(b_parts[j1:j2]),
        })
    return diff


@router.get("/analysis/diff")
async def diff_page(request: Request, code: str = "", field: str = "",
                    year_a: int = 0, year_b: int = 0):
    # All sovereign countries for dropdown
    countries = sql("""
        SELECT CanonicalName, ISOAlpha2
        FROM MasterCountries mc
        WHERE ISOAlpha2 IS NOT NULL
          AND (mc.EntityType = 'sovereign'
               OR NOT EXISTS (
                   SELECT 1 FROM MasterCountries mc2
                   WHERE mc2.ISOAlpha2 = mc.ISOAlpha2
                     AND mc2.EntityType = 'sovereign'
                     AND mc2.MasterCountryID != mc.MasterCountryID))
        ORDER BY CanonicalName
    """)

    all_years = [r['Year'] for r in sql(
        "SELECT DISTINCT Year FROM Countries ORDER BY Year DESC"
    )]

    diff_result = None
    text_a = None
    text_b = None
    country_name = ''

    if code and field and year_a and year_b:
        master = sql_one("""
            SELECT MasterCountryID, CanonicalName FROM MasterCountries
            WHERE CanonicalCode = ? OR ISOAlpha2 = ?
        """, [code.upper(), code.upper()])

        if master:
            country_name = master['CanonicalName']
            text_a = _get_field_content(master['MasterCountryID'], year_a, field)
            text_b = _get_field_content(master['MasterCountryID'], year_b, field)
            diff_result = _compute_diff(text_a, text_b)

    return templates.TemplateResponse("analysis/diff.html", {
        "request": request,
        "countries": countries,
        "all_years": all_years,
        "code": code,
        "field": field,
        "year_a": year_a,
        "year_b": year_b,
        "country_name": country_name,
        "text_a": text_a,
        "text_b": text_b,
        "diff": diff_result,
    })
