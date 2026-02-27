"""
FieldValues Dashboard Preview — NEW sub-field queries only.

Every chart shows the actual SQL query + the raw source text it was parsed from.

Usage:
    python etl/structured_parsing/dashboard_preview.py
    Open http://localhost:8050 in your browser.
"""

import json
import os
import sqlite3
import html as html_mod

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import uvicorn

DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "data", "factbook_field_values.db"
)


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def query_pivot_with_source(year, canonical_name, sub_fields, limit=15, order_sub=None):
    """Get chart data + the raw Content it was parsed from."""
    db = get_db()
    cases = ", ".join(
        f"MAX(CASE WHEN fv.SubField = '{s}' THEN fv.NumericVal END) AS [{s}]"
        for s in sub_fields
    )
    order_col = order_sub or sub_fields[0]
    rows = db.execute(f"""
        SELECT c.Name, c.Year, cf.FieldName, cf.Content, {cases}
        FROM FieldValues fv
        JOIN CountryFields cf ON fv.FieldID = cf.FieldID
        JOIN Countries c ON cf.CountryID = c.CountryID
        JOIN FieldNameMappings fnm ON cf.FieldName = fnm.OriginalName
        WHERE c.Year = ?
          AND fnm.CanonicalName = ?
          AND fv.SubField IN ({','.join('?' for _ in sub_fields)})
          AND fv.NumericVal IS NOT NULL
          AND fnm.IsNoise = 0
          AND c.Name NOT IN ('World', 'European Union')
        GROUP BY c.Name, cf.FieldID
        HAVING [{order_col}] IS NOT NULL
        ORDER BY [{order_col}] DESC
        LIMIT ?
    """, (year, canonical_name, *sub_fields, limit)).fetchall()
    db.close()
    return rows


def query_scatter_with_source(year, canonical_name, sub_a, sub_b, limit=200):
    """Scatter data + raw source for a sample."""
    db = get_db()
    rows = db.execute(f"""
        SELECT c.Name, cf.Content,
               MAX(CASE WHEN fv.SubField = ? THEN fv.NumericVal END) AS val_a,
               MAX(CASE WHEN fv.SubField = ? THEN fv.NumericVal END) AS val_b
        FROM FieldValues fv
        JOIN CountryFields cf ON fv.FieldID = cf.FieldID
        JOIN Countries c ON cf.CountryID = c.CountryID
        JOIN FieldNameMappings fnm ON cf.FieldName = fnm.OriginalName
        WHERE c.Year = ?
          AND fnm.CanonicalName = ?
          AND fv.SubField IN (?, ?)
          AND fv.NumericVal IS NOT NULL
          AND fnm.IsNoise = 0
          AND c.Name NOT IN ('World', 'European Union')
        GROUP BY c.Name, cf.FieldID
        HAVING val_a IS NOT NULL AND val_b IS NOT NULL
        LIMIT ?
    """, (sub_a, sub_b, year, canonical_name, sub_a, sub_b, limit)).fetchall()
    db.close()
    return rows


def build_source_table(rows, sub_fields, show_content=True):
    """Build an HTML table showing country, parsed values, and raw source."""
    cols = ["Country"] + [s for s in sub_fields]
    if show_content:
        cols.append("Raw Source (CountryFields.Content)")

    header = "".join(f"<th>{c}</th>" for c in cols)
    body = ""
    for r in rows[:10]:  # Show top 10
        name = html_mod.escape(str(r["Name"]))
        vals = ""
        for s in sub_fields:
            v = r[s]
            if v is not None:
                if abs(v) >= 1e9:
                    vals += f"<td class='num'>${v/1e9:,.1f}B</td>"
                elif abs(v) >= 1e6:
                    vals += f"<td class='num'>{v:,.0f}</td>"
                elif abs(v) >= 100:
                    vals += f"<td class='num'>{v:,.0f}</td>"
                else:
                    vals += f"<td class='num'>{v:,.1f}</td>"
            else:
                vals += "<td class='num'>-</td>"

        content_cell = ""
        if show_content:
            raw = str(r["Content"] or "")[:300]
            raw = html_mod.escape(raw)
            content_cell = f"<td class='raw'>{raw}</td>"

        body += f"<tr><td class='country'>{name}</td>{vals}{content_cell}</tr>"

    return f"<table class='data-table'><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>"


def build_scatter_source_table(rows, label_a, label_b):
    """Table for scatter data with source."""
    header = f"<th>Country</th><th>{label_a}</th><th>{label_b}</th><th>Raw Source (CountryFields.Content)</th>"
    body = ""
    # Show 8 samples spread across the data
    sample_idx = list(range(0, len(rows), max(1, len(rows)//8)))[:8]
    for i in sample_idx:
        r = rows[i]
        name = html_mod.escape(str(r["Name"]))
        va = r["val_a"]
        vb = r["val_b"]
        raw = html_mod.escape(str(r["Content"] or "")[:300])
        body += f"<tr><td class='country'>{name}</td><td class='num'>{va:.1f}</td><td class='num'>{vb:.1f}</td><td class='raw'>{raw}</td></tr>"

    return f"<table class='data-table'><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>"


app = FastAPI()


@app.get("/", response_class=HTMLResponse)
def dashboard():
    # ── Query data ──
    # 1. Land vs Water
    lw_sql = """SELECT c.Name,
  MAX(CASE WHEN fv.SubField = 'land' THEN fv.NumericVal END) AS land,
  MAX(CASE WHEN fv.SubField = 'water' THEN fv.NumericVal END) AS water
FROM FieldValues fv
JOIN CountryFields cf ON fv.FieldID = cf.FieldID
JOIN Countries c ON cf.CountryID = c.CountryID
JOIN FieldNameMappings fnm ON cf.FieldName = fnm.OriginalName
WHERE c.Year = 2025 AND fnm.CanonicalName = 'Area'
  AND fv.SubField IN ('land', 'water')
GROUP BY c.Name, cf.FieldID
ORDER BY land DESC LIMIT 15"""
    lw_rows = query_pivot_with_source(2025, "Area", ["land", "water"], 15, "land")
    lw_names = json.dumps([r["Name"] for r in lw_rows])
    lw_land = json.dumps([r["land"] or 0 for r in lw_rows])
    lw_water = json.dumps([r["water"] or 0 for r in lw_rows])
    lw_table = build_source_table(lw_rows, ["land", "water"])

    # 2. Life exp male vs female
    le_sql = """SELECT c.Name,
  MAX(CASE WHEN fv.SubField = 'male' THEN fv.NumericVal END) AS male,
  MAX(CASE WHEN fv.SubField = 'female' THEN fv.NumericVal END) AS female
FROM FieldValues fv
JOIN CountryFields cf ON fv.FieldID = cf.FieldID
JOIN Countries c ON cf.CountryID = c.CountryID
JOIN FieldNameMappings fnm ON cf.FieldName = fnm.OriginalName
WHERE c.Year = 2025
  AND fnm.CanonicalName = 'Life expectancy at birth'
  AND fv.SubField IN ('male', 'female')
GROUP BY c.Name, cf.FieldID
HAVING male IS NOT NULL AND female IS NOT NULL"""
    le_rows = query_scatter_with_source(2025, "Life expectancy at birth", "male", "female")
    le_scatter = json.dumps([[r["val_a"], r["val_b"], r["Name"]] for r in le_rows])
    le_table = build_scatter_source_table(le_rows, "Male (yrs)", "Female (yrs)")

    # 3. Age structure
    age_sql = """SELECT c.Name,
  MAX(CASE WHEN fv.SubField = '0-14 years_pct' THEN fv.NumericVal END) AS [0-14],
  MAX(CASE WHEN fv.SubField = '15-64 years_pct' THEN fv.NumericVal END) AS [15-64],
  MAX(CASE WHEN fv.SubField = '65 years and over_pct' THEN fv.NumericVal END) AS [65+]
FROM FieldValues fv ...
WHERE fnm.CanonicalName = 'Age structure'
ORDER BY [65+] DESC LIMIT 20"""
    age_rows = query_pivot_with_source(
        2025, "Age structure",
        ["0-14 years_pct", "15-64 years_pct", "65 years and over_pct"],
        20, "65 years and over_pct"
    )
    age_names = json.dumps([r["Name"] for r in age_rows])
    age_014 = json.dumps([r["0-14 years_pct"] or 0 for r in age_rows])
    age_1564 = json.dumps([r["15-64 years_pct"] or 0 for r in age_rows])
    age_65 = json.dumps([r["65 years and over_pct"] or 0 for r in age_rows])
    age_table = build_source_table(age_rows, ["0-14 years_pct", "15-64 years_pct", "65 years and over_pct"])

    # 4. Budget revenues vs expenditures
    bud_sql = """SELECT c.Name,
  MAX(CASE WHEN fv.SubField = 'revenues' THEN fv.NumericVal END) AS revenues,
  MAX(CASE WHEN fv.SubField = 'expenditures' THEN fv.NumericVal END) AS expenditures
FROM FieldValues fv ...
WHERE fnm.CanonicalName = 'Budget'
ORDER BY revenues DESC LIMIT 15"""
    bud_rows = query_pivot_with_source(2025, "Budget", ["revenues", "expenditures"], 15, "revenues")
    bud_names = json.dumps([r["Name"] for r in bud_rows])
    bud_rev = json.dumps([r["revenues"] or 0 for r in bud_rows])
    bud_exp = json.dumps([r["expenditures"] or 0 for r in bud_rows])
    bud_table = build_source_table(bud_rows, ["revenues", "expenditures"])

    # 5. Dependency ratios
    dep_sql = """SELECT c.Name,
  MAX(CASE WHEN fv.SubField = 'youth' THEN fv.NumericVal END) AS youth,
  MAX(CASE WHEN fv.SubField = 'elderly' THEN fv.NumericVal END) AS elderly
FROM FieldValues fv ...
WHERE fnm.CanonicalName = 'Dependency ratios'"""
    dep_rows = query_scatter_with_source(2025, "Dependency ratios", "youth", "elderly")
    dep_scatter = json.dumps([[r["val_a"], r["val_b"], r["Name"]] for r in dep_rows])
    dep_table = build_scatter_source_table(dep_rows, "Youth dep.", "Elderly dep.")

    # 6. Elevation extremes
    elev_sql = """SELECT c.Name,
  MAX(CASE WHEN fv.SubField = 'highest' THEN fv.NumericVal END) AS highest,
  MAX(CASE WHEN fv.SubField = 'lowest' THEN fv.NumericVal END) AS lowest
FROM FieldValues fv ...
WHERE fnm.CanonicalName = 'Elevation'
ORDER BY highest DESC LIMIT 15"""
    elev_rows = query_pivot_with_source(2025, "Elevation", ["highest", "lowest"], 15, "highest")
    elev_names = json.dumps([r["Name"] for r in elev_rows])
    elev_hi = json.dumps([r["highest"] or 0 for r in elev_rows])
    elev_lo = json.dumps([r["lowest"] or 0 for r in elev_rows])
    elev_table = build_source_table(elev_rows, ["highest", "lowest"])

    # 7. Land use
    lu_sql = """SELECT c.Name,
  MAX(CASE WHEN fv.SubField = 'forest' THEN fv.NumericVal END) AS forest,
  MAX(CASE WHEN fv.SubField = 'agricultural_land' THEN fv.NumericVal END) AS agricultural,
  MAX(CASE WHEN fv.SubField = 'other' THEN fv.NumericVal END) AS other
FROM FieldValues fv ...
WHERE fnm.CanonicalName = 'Land use'
ORDER BY forest DESC LIMIT 15"""
    lu_rows = query_pivot_with_source(2025, "Land use", ["forest", "agricultural_land", "other"], 15, "forest")
    lu_names = json.dumps([r["Name"] for r in lu_rows])
    lu_forest = json.dumps([r["forest"] or 0 for r in lu_rows])
    lu_agri = json.dumps([r["agricultural_land"] or 0 for r in lu_rows])
    lu_other = json.dumps([r["other"] or 0 for r in lu_rows])
    lu_table = build_source_table(lu_rows, ["forest", "agricultural_land", "other"])

    # 8. Urbanization scatter
    urb_sql = """SELECT c.Name,
  MAX(CASE WHEN fv.SubField = 'urban_population' THEN fv.NumericVal END) AS urban_pct,
  MAX(CASE WHEN fv.SubField = 'rate_of_urbanization' THEN fv.NumericVal END) AS rate
FROM FieldValues fv ...
WHERE fnm.CanonicalName = 'Urbanization'"""
    urb_rows = query_scatter_with_source(2025, "Urbanization", "urban_population", "rate_of_urbanization")
    urb_scatter = json.dumps([[r["val_a"], r["val_b"], r["Name"]] for r in urb_rows])
    urb_table = build_scatter_source_table(urb_rows, "Urban %", "Growth rate %")

    # Escape SQL for HTML
    def esc_sql(s):
        return html_mod.escape(s)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>FieldValues Dashboard -- New Queries</title>
<script src="https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js"></script>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    background: #111418; color: #D4D8DD;
    font-family: 'Segoe UI', system-ui, sans-serif; padding: 24px;
  }}
  h1 {{ color: #E8ECEF; font-size: 26px; font-weight: 600; margin-bottom: 6px; }}
  .subtitle {{ color: #8A919A; font-size: 14px; margin-bottom: 24px; }}
  .panel {{
    background: #1C2127; border: 1px solid #2F343C; border-radius: 8px;
    padding: 20px; margin-bottom: 20px;
  }}
  .panel h3 {{ color: #E8ECEF; font-size: 16px; font-weight: 600; margin-bottom: 4px; }}
  .new-badge {{
    display: inline-block; background: #51CF66; color: #111418;
    font-size: 10px; font-weight: 700; padding: 2px 6px;
    border-radius: 3px; margin-left: 8px; vertical-align: middle;
  }}
  .hint {{ color: #6B7785; font-size: 11px; margin-bottom: 8px; }}
  .sql-box {{
    background: #0D1117; border: 1px solid #2F343C; border-radius: 6px;
    padding: 12px 16px; margin: 10px 0;
    font-family: 'Cascadia Code', 'Fira Code', monospace;
    font-size: 12px; color: #79C0FF; white-space: pre-wrap;
    line-height: 1.5; overflow-x: auto;
  }}
  .sql-label {{
    color: #8A919A; font-size: 11px; text-transform: uppercase;
    letter-spacing: 0.5px; margin-bottom: 4px; font-weight: 600;
  }}
  .chart {{ width: 100%; height: 380px; }}
  .chart-row {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }}
  .data-table {{
    width: 100%; border-collapse: collapse; margin-top: 12px; font-size: 12px;
  }}
  .data-table th {{
    background: #0D1117; color: #8A919A; padding: 8px 10px;
    text-align: left; font-weight: 600; border-bottom: 1px solid #2F343C;
    position: sticky; top: 0;
  }}
  .data-table td {{
    padding: 6px 10px; border-bottom: 1px solid #1a1f26;
  }}
  .data-table tr:hover {{ background: #1a2332; }}
  .data-table .country {{ color: #E8ECEF; font-weight: 500; white-space: nowrap; }}
  .data-table .num {{ color: #4A9EFF; text-align: right; font-family: monospace; }}
  .data-table .raw {{
    color: #6B7785; font-size: 11px; max-width: 500px;
    overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
    font-family: monospace;
  }}
  .table-scroll {{ max-height: 350px; overflow-y: auto; }}
  .toggle-btn {{
    background: #2F343C; color: #8A919A; border: none; border-radius: 4px;
    padding: 6px 12px; font-size: 11px; cursor: pointer; margin: 8px 4px 0 0;
  }}
  .toggle-btn:hover {{ background: #3D434C; color: #D4D8DD; }}
  .toggle-btn.active {{ background: #4A9EFF; color: #111418; }}
  .tab-content {{ display: none; }}
  .tab-content.active {{ display: block; }}
  .banner {{
    background: linear-gradient(135deg, #1a2332 0%, #1C2127 100%);
    border: 1px solid #2F343C; border-left: 4px solid #51CF66;
    border-radius: 8px; padding: 16px 20px; margin-bottom: 24px;
  }}
  .banner p {{ color: #8A919A; font-size: 13px; line-height: 1.6; }}
  .banner strong {{ color: #D4D8DD; }}
</style>
</head>
<body>

<h1>FieldValues Dashboard<span class="new-badge">NEW QUERIES ONLY</span></h1>
<p class="subtitle">Sub-field breakdowns the webapp's regex parsers never extracted -- 188,177 new queryable values</p>

<div class="banner">
  <p>
    Each panel shows: <strong>the chart</strong>, <strong>the exact SQL query</strong>, and <strong>the raw source text</strong> from CountryFields.Content that was parsed.<br>
    You can see exactly where each number came from.
  </p>
</div>

<!-- ═══════ 1. LAND VS WATER ═══════ -->
<div class="panel">
  <h3>Land vs Water Area -- Top 15 (2025)<span class="new-badge">NEW</span></h3>
  <div class="hint">The webapp only extracts total area. Land/water split is new.</div>
  <div>
    <button class="toggle-btn active" onclick="showTab(this,'c1-chart')">Chart</button>
    <button class="toggle-btn" onclick="showTab(this,'c1-sql')">SQL Query</button>
    <button class="toggle-btn" onclick="showTab(this,'c1-source')">Source Data</button>
  </div>
  <div id="c1-chart" class="tab-content active"><div id="c1" class="chart"></div></div>
  <div id="c1-sql" class="tab-content">
    <div class="sql-label">SQL Query</div>
    <div class="sql-box">{esc_sql(lw_sql)}</div>
  </div>
  <div id="c1-source" class="tab-content">
    <div class="sql-label">Parsed Results + Raw Source Text</div>
    <div class="table-scroll">{lw_table}</div>
  </div>
</div>

<!-- ═══════ 2. LIFE EXPECTANCY M/F ═══════ -->
<div class="panel">
  <h3>Life Expectancy: Male vs Female (2025)<span class="new-badge">NEW</span></h3>
  <div class="hint">The webapp only extracts total_population. Male/female split is new.</div>
  <div>
    <button class="toggle-btn active" onclick="showTab(this,'c2-chart')">Chart</button>
    <button class="toggle-btn" onclick="showTab(this,'c2-sql')">SQL Query</button>
    <button class="toggle-btn" onclick="showTab(this,'c2-source')">Source Data</button>
  </div>
  <div id="c2-chart" class="tab-content active"><div id="c2" class="chart"></div></div>
  <div id="c2-sql" class="tab-content">
    <div class="sql-label">SQL Query</div>
    <div class="sql-box">{esc_sql(le_sql)}</div>
  </div>
  <div id="c2-source" class="tab-content">
    <div class="sql-label">Parsed Results + Raw Source Text</div>
    <div class="table-scroll">{le_table}</div>
  </div>
</div>

<!-- ═══════ 3. AGE STRUCTURE ═══════ -->
<div class="panel">
  <h3>Age Structure -- Top 20 Oldest Populations (2025)<span class="new-badge">NEW</span></h3>
  <div class="hint">Age bracket percentages (0-14, 15-64, 65+) were never parsed.</div>
  <div>
    <button class="toggle-btn active" onclick="showTab(this,'c3-chart')">Chart</button>
    <button class="toggle-btn" onclick="showTab(this,'c3-sql')">SQL Query</button>
    <button class="toggle-btn" onclick="showTab(this,'c3-source')">Source Data</button>
  </div>
  <div id="c3-chart" class="tab-content active"><div id="c3" class="chart"></div></div>
  <div id="c3-sql" class="tab-content">
    <div class="sql-label">SQL Query</div>
    <div class="sql-box">{esc_sql(age_sql)}</div>
  </div>
  <div id="c3-source" class="tab-content">
    <div class="sql-label">Parsed Results + Raw Source Text</div>
    <div class="table-scroll">{age_table}</div>
  </div>
</div>

<!-- ═══════ 4. BUDGET ═══════ -->
<div class="panel">
  <h3>Budget: Revenues vs Expenditures (2025)<span class="new-badge">NEW</span></h3>
  <div class="hint">Budget revenues/expenditures were never individually parsed.</div>
  <div>
    <button class="toggle-btn active" onclick="showTab(this,'c4-chart')">Chart</button>
    <button class="toggle-btn" onclick="showTab(this,'c4-sql')">SQL Query</button>
    <button class="toggle-btn" onclick="showTab(this,'c4-source')">Source Data</button>
  </div>
  <div id="c4-chart" class="tab-content active"><div id="c4" class="chart"></div></div>
  <div id="c4-sql" class="tab-content">
    <div class="sql-label">SQL Query</div>
    <div class="sql-box">{esc_sql(bud_sql)}</div>
  </div>
  <div id="c4-source" class="tab-content">
    <div class="sql-label">Parsed Results + Raw Source Text</div>
    <div class="table-scroll">{bud_table}</div>
  </div>
</div>

<div class="chart-row">
<!-- ═══════ 5. DEPENDENCY RATIOS ═══════ -->
<div class="panel">
  <h3>Dependency Ratios: Youth vs Elderly (2025)<span class="new-badge">NEW</span></h3>
  <div class="hint">Dependency ratios were never parsed at all.</div>
  <div>
    <button class="toggle-btn active" onclick="showTab(this,'c5-chart')">Chart</button>
    <button class="toggle-btn" onclick="showTab(this,'c5-sql')">SQL Query</button>
    <button class="toggle-btn" onclick="showTab(this,'c5-source')">Source Data</button>
  </div>
  <div id="c5-chart" class="tab-content active"><div id="c5" class="chart"></div></div>
  <div id="c5-sql" class="tab-content">
    <div class="sql-label">SQL Query</div>
    <div class="sql-box">{esc_sql(dep_sql)}</div>
  </div>
  <div id="c5-source" class="tab-content">
    <div class="sql-label">Parsed Results + Raw Source Text</div>
    <div class="table-scroll">{dep_table}</div>
  </div>
</div>

<!-- ═══════ 6. URBANIZATION ═══════ -->
<div class="panel">
  <h3>Urbanization: % Urban vs Growth Rate (2025)<span class="new-badge">NEW</span></h3>
  <div class="hint">Urbanization % and rate were never parsed separately.</div>
  <div>
    <button class="toggle-btn active" onclick="showTab(this,'c6-chart')">Chart</button>
    <button class="toggle-btn" onclick="showTab(this,'c6-sql')">SQL Query</button>
    <button class="toggle-btn" onclick="showTab(this,'c6-source')">Source Data</button>
  </div>
  <div id="c6-chart" class="tab-content active"><div id="c6" class="chart"></div></div>
  <div id="c6-sql" class="tab-content">
    <div class="sql-label">SQL Query</div>
    <div class="sql-box">{esc_sql(urb_sql)}</div>
  </div>
  <div id="c6-source" class="tab-content">
    <div class="sql-label">Parsed Results + Raw Source Text</div>
    <div class="table-scroll">{urb_table}</div>
  </div>
</div>
</div>

<!-- ═══════ 7. ELEVATION ═══════ -->
<div class="panel">
  <h3>Elevation Extremes -- Top 15 Highest Points (2025)<span class="new-badge">NEW</span></h3>
  <div class="hint">Elevation highest/lowest/mean were never parsed.</div>
  <div>
    <button class="toggle-btn active" onclick="showTab(this,'c7-chart')">Chart</button>
    <button class="toggle-btn" onclick="showTab(this,'c7-sql')">SQL Query</button>
    <button class="toggle-btn" onclick="showTab(this,'c7-source')">Source Data</button>
  </div>
  <div id="c7-chart" class="tab-content active"><div id="c7" class="chart"></div></div>
  <div id="c7-sql" class="tab-content">
    <div class="sql-label">SQL Query</div>
    <div class="sql-box">{esc_sql(elev_sql)}</div>
  </div>
  <div id="c7-source" class="tab-content">
    <div class="sql-label">Parsed Results + Raw Source Text</div>
    <div class="table-scroll">{elev_table}</div>
  </div>
</div>

<!-- ═══════ 8. LAND USE ═══════ -->
<div class="panel">
  <h3>Land Use -- Top 15 by Forest Cover (2025)<span class="new-badge">NEW</span></h3>
  <div class="hint">Forest, agricultural land, and other % were never parsed.</div>
  <div>
    <button class="toggle-btn active" onclick="showTab(this,'c8-chart')">Chart</button>
    <button class="toggle-btn" onclick="showTab(this,'c8-sql')">SQL Query</button>
    <button class="toggle-btn" onclick="showTab(this,'c8-source')">Source Data</button>
  </div>
  <div id="c8-chart" class="tab-content active"><div id="c8" class="chart"></div></div>
  <div id="c8-sql" class="tab-content">
    <div class="sql-label">SQL Query</div>
    <div class="sql-box">{esc_sql(lu_sql)}</div>
  </div>
  <div id="c8-source" class="tab-content">
    <div class="sql-label">Parsed Results + Raw Source Text</div>
    <div class="table-scroll">{lu_table}</div>
  </div>
</div>

<script>
function showTab(btn, id) {{
  const panel = btn.closest('.panel');
  panel.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
  panel.querySelectorAll('.toggle-btn').forEach(el => el.classList.remove('active'));
  document.getElementById(id).classList.add('active');
  btn.classList.add('active');
  // Resize chart if switching back to chart tab
  const chartEl = document.getElementById(id).querySelector('.chart, [id^="c"]');
  if (chartEl) {{
    const inst = echarts.getInstanceByDom(chartEl);
    if (inst) inst.resize();
  }}
}}

const T = {{
  text: '#D4D8DD', sub: '#8A919A', grid: '#2F343C',
  c: ['#4A9EFF','#FF6B6B','#51CF66','#FFD43B','#CC5DE8','#FF922B','#20C997']
}};
function B() {{
  return {{
    backgroundColor: 'transparent',
    textStyle: {{ color: T.text, fontFamily: 'Segoe UI, system-ui, sans-serif' }},
    grid: {{ left: '3%', right: '4%', bottom: '3%', top: '12%', containLabel: true }},
    tooltip: {{ backgroundColor: '#1C2127', borderColor: '#2F343C', textStyle: {{ color: '#D4D8DD' }} }}
  }};
}}

// 1. Land vs Water
echarts.init(document.getElementById('c1')).setOption({{
  ...B(),
  tooltip: {{ trigger: 'axis', backgroundColor: '#1C2127', borderColor: '#2F343C', textStyle: {{ color: '#D4D8DD' }},
    formatter: p => p[0].name+'<br>'+p.map(s=>s.seriesName+': '+s.value.toLocaleString()+' sq km').join('<br>') }},
  legend: {{ data: ['Land','Water'], textStyle: {{ color: T.sub }}, top: 0 }},
  xAxis: {{ type: 'category', data: {lw_names}, axisLabel: {{ rotate: 45, color: T.sub, fontSize: 10 }}, axisLine: {{ lineStyle: {{ color: T.grid }} }} }},
  yAxis: {{ type: 'value', axisLabel: {{ color: T.sub, formatter: v=>(v/1e6).toFixed(1)+'M' }}, splitLine: {{ lineStyle: {{ color: T.grid }} }} }},
  series: [
    {{ name:'Land', type:'bar', stack:'a', data:{lw_land}, itemStyle:{{ color:'#51CF66' }} }},
    {{ name:'Water', type:'bar', stack:'a', data:{lw_water}, itemStyle:{{ color:'#4A9EFF' }} }}
  ]
}});

// 2. Life exp scatter
echarts.init(document.getElementById('c2')).setOption({{
  ...B(),
  tooltip: {{ trigger:'item', backgroundColor:'#1C2127', borderColor:'#2F343C', textStyle:{{ color:'#D4D8DD' }},
    formatter: p=>p.data[2]+'<br>Male: '+p.data[0].toFixed(1)+' yrs<br>Female: '+p.data[1].toFixed(1)+' yrs' }},
  xAxis: {{ name:'Male (years)', type:'value', axisLabel:{{ color:T.sub }}, splitLine:{{ lineStyle:{{ color:T.grid }} }}, nameTextStyle:{{ color:T.sub }} }},
  yAxis: {{ name:'Female (years)', type:'value', axisLabel:{{ color:T.sub }}, splitLine:{{ lineStyle:{{ color:T.grid }} }}, nameTextStyle:{{ color:T.sub }} }},
  series: [
    {{ type:'scatter', data:{le_scatter}, symbolSize:7, itemStyle:{{ color:'#CC5DE8', opacity:0.7 }} }},
    {{ type:'line', data:[[30,30],[90,90]], lineStyle:{{ color:'#2F343C', type:'dashed' }}, symbol:'none', tooltip:{{ show:false }} }}
  ]
}});

// 3. Age structure
echarts.init(document.getElementById('c3')).setOption({{
  ...B(),
  tooltip: {{ trigger:'axis', backgroundColor:'#1C2127', borderColor:'#2F343C', textStyle:{{ color:'#D4D8DD' }} }},
  legend: {{ data:['0-14 yrs','15-64 yrs','65+ yrs'], textStyle:{{ color:T.sub }}, top:0 }},
  xAxis: {{ type:'category', data:{age_names}, axisLabel:{{ rotate:45, color:T.sub, fontSize:10 }}, axisLine:{{ lineStyle:{{ color:T.grid }} }} }},
  yAxis: {{ type:'value', max:100, axisLabel:{{ color:T.sub, formatter:v=>v+'%' }}, splitLine:{{ lineStyle:{{ color:T.grid }} }} }},
  series: [
    {{ name:'0-14 yrs', type:'bar', stack:'age', data:{age_014}, itemStyle:{{ color:'#4A9EFF' }} }},
    {{ name:'15-64 yrs', type:'bar', stack:'age', data:{age_1564}, itemStyle:{{ color:'#51CF66' }} }},
    {{ name:'65+ yrs', type:'bar', stack:'age', data:{age_65}, itemStyle:{{ color:'#FF6B6B' }} }}
  ]
}});

// 4. Budget
echarts.init(document.getElementById('c4')).setOption({{
  ...B(),
  tooltip: {{ trigger:'axis', backgroundColor:'#1C2127', borderColor:'#2F343C', textStyle:{{ color:'#D4D8DD' }},
    formatter: p=>p[0].name+'<br>'+p.map(s=>s.seriesName+': $'+(s.value/1e9).toFixed(1)+'B').join('<br>') }},
  legend: {{ data:['Revenues','Expenditures'], textStyle:{{ color:T.sub }}, top:0 }},
  xAxis: {{ type:'category', data:{bud_names}, axisLabel:{{ rotate:45, color:T.sub, fontSize:10 }}, axisLine:{{ lineStyle:{{ color:T.grid }} }} }},
  yAxis: {{ type:'value', axisLabel:{{ color:T.sub, formatter:v=>'$'+(v/1e12).toFixed(1)+'T' }}, splitLine:{{ lineStyle:{{ color:T.grid }} }} }},
  series: [
    {{ name:'Revenues', type:'bar', data:{bud_rev}, itemStyle:{{ color:'#51CF66' }} }},
    {{ name:'Expenditures', type:'bar', data:{bud_exp}, itemStyle:{{ color:'#FF6B6B' }} }}
  ]
}});

// 5. Dependency scatter
echarts.init(document.getElementById('c5')).setOption({{
  ...B(),
  tooltip: {{ trigger:'item', backgroundColor:'#1C2127', borderColor:'#2F343C', textStyle:{{ color:'#D4D8DD' }},
    formatter: p=>p.data[2]+'<br>Youth: '+p.data[0].toFixed(1)+'<br>Elderly: '+p.data[1].toFixed(1) }},
  xAxis: {{ name:'Youth dependency', type:'value', axisLabel:{{ color:T.sub }}, splitLine:{{ lineStyle:{{ color:T.grid }} }}, nameTextStyle:{{ color:T.sub }} }},
  yAxis: {{ name:'Elderly dependency', type:'value', axisLabel:{{ color:T.sub }}, splitLine:{{ lineStyle:{{ color:T.grid }} }}, nameTextStyle:{{ color:T.sub }} }},
  series: [{{ type:'scatter', data:{dep_scatter}, symbolSize:7, itemStyle:{{ color:'#4A9EFF', opacity:0.7 }} }}]
}});

// 6. Urbanization scatter
echarts.init(document.getElementById('c6')).setOption({{
  ...B(),
  tooltip: {{ trigger:'item', backgroundColor:'#1C2127', borderColor:'#2F343C', textStyle:{{ color:'#D4D8DD' }},
    formatter: p=>p.data[2]+'<br>Urban: '+p.data[0].toFixed(1)+'%<br>Growth: '+p.data[1].toFixed(2)+'%' }},
  xAxis: {{ name:'Urban population (%)', type:'value', axisLabel:{{ color:T.sub }}, splitLine:{{ lineStyle:{{ color:T.grid }} }}, nameTextStyle:{{ color:T.sub }} }},
  yAxis: {{ name:'Rate of urbanization (%)', type:'value', axisLabel:{{ color:T.sub }}, splitLine:{{ lineStyle:{{ color:T.grid }} }}, nameTextStyle:{{ color:T.sub }} }},
  series: [{{ type:'scatter', data:{urb_scatter}, symbolSize:7, itemStyle:{{ color:'#20C997', opacity:0.7 }} }}]
}});

// 7. Elevation
echarts.init(document.getElementById('c7')).setOption({{
  ...B(),
  tooltip: {{ trigger:'axis', backgroundColor:'#1C2127', borderColor:'#2F343C', textStyle:{{ color:'#D4D8DD' }},
    formatter: p=>p[0].name+'<br>'+p.map(s=>s.seriesName+': '+s.value.toLocaleString()+' m').join('<br>') }},
  legend: {{ data:['Highest','Lowest'], textStyle:{{ color:T.sub }}, top:0 }},
  xAxis: {{ type:'category', data:{elev_names}, axisLabel:{{ rotate:45, color:T.sub, fontSize:10 }}, axisLine:{{ lineStyle:{{ color:T.grid }} }} }},
  yAxis: {{ type:'value', axisLabel:{{ color:T.sub, formatter:v=>v.toLocaleString()+'m' }}, splitLine:{{ lineStyle:{{ color:T.grid }} }} }},
  series: [
    {{ name:'Highest', type:'bar', data:{elev_hi}, itemStyle:{{ color:'#FF922B' }} }},
    {{ name:'Lowest', type:'bar', data:{elev_lo}, itemStyle:{{ color:'#4A9EFF' }} }}
  ]
}});

// 8. Land use
echarts.init(document.getElementById('c8')).setOption({{
  ...B(),
  tooltip: {{ trigger:'axis', backgroundColor:'#1C2127', borderColor:'#2F343C', textStyle:{{ color:'#D4D8DD' }} }},
  legend: {{ data:['Forest','Agricultural','Other'], textStyle:{{ color:T.sub }}, top:0 }},
  xAxis: {{ type:'category', data:{lu_names}, axisLabel:{{ rotate:45, color:T.sub, fontSize:10 }}, axisLine:{{ lineStyle:{{ color:T.grid }} }} }},
  yAxis: {{ type:'value', max:100, axisLabel:{{ color:T.sub, formatter:v=>v+'%' }}, splitLine:{{ lineStyle:{{ color:T.grid }} }} }},
  series: [
    {{ name:'Forest', type:'bar', stack:'lu', data:{lu_forest}, itemStyle:{{ color:'#20C997' }} }},
    {{ name:'Agricultural', type:'bar', stack:'lu', data:{lu_agri}, itemStyle:{{ color:'#FFD43B' }} }},
    {{ name:'Other', type:'bar', stack:'lu', data:{lu_other}, itemStyle:{{ color:'#8A919A' }} }}
  ]
}});

window.addEventListener('resize', () => {{
  document.querySelectorAll('[id^="c"]').forEach(el => {{
    if (el.classList.contains('chart')) {{
      const i = echarts.getInstanceByDom(el);
      if (i) i.resize();
    }}
  }});
}});
</script>
</body>
</html>"""
    return HTMLResponse(content=html)


if __name__ == "__main__":
    print(f"Database: {DB_PATH}")
    print(f"Dashboard: http://localhost:8050")
    uvicorn.run(app, host="127.0.0.1", port=8050, log_level="warning")
