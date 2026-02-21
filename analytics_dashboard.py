#!/usr/bin/env python3
"""
CIA Factbook Archive — Local Analytics Dashboard
Syncs analytics.db from Fly.io and serves a dashboard on localhost:8888.

Usage:
    python analytics_dashboard.py          # sync + open dashboard
    python analytics_dashboard.py --no-sync  # skip sync, use local copy
"""
import http.server
import json
import os
import sqlite3
import subprocess
import sys
import threading
import time
import webbrowser
from datetime import datetime, timedelta

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

PORT = 8888
DB_PATH = os.path.join(os.path.dirname(__file__), "data", "analytics.db")
MAPBOX_TOKEN = os.getenv("MAPBOX_TOKEN", "")
SYNC_INTERVAL = 300  # 5 minutes

# Background sync state
_sync_status = {"last_sync": None, "next_sync": None, "status": "idle", "error": None}
_sync_lock = threading.Lock()
_sync_timer = None


def sync_db():
    """Download analytics.db from Fly.io."""
    with _sync_lock:
        _sync_status["status"] = "syncing"
    print("[*] Syncing analytics.db from Fly.io...")
    bak = DB_PATH + ".bak"
    if os.path.exists(DB_PATH):
        os.replace(DB_PATH, bak)
    try:
        env = os.environ.copy()
        env["MSYS_NO_PATHCONV"] = "1"
        subprocess.run(
            ["flyctl", "ssh", "sftp", "get", "/data/analytics.db", DB_PATH],
            check=True, env=env, capture_output=True, text=True,
        )
        if os.path.exists(bak):
            os.remove(bak)
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with _sync_lock:
            _sync_status["last_sync"] = now
            _sync_status["status"] = "ok"
            _sync_status["error"] = None
        print(f"[+] Synced successfully at {now}")
    except subprocess.CalledProcessError as e:
        msg = e.stderr.strip() if e.stderr else str(e)
        with _sync_lock:
            _sync_status["status"] = "error"
            _sync_status["error"] = msg
        print(f"[!] Sync failed: {msg}")
        if os.path.exists(bak):
            os.replace(bak, DB_PATH)
            print("[*] Using cached local copy")
        elif not os.path.exists(DB_PATH):
            print("[!] No local analytics.db found. Run with Fly.io access.")
            sys.exit(1)


def _background_sync():
    """Background thread: sync DB from Fly.io every SYNC_INTERVAL seconds."""
    global _sync_timer
    while True:
        time.sleep(SYNC_INTERVAL)
        with _sync_lock:
            _sync_status["next_sync"] = datetime.now().strftime("%H:%M:%S")
        try:
            sync_db()
        except Exception as e:
            print(f"[!] Background sync error: {e}")
        with _sync_lock:
            nxt = (datetime.now() + timedelta(seconds=SYNC_INTERVAL)).strftime("%H:%M:%S")
            _sync_status["next_sync"] = nxt


def query_analytics():
    """Query analytics.db and return all dashboard data as JSON."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    data = {}

    # Bot detection: UA patterns + behavioral (high-volume IPs are bots)
    bot_patterns = ['bot', 'crawl', 'spider', 'slurp', 'semrush', 'ahref',
                    'mj12bot', 'dotbot', 'bytespider', 'claudebot', 'gptbot',
                    'wget', 'curl', 'python-requests', 'scrapy', 'httpx']
    ua_clause = " OR ".join([f"lower(user_agent) LIKE '%{b}%'" for b in bot_patterns])

    # Find high-volume IPs (>50 requests = almost certainly automated)
    vol_rows = conn.execute(
        "SELECT ip_hash FROM page_views GROUP BY ip_hash HAVING count(*) > 50"
    ).fetchall()
    high_vol_ips = {r["ip_hash"] for r in vol_rows}

    # Combined bot clause: known UA OR high-volume IP
    if high_vol_ips:
        ip_list = ",".join([f"'{ip}'" for ip in high_vol_ips])
        bot_clause = f"({ua_clause}) OR ip_hash IN ({ip_list})"
    else:
        bot_clause = ua_clause

    # --- Summary KPIs ---
    data["total_views"] = conn.execute("SELECT count(*) FROM page_views").fetchone()[0]
    data["unique_sessions"] = conn.execute("SELECT count(DISTINCT session_id) FROM page_views").fetchone()[0]
    data["unique_ips"] = conn.execute("SELECT count(DISTINCT ip_hash) FROM page_views").fetchone()[0]
    data["date_range"] = {
        "first": conn.execute("SELECT min(timestamp) FROM page_views").fetchone()[0],
        "last": conn.execute("SELECT max(timestamp) FROM page_views").fetchone()[0],
    }
    avg_ms = conn.execute("SELECT avg(response_ms) FROM page_views WHERE response_ms > 0").fetchone()[0]
    data["avg_response_ms"] = round(avg_ms, 1) if avg_ms else 0

    # --- Traffic by hour ---
    rows = conn.execute("""
        SELECT strftime('%Y-%m-%d %H:00', timestamp) AS hour, count(*) AS cnt
        FROM page_views GROUP BY hour ORDER BY hour
    """).fetchall()
    data["traffic_hourly"] = [{"hour": r["hour"], "count": r["cnt"]} for r in rows]

    # --- Traffic by day (with bot/human split) ---
    rows = conn.execute(f"""
        SELECT date(timestamp) AS day, count(*) AS cnt,
               count(DISTINCT session_id) AS sessions,
               count(DISTINCT ip_hash) AS ips,
               round(avg(CASE WHEN response_ms > 0 THEN response_ms END), 1) AS avg_ms,
               sum(CASE WHEN ({bot_clause}) THEN 1 ELSE 0 END) AS bots
        FROM page_views GROUP BY day ORDER BY day
    """).fetchall()
    data["traffic_daily"] = [{"day": r["day"], "count": r["cnt"],
                              "sessions": r["sessions"], "ips": r["ips"],
                              "avg_ms": r["avg_ms"] or 0,
                              "bots": r["bots"],
                              "humans": r["cnt"] - r["bots"]} for r in rows]

    # --- Top pages ---
    rows = conn.execute("""
        SELECT path, count(*) AS cnt, round(avg(response_ms),1) AS avg_ms
        FROM page_views
        GROUP BY path ORDER BY cnt DESC LIMIT 25
    """).fetchall()
    data["top_pages"] = [{"path": r["path"], "count": r["cnt"],
                          "avg_ms": r["avg_ms"]} for r in rows]

    # --- Status codes ---
    rows = conn.execute("""
        SELECT status_code, count(*) AS cnt
        FROM page_views GROUP BY status_code ORDER BY cnt DESC
    """).fetchall()
    data["status_codes"] = [{"code": r["status_code"], "count": r["cnt"]} for r in rows]

    # --- Bot vs Human ---
    bot_count = conn.execute(f"SELECT count(*) FROM page_views WHERE {bot_clause}").fetchone()[0]
    human_count = data["total_views"] - bot_count
    data["bot_vs_human"] = {"bot": bot_count, "human": human_count}

    # --- Bot breakdown ---
    rows = conn.execute(f"""
        SELECT
            CASE
                WHEN lower(user_agent) LIKE '%claudebot%' THEN 'ClaudeBot'
                WHEN lower(user_agent) LIKE '%googlebot%' THEN 'Googlebot'
                WHEN lower(user_agent) LIKE '%bingbot%' THEN 'Bingbot'
                WHEN lower(user_agent) LIKE '%mj12bot%' THEN 'MJ12bot'
                WHEN lower(user_agent) LIKE '%semrush%' THEN 'SemrushBot'
                WHEN lower(user_agent) LIKE '%ahref%' THEN 'AhrefsBot'
                WHEN lower(user_agent) LIKE '%dotbot%' THEN 'DotBot'
                WHEN lower(user_agent) LIKE '%gptbot%' THEN 'GPTBot'
                WHEN lower(user_agent) LIKE '%bytespider%' THEN 'ByteSpider'
                ELSE 'Other Bot'
            END AS bot_name,
            count(*) AS cnt
        FROM page_views
        WHERE {bot_clause}
        GROUP BY bot_name ORDER BY cnt DESC
    """).fetchall()
    data["bot_breakdown"] = [{"name": r["bot_name"], "count": r["cnt"]} for r in rows]

    # --- Suspicious IPs (high-volume or rate-limited) ---
    rows = conn.execute(f"""
        SELECT ip_hash,
               count(*) AS total,
               sum(CASE WHEN status_code = 429 THEN 1 ELSE 0 END) AS rate_limited,
               sum(CASE WHEN status_code = 403 THEN 1 ELSE 0 END) AS banned,
               sum(CASE WHEN status_code >= 400 THEN 1 ELSE 0 END) AS errors,
               min(timestamp) AS first_seen,
               max(timestamp) AS last_seen,
               group_concat(DISTINCT country) AS countries,
               CASE WHEN ({bot_clause}) THEN 1 ELSE 0 END AS is_bot
        FROM page_views
        GROUP BY ip_hash
        HAVING total > 30 OR rate_limited > 0 OR banned > 0
        ORDER BY total DESC LIMIT 25
    """).fetchall()
    data["suspicious_ips"] = [{
        "ip": r["ip_hash"], "total": r["total"],
        "rate_limited": r["rate_limited"], "banned": r["banned"],
        "errors": r["errors"],
        "first": r["first_seen"], "last": r["last_seen"],
        "countries": r["countries"] or "---",
        "is_bot": bool(r["is_bot"]),
    } for r in rows]

    # --- Geographic data ---
    rows = conn.execute("""
        SELECT country, city, latitude, longitude,
               count(*) AS cnt, count(DISTINCT ip_hash) AS ips
        FROM page_views
        WHERE country IS NOT NULL
        GROUP BY country, city
        ORDER BY cnt DESC
    """).fetchall()
    data["geo"] = [{"country": r["country"], "city": r["city"],
                    "lat": r["latitude"], "lon": r["longitude"],
                    "count": r["cnt"], "ips": r["ips"]} for r in rows]

    # --- Geographic by country ---
    rows = conn.execute("""
        SELECT country, count(*) AS cnt, count(DISTINCT ip_hash) AS ips
        FROM page_views WHERE country IS NOT NULL
        GROUP BY country ORDER BY cnt DESC
    """).fetchall()
    data["geo_countries"] = [{"country": r["country"], "count": r["cnt"],
                              "ips": r["ips"]} for r in rows]

    # --- Response time distribution ---
    buckets = [(0, 50), (50, 100), (100, 200), (200, 500), (500, 1000), (1000, 5000), (5000, 99999)]
    rt_dist = []
    for lo, hi in buckets:
        cnt = conn.execute(
            "SELECT count(*) FROM page_views WHERE response_ms >= ? AND response_ms < ?",
            (lo, hi)
        ).fetchone()[0]
        label = f"{lo}-{hi}ms" if hi < 99999 else f"{lo}ms+"
        rt_dist.append({"label": label, "count": cnt})
    data["response_time_dist"] = rt_dist

    # --- Referrers ---
    rows = conn.execute("""
        SELECT referrer, count(*) AS cnt
        FROM page_views WHERE referrer != '' AND referrer IS NOT NULL
        GROUP BY referrer ORDER BY cnt DESC LIMIT 15
    """).fetchall()
    data["referrers"] = [{"referrer": r["referrer"], "count": r["cnt"]} for r in rows]

    # --- Recent page views (last 100) ---
    rows = conn.execute("""
        SELECT timestamp, ip_hash, country, city, path, status_code,
               user_agent, response_ms
        FROM page_views ORDER BY id DESC LIMIT 100
    """).fetchall()
    data["recent"] = [{
        "time": r["timestamp"], "ip": r["ip_hash"],
        "country": r["country"] or "---", "city": r["city"] or "---",
        "path": r["path"], "status": r["status_code"],
        "ua": r["user_agent"][:100] if r["user_agent"] else "",
        "ms": r["response_ms"],
    } for r in rows]

    # --- Visitor timeline (unique IPs per hour with bot flag) ---
    rows = conn.execute(f"""
        SELECT strftime('%Y-%m-%d %H:00', timestamp) AS hour,
               ip_hash,
               CASE WHEN ({bot_clause}) THEN 1 ELSE 0 END AS is_bot
        FROM page_views
    """).fetchall()
    visitor_hours = {}
    for r in rows:
        h = r["hour"]
        if h not in visitor_hours:
            visitor_hours[h] = {"bots": set(), "humans": set()}
        if r["is_bot"]:
            visitor_hours[h]["bots"].add(r["ip_hash"])
        else:
            visitor_hours[h]["humans"].add(r["ip_hash"])
    data["visitor_timeline"] = sorted([
        {"hour": h, "bots": len(v["bots"]), "humans": len(v["humans"])}
        for h, v in visitor_hours.items()
    ], key=lambda x: x["hour"])

    # Pass high-volume IPs to client for table flagging
    data["high_volume_ips"] = list(high_vol_ips)

    # --- Hourly heatmap data (hour of day x day of week) ---
    rows = conn.execute("""
        SELECT cast(strftime('%w', timestamp) AS int) AS dow,
               cast(strftime('%H', timestamp) AS int) AS hod,
               count(*) AS cnt
        FROM page_views GROUP BY dow, hod
    """).fetchall()
    data["heatmap"] = [{"dow": r["dow"], "hour": r["hod"], "count": r["cnt"]} for r in rows]

    conn.close()
    return data


DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Analytics Dashboard // CIA Factbook Archive</title>
<script src="https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js"></script>
<link href="https://api.mapbox.com/mapbox-gl-js/v3.3.0/mapbox-gl.css" rel="stylesheet">
<script src="https://api.mapbox.com/mapbox-gl-js/v3.3.0/mapbox-gl.js"></script>
<style>
  * { margin:0; padding:0; box-sizing:border-box; }
  body { background:#111418; color:#C5CBD3; font-family:-apple-system,'Segoe UI',Roboto,sans-serif; font-size:14px; line-height:1.5; }

  /* ---- Header ---- */
  .header { padding:20px 24px 0; }
  .doc-id { font-family:Consolas,'Courier New',monospace; font-size:0.62rem; color:#5F6B7C; letter-spacing:1.5px; text-transform:uppercase; margin-bottom:6px; }
  .header h1 { font-size:1.2rem; font-weight:600; color:#E4E7EB; margin-bottom:2px; }
  .header .sub { font-size:0.82rem; color:#8F99A8; }
  .doc-rule { border:none; border-top:1px solid #2F343C; margin:12px 0; }
  .doc-rule.double { border-top:3px double #2F343C; }

  /* ---- Filter Bar ---- */
  .filter-bar {
    position:sticky; top:0; z-index:100; background:#111418; border-bottom:1px solid #2F343C;
    padding:10px 24px; display:flex; align-items:center; gap:12px; flex-wrap:wrap;
  }
  .range-btn {
    background:#1C2127; border:1px solid #383E47; border-radius:3px; color:#8F99A8;
    padding:6px 16px; font-size:0.78rem; cursor:pointer; font-weight:600;
    letter-spacing:0.5px; transition:all 0.15s;
  }
  .range-btn:hover { border-color:#2D72D2; color:#C5CBD3; }
  .range-btn.active { background:#2D72D2; border-color:#2D72D2; color:#fff; }
  .filter-bar .spacer { flex:1; }
  .filter-bar select {
    background:#1C2127; border:1px solid #383E47; border-radius:3px; color:#C5CBD3;
    padding:6px 10px; font-size:0.78rem;
  }
  .filter-bar label { font-size:0.68rem; color:#5F6B7C; text-transform:uppercase; letter-spacing:1px; font-weight:600; }
  .sync-btn {
    background:#2D72D2; color:#fff; border:none; border-radius:3px;
    padding:6px 14px; font-size:0.78rem; cursor:pointer; font-weight:600;
  }
  .sync-btn:hover { background:#215DB0; }
  #refresh-status { font-size:0.68rem; color:#5F6B7C; font-family:Consolas,monospace; }

  .container { max-width:1600px; margin:0 auto; padding:0 24px 40px; }

  /* ---- KPI Cards ---- */
  .kpi-grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(140px,1fr)); gap:10px; margin:16px 0; }
  .kpi-card { background:#1C2127; border:1px solid #2F343C; border-radius:4px; padding:14px 16px; text-align:center; }
  .kpi-value { font-size:1.5rem; font-weight:700; color:#E4E7EB; font-variant-numeric:tabular-nums; }
  .kpi-label { font-size:0.65rem; color:#5F6B7C; text-transform:uppercase; letter-spacing:1.2px; margin-top:4px; font-weight:600; }
  .kpi-delta { font-size:0.7rem; margin-top:2px; }
  .kpi-delta.up { color:#29A634; }
  .kpi-delta.down { color:#CD4246; }

  /* ---- Sections ---- */
  .sec { display:flex; align-items:center; gap:10px; margin:28px 0 14px; }
  .sec-num { font-family:Consolas,monospace; font-size:0.68rem; color:#2D72D2; font-weight:700; letter-spacing:1px; }
  .sec-title { font-size:0.72rem; color:#8F99A8; text-transform:uppercase; letter-spacing:1.2px; font-weight:600; }
  .sec-rule { flex:1; border:none; border-top:1px solid #2F343C; }

  /* ---- Charts ---- */
  .chart-grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(420px,1fr)); gap:16px; margin:16px 0; }
  .chart-card { background:#1C2127; border:1px solid #2F343C; border-radius:4px; padding:16px; }
  .chart-card h3 { font-size:0.68rem; font-weight:600; text-transform:uppercase; letter-spacing:1.2px; color:#5F6B7C; margin-bottom:10px; font-family:Consolas,monospace; }
  .chart-box { width:100%; height:300px; }
  .chart-hero { width:100%; height:450px; }
  .chart-tall { width:100%; height:400px; }

  /* ---- Map ---- */
  #visitor-map { width:100%; height:400px; border-radius:4px; }
  .mapboxgl-popup-content { background:#1C2127!important; color:#C5CBD3; border:1px solid #2F343C; border-radius:4px; font-size:0.82rem; padding:8px 12px; }
  .mapboxgl-popup-tip { border-top-color:#1C2127!important; }
  .dark-popup .mapboxgl-popup-content { box-shadow:0 2px 8px rgba(0,0,0,0.5); }

  /* ---- Tables ---- */
  table { width:100%; border-collapse:collapse; font-size:0.8rem; }
  thead th { text-align:left; color:#5F6B7C; font-size:0.65rem; text-transform:uppercase; letter-spacing:1px; padding:8px 10px; border-bottom:2px solid #2F343C; font-weight:700; position:sticky; top:0; background:#1C2127; }
  td { padding:6px 10px; border-bottom:1px solid #252A31; color:#ABB3BF; }
  tr:hover td { background:rgba(45,114,210,0.06); }
  .r { text-align:right; font-variant-numeric:tabular-nums; }
  .mono { font-family:Consolas,'Courier New',monospace; font-size:0.75rem; }
  .bot-tag { background:#CD4246; color:#fff; font-size:0.6rem; padding:2px 6px; border-radius:3px; font-weight:700; letter-spacing:0.5px; }
  .human-tag { background:#29A634; color:#fff; font-size:0.6rem; padding:2px 6px; border-radius:3px; font-weight:700; letter-spacing:0.5px; }
  .warn-tag { background:#D1980B; color:#111418; font-size:0.6rem; padding:2px 6px; border-radius:3px; font-weight:700; }
  .status-ok { color:#29A634; }
  .status-warn { color:#D1980B; }
  .status-err { color:#CD4246; }
  .table-scroll { overflow-x:auto; max-height:500px; overflow-y:auto; border:1px solid #2F343C; border-radius:4px; background:#1C2127; }
  .ip-link { color:#4B97F7; cursor:pointer; text-decoration:underline; text-decoration-style:dotted; }
  .ip-link:hover { color:#2D72D2; }
  .ip-mini-card { background:#252A31; border:1px solid #2F343C; border-radius:4px; padding:8px 12px; text-align:center; }
  .ip-mini-val { font-size:1.1rem; font-weight:700; color:#E4E7EB; font-variant-numeric:tabular-nums; }
  .ip-mini-label { font-size:0.6rem; color:#5F6B7C; text-transform:uppercase; letter-spacing:1px; margin-top:2px; }
  .ip-section-title { font-size:0.65rem; color:#5F6B7C; text-transform:uppercase; letter-spacing:1.2px; font-weight:700; margin-bottom:6px; font-family:Consolas,monospace; }
  .ip-ua-item { font-size:0.75rem; color:#ABB3BF; background:#252A31; border:1px solid #2F343C; border-radius:3px; padding:6px 10px; margin-bottom:4px; word-break:break-all; font-family:Consolas,monospace; }
  .ip-path-row { display:flex; justify-content:space-between; padding:3px 0; border-bottom:1px solid #252A31; font-size:0.78rem; }
  .ip-path-row .cnt { color:#2D72D2; font-weight:700; font-variant-numeric:tabular-nums; }

  /* ---- Responsive ---- */
  @media (max-width:900px) {
    .chart-grid { grid-template-columns:1fr; }
    .chart-hero { height:320px; }
    .chart-box { height:240px; }
    .kpi-grid { grid-template-columns:repeat(3,1fr); }
    .filter-bar { padding:8px 16px; }
    .container { padding:0 16px 40px; }
  }
  @media (max-width:480px) {
    .kpi-grid { grid-template-columns:repeat(2,1fr); }
    .chart-hero { height:260px; }
  }
</style>
</head>
<body>

<div class="header">
  <div class="doc-id">LOCAL INTELLIGENCE // ANALYTICS DASHBOARD // CLASSIFIED</div>
  <h1>CIA Factbook Archive &mdash; Visitor Analytics</h1>
  <div class="sub" id="date-range"></div>
  <hr class="doc-rule double">
</div>

<!-- Filter Bar -->
<div class="filter-bar">
  <button class="range-btn" data-range="24h">24 Hours</button>
  <button class="range-btn active" data-range="7d">7 Days</button>
  <button class="range-btn" data-range="30d">30 Days</button>
  <button class="range-btn" data-range="all">All Time</button>
  <span class="spacer"></span>
  <label>Auto-refresh</label>
  <select id="refresh-interval">
    <option value="0">Off</option>
    <option value="30">30s</option>
    <option value="60">1min</option>
    <option value="300" selected>5min</option>
  </select>
  <span id="refresh-status"></span>
  <span id="sync-status" style="font-size:0.68rem;color:#5F6B7C;font-family:Consolas,monospace;"></span>
  <button class="sync-btn" onclick="syncNow()">Sync Now</button>
</div>

<div class="container">

<!-- KPI Strip -->
<div class="kpi-grid" id="kpis"></div>

<!-- Section 01: Traffic Timeline (HERO) -->
<div class="sec">
  <span class="sec-num">01</span>
  <span class="sec-title">Traffic Timeline &mdash; Page Views</span>
  <hr class="sec-rule">
</div>
<div class="chart-card">
  <h3>Daily Page Views // Human vs Bot Traffic</h3>
  <div class="chart-hero" id="chart-traffic"></div>
</div>

<!-- Section 02: Visitor Activity -->
<div class="sec">
  <span class="sec-num">02</span>
  <span class="sec-title">Visitor Activity &mdash; Unique IPs</span>
  <hr class="sec-rule">
</div>
<div class="chart-card">
  <h3>Unique Visitors Per Hour // Humans (Green) vs Bots (Red)</h3>
  <div class="chart-hero" id="chart-visitors"></div>
</div>

<!-- Section 03: Bot Intelligence -->
<div class="sec">
  <span class="sec-num">03</span>
  <span class="sec-title">Bot Intelligence &amp; Threat Detection</span>
  <hr class="sec-rule">
</div>
<div class="chart-grid">
  <div class="chart-card">
    <h3>Bot vs Human Ratio</h3>
    <div class="chart-box" id="chart-bot-pie"></div>
  </div>
  <div class="chart-card">
    <h3>Bot Breakdown by Identity</h3>
    <div class="chart-box" id="chart-bot-bar"></div>
  </div>
</div>

<!-- Suspicious IPs Table -->
<div style="margin:16px 0;">
  <div class="chart-card">
    <h3>Suspicious IP Activity // Click IP to Investigate</h3>
    <div class="table-scroll" style="max-height:350px;">
      <table>
        <thead>
          <tr>
            <th>IP Hash</th>
            <th class="r">Total Reqs</th>
            <th class="r">429s</th>
            <th class="r">403s</th>
            <th class="r">Errors</th>
            <th>First Seen</th>
            <th>Last Seen</th>
            <th>Country</th>
            <th>Type</th>
          </tr>
        </thead>
        <tbody id="suspicious-body"></tbody>
      </table>
    </div>
  </div>
</div>

<!-- IP Investigation Panel (hidden until click) -->
<div id="ip-panel" style="display:none;margin:16px 0;">
  <div class="chart-card" style="border-color:#2D72D2;">
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:12px;">
      <h3 style="margin:0;">IP Dossier // <span id="ip-panel-hash" style="color:#2D72D2;"></span></h3>
      <button onclick="document.getElementById('ip-panel').style.display='none'" style="background:#383E47;border:none;color:#C5CBD3;padding:4px 12px;border-radius:3px;cursor:pointer;font-size:0.8rem;">Close</button>
    </div>
    <!-- Summary KPIs -->
    <div id="ip-kpis" style="display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:8px;margin-bottom:16px;"></div>
    <!-- Interval Analysis -->
    <div id="ip-interval" style="margin-bottom:16px;"></div>
    <!-- Activity Timeline -->
    <div id="ip-timeline" style="height:200px;margin-bottom:16px;"></div>
    <!-- User Agents -->
    <div id="ip-uas" style="margin-bottom:16px;"></div>
    <!-- Top Paths -->
    <div id="ip-paths" style="margin-bottom:16px;"></div>
    <!-- Recent Requests -->
    <div id="ip-recent" style="max-height:300px;overflow-y:auto;"></div>
  </div>
</div>

<!-- Section 04: Activity Heatmap -->
<div class="sec">
  <span class="sec-num">04</span>
  <span class="sec-title">Activity Heatmap &mdash; Hour of Day vs Day of Week</span>
  <hr class="sec-rule">
</div>
<div class="chart-card">
  <h3>Request Volume by Time Slot</h3>
  <div class="chart-box" id="chart-heatmap" style="height:260px;"></div>
</div>

<!-- Section 05: Visitor Map -->
<div class="sec">
  <span class="sec-num">05</span>
  <span class="sec-title">Geographic Intelligence</span>
  <hr class="sec-rule">
</div>
<div class="chart-card" style="margin:16px 0;">
  <h3>Visitor Origins // Mapbox Globe</h3>
  <div id="visitor-map"></div>
  <div id="geo-note" style="font-size:0.72rem;color:#5F6B7C;margin-top:8px;font-family:Consolas,monospace;"></div>
</div>

<!-- Section 06: Pages & Performance -->
<div class="sec">
  <span class="sec-num">06</span>
  <span class="sec-title">Pages &amp; Performance</span>
  <hr class="sec-rule">
</div>
<div class="chart-grid">
  <div class="chart-card">
    <h3>Top Pages by Volume</h3>
    <div class="chart-tall" id="chart-pages"></div>
  </div>
  <div class="chart-card">
    <h3>Response Time Distribution</h3>
    <div class="chart-box" id="chart-rt"></div>
  </div>
</div>

<!-- Section 07: Status Codes -->
<div class="sec">
  <span class="sec-num">07</span>
  <span class="sec-title">HTTP Status Codes</span>
  <hr class="sec-rule">
</div>
<div class="chart-grid">
  <div class="chart-card">
    <h3>Status Code Distribution</h3>
    <div class="chart-box" id="chart-status"></div>
  </div>
  <div class="chart-card">
    <h3>Referrer Sources</h3>
    <div class="chart-box" id="chart-referrers"></div>
  </div>
</div>

<!-- Section 08: Live Feed -->
<div class="sec">
  <span class="sec-num">08</span>
  <span class="sec-title">Recent Activity Feed &mdash; Last 100 Requests</span>
  <hr class="sec-rule">
</div>
<div class="chart-card" style="margin:16px 0;padding:0;">
  <div class="table-scroll" style="max-height:600px;">
    <table>
      <thead>
        <tr>
          <th>Timestamp (UTC)</th>
          <th>IP</th>
          <th>Country</th>
          <th>City</th>
          <th>Path</th>
          <th class="r">Status</th>
          <th class="r">ms</th>
          <th>Type</th>
          <th>User Agent</th>
        </tr>
      </thead>
      <tbody id="recent-body"></tbody>
    </table>
  </div>
</div>

</div><!-- /container -->

<script>
var D = __DATA__;
var activeRange = '7d';
var charts = {};

/* ---- Theme ---- */
var DG2 = {
  bg:'transparent', text:'#ABB3BF', axis:'#2F343C', split:'#252A31', label:'#8F99A8',
  palette:['#2D72D2','#29A634','#D1980B','#D33D17','#9D3F9D','#00A396','#DB2C6F','#7961DB'],
  tooltip:{ backgroundColor:'#1C2127', borderColor:'#2F343C', textStyle:{ color:'#C5CBD3', fontSize:12 } },
};

function mkChart(id) {
  var el = document.getElementById(id);
  if (!el) return null;
  var c = echarts.init(el, null, { renderer:'canvas' });
  new ResizeObserver(function() { c.resize(); }).observe(el);
  charts[id] = c;
  return c;
}

var botPatterns = ['bot','crawl','spider','slurp','semrush','ahref','mj12bot',
  'dotbot','bytespider','claudebot','gptbot','wget','curl','python-requests','scrapy','httpx'];
var highVolIPs = new Set(D.high_volume_ips || []);
function isBot(ua, ip) {
  if (ip && highVolIPs.has(ip)) return true;
  var low = (ua || '').toLowerCase();
  return botPatterns.some(function(p) { return low.indexOf(p) >= 0; });
}

function fmtNum(n) { return Number(n).toLocaleString(); }

/* ---- Time Range Filtering ---- */
function getCutoff(range) {
  if (range === 'all' || !D.traffic_daily.length) return '1970-01-01';
  var last = D.traffic_daily[D.traffic_daily.length - 1].day;
  var d = new Date(last + 'T23:59:59');
  var days = range === '24h' ? 1 : range === '7d' ? 7 : 30;
  d.setDate(d.getDate() - days);
  return d.toISOString().substring(0, 10);
}

function filterDaily(range) {
  var cutoff = getCutoff(range);
  return D.traffic_daily.filter(function(d) { return d.day >= cutoff; });
}

function filterHourly(range) {
  var cutoff = getCutoff(range);
  return D.traffic_hourly.filter(function(d) { return d.hour >= cutoff; });
}

function filterVisitors(range) {
  var cutoff = getCutoff(range);
  return D.visitor_timeline.filter(function(d) { return d.hour >= cutoff; });
}

/* ---- KPI Update ---- */
function updateKPIs(daily) {
  var views = 0, sessions = 0, bots = 0, humans = 0, msSum = 0, msCount = 0;
  daily.forEach(function(d) {
    views += d.count;
    sessions += d.sessions;
    bots += d.bots;
    humans += d.humans;
    if (d.avg_ms > 0) { msSum += d.avg_ms * d.count; msCount += d.count; }
  });
  var avgMs = msCount > 0 ? Math.round(msSum / msCount) : 0;
  var days = daily.length || 1;
  var viewsPerDay = Math.round(views / days);

  var kpis = [
    ['Page Views', fmtNum(views), ''],
    ['Views / Day', fmtNum(viewsPerDay), ''],
    ['Sessions', fmtNum(sessions), ''],
    ['Avg Response', avgMs + 'ms', ''],
    ['Humans', fmtNum(humans), 'up'],
    ['Bots', fmtNum(bots), bots > humans ? 'down' : ''],
  ];
  var html = '';
  kpis.forEach(function(k) {
    html += '<div class="kpi-card"><div class="kpi-value">' + k[1] + '</div>';
    html += '<div class="kpi-label">' + k[0] + '</div></div>';
  });
  document.getElementById('kpis').innerHTML = html;
}

/* ---- Traffic Chart ---- */
function renderTraffic(range) {
  var useHourly = (range === '24h');
  var src = useHourly ? filterHourly(range) : filterDaily(range);
  var c = charts['chart-traffic'] || mkChart('chart-traffic');
  if (!c) return;

  if (useHourly) {
    c.setOption({
      grid:{ top:10, right:20, bottom:50, left:60 },
      xAxis:{ type:'category', data:src.map(function(d){ return d.hour; }), boundaryGap:false,
              axisLabel:{ color:DG2.label, fontSize:9, rotate:45 }, axisLine:{ lineStyle:{ color:DG2.axis } } },
      yAxis:{ type:'value', splitLine:{ lineStyle:{ color:DG2.split } }, axisLabel:{ color:DG2.label } },
      series:[{ type:'line', data:src.map(function(d){ return d.count; }), smooth:true, showSymbol:false,
                lineStyle:{ color:'#2D72D2', width:2 },
                areaStyle:{ color:{ type:'linear', x:0,y:0,x2:0,y2:1, colorStops:[{offset:0,color:'rgba(45,114,210,0.35)'},{offset:1,color:'rgba(45,114,210,0.03)'}] } } }],
      tooltip:Object.assign({ trigger:'axis' }, DG2.tooltip),
      legend:{ show:false },
    }, true);
  } else {
    c.setOption({
      grid:{ top:30, right:20, bottom:50, left:60 },
      legend:{ data:['Humans','Bots'], textStyle:{ color:DG2.label, fontSize:11 }, top:0 },
      xAxis:{ type:'category', data:src.map(function(d){ return d.day; }), boundaryGap:false,
              axisLabel:{ color:DG2.label, fontSize:10, rotate:30 }, axisLine:{ lineStyle:{ color:DG2.axis } } },
      yAxis:{ type:'value', splitLine:{ lineStyle:{ color:DG2.split } }, axisLabel:{ color:DG2.label } },
      series:[
        { name:'Humans', type:'line', stack:'t', data:src.map(function(d){ return d.humans; }),
          smooth:true, showSymbol:false, lineStyle:{ width:1.5, color:'#29A634' },
          areaStyle:{ color:{ type:'linear', x:0,y:0,x2:0,y2:1, colorStops:[{offset:0,color:'rgba(41,166,52,0.4)'},{offset:1,color:'rgba(41,166,52,0.05)'}] } } },
        { name:'Bots', type:'line', stack:'t', data:src.map(function(d){ return d.bots; }),
          smooth:true, showSymbol:false, lineStyle:{ width:1.5, color:'#CD4246' },
          areaStyle:{ color:{ type:'linear', x:0,y:0,x2:0,y2:1, colorStops:[{offset:0,color:'rgba(205,66,70,0.4)'},{offset:1,color:'rgba(205,66,70,0.05)'}] } } },
      ],
      tooltip:Object.assign({ trigger:'axis' }, DG2.tooltip),
    }, true);
  }
}

/* ---- Visitor Timeline ---- */
function renderVisitors(range) {
  var vt = filterVisitors(range);
  var c = charts['chart-visitors'] || mkChart('chart-visitors');
  if (!c) return;

  /* For 7d+ ranges, aggregate hourly to daily */
  var data;
  if (range === '24h') {
    data = { labels: vt.map(function(d){ return d.hour.substring(11); }),
             humans: vt.map(function(d){ return d.humans; }),
             bots: vt.map(function(d){ return d.bots; }) };
  } else {
    var daily = {};
    vt.forEach(function(v) {
      var day = v.hour.substring(0, 10);
      if (!daily[day]) daily[day] = { humans:0, bots:0 };
      daily[day].humans += v.humans;
      daily[day].bots += v.bots;
    });
    var days = Object.keys(daily).sort();
    data = { labels: days,
             humans: days.map(function(d){ return daily[d].humans; }),
             bots: days.map(function(d){ return daily[d].bots; }) };
  }

  c.setOption({
    grid:{ top:30, right:20, bottom:50, left:60 },
    legend:{ data:['Humans','Bots'], textStyle:{ color:DG2.label, fontSize:11 }, top:0 },
    xAxis:{ type:'category', data:data.labels, boundaryGap:false,
            axisLabel:{ color:DG2.label, fontSize:10, rotate:30 }, axisLine:{ lineStyle:{ color:DG2.axis } } },
    yAxis:{ type:'value', name:'Unique IPs', nameTextStyle:{ color:DG2.label, fontSize:10 },
            splitLine:{ lineStyle:{ color:DG2.split } }, axisLabel:{ color:DG2.label } },
    series:[
      { name:'Humans', type:'line', stack:'v', data:data.humans,
        smooth:true, showSymbol:false, lineStyle:{ width:1.5, color:'#29A634' },
        areaStyle:{ color:{ type:'linear', x:0,y:0,x2:0,y2:1, colorStops:[{offset:0,color:'rgba(41,166,52,0.45)'},{offset:1,color:'rgba(41,166,52,0.05)'}] } } },
      { name:'Bots', type:'line', stack:'v', data:data.bots,
        smooth:true, showSymbol:false, lineStyle:{ width:1.5, color:'#CD4246' },
        areaStyle:{ color:{ type:'linear', x:0,y:0,x2:0,y2:1, colorStops:[{offset:0,color:'rgba(205,66,70,0.45)'},{offset:1,color:'rgba(205,66,70,0.05)'}] } } },
    ],
    tooltip:Object.assign({ trigger:'axis' }, DG2.tooltip),
  }, true);
}

/* ---- Apply Filter ---- */
function applyFilter(range) {
  activeRange = range;
  document.querySelectorAll('.range-btn').forEach(function(b) {
    b.classList.toggle('active', b.dataset.range === range);
  });
  var daily = filterDaily(range);
  updateKPIs(daily);
  renderTraffic(range);
  renderVisitors(range);
}

/* ---- Static Charts (don't filter) ---- */
function renderStaticCharts() {
  /* Bot Pie */
  var c = mkChart('chart-bot-pie');
  if (c) c.setOption({
    series:[{ type:'pie', radius:['40%','70%'], center:['50%','55%'],
      data:[
        { name:'Humans', value:D.bot_vs_human.human, itemStyle:{ color:'#29A634' } },
        { name:'Bots', value:D.bot_vs_human.bot, itemStyle:{ color:'#CD4246' } },
      ],
      label:{ color:DG2.text, fontSize:12, formatter:'{b}: {c} ({d}%)' },
    }],
    tooltip:DG2.tooltip,
  });

  /* Bot Breakdown */
  var bb = D.bot_breakdown;
  if (bb.length) {
    c = mkChart('chart-bot-bar');
    if (c) c.setOption({
      grid:{ top:10, right:16, bottom:30, left:100 },
      xAxis:{ type:'value', splitLine:{ lineStyle:{ color:DG2.split } }, axisLabel:{ color:DG2.label } },
      yAxis:{ type:'category', data:bb.map(function(d){ return d.name; }).reverse(),
              axisLabel:{ color:DG2.label, fontSize:10 } },
      series:[{ type:'bar', data:bb.map(function(d){ return d.count; }).reverse(),
                itemStyle:{ color:'#CD4246' }, barMaxWidth:20 }],
      tooltip:Object.assign({ trigger:'axis', axisPointer:{ type:'shadow' } }, DG2.tooltip),
    });
  }

  /* Top Pages */
  var tp = D.top_pages.slice(0, 15);
  c = mkChart('chart-pages');
  if (c) c.setOption({
    grid:{ top:10, right:60, bottom:30, left:200 },
    xAxis:{ type:'value', splitLine:{ lineStyle:{ color:DG2.split } }, axisLabel:{ color:DG2.label } },
    yAxis:{ type:'category', data:tp.map(function(d){ return d.path; }).reverse(),
            axisLabel:{ color:DG2.label, fontSize:10, width:190, overflow:'truncate' } },
    series:[{ type:'bar', data:tp.map(function(d){ return d.count; }).reverse(),
              itemStyle:{ color:'#2D72D2' }, barMaxWidth:18,
              label:{ show:true, position:'right', color:DG2.label, fontSize:10 } }],
    tooltip:Object.assign({ trigger:'axis', axisPointer:{ type:'shadow' },
      formatter:function(p) {
        var idx = tp.length - 1 - p[0].dataIndex;
        return '<b>' + tp[idx].path + '</b><br>' + fmtNum(tp[idx].count) + ' views, ' + (tp[idx].avg_ms || 0) + 'ms avg';
      } }, DG2.tooltip),
  });

  /* Response Time */
  var rt = D.response_time_dist;
  c = mkChart('chart-rt');
  if (c) c.setOption({
    grid:{ top:10, right:16, bottom:30, left:50 },
    xAxis:{ type:'category', data:rt.map(function(d){ return d.label; }),
            axisLabel:{ color:DG2.label, fontSize:10 }, axisLine:{ lineStyle:{ color:DG2.axis } } },
    yAxis:{ type:'value', splitLine:{ lineStyle:{ color:DG2.split } }, axisLabel:{ color:DG2.label } },
    series:[{ type:'bar', data:rt.map(function(d){ return d.count; }),
              itemStyle:{ color:'#D1980B' }, barMaxWidth:40 }],
    tooltip:Object.assign({ trigger:'axis' }, DG2.tooltip),
  });

  /* Status Codes */
  var sc = D.status_codes;
  if (sc.length) {
    var statusColors = { 200:'#29A634', 304:'#29A634', 301:'#2D72D2', 302:'#2D72D2',
                         404:'#D1980B', 429:'#CD4246', 403:'#CD4246', 500:'#9D3F9D' };
    c = mkChart('chart-status');
    if (c) c.setOption({
      series:[{ type:'pie', radius:['35%','65%'], center:['50%','55%'],
        data:sc.map(function(s) {
          return { name:s.code + '', value:s.count,
                   itemStyle:{ color:statusColors[s.code] || '#5F6B7C' } };
        }),
        label:{ color:DG2.text, fontSize:11, formatter:'{b}: {c}' },
      }],
      tooltip:DG2.tooltip,
    });
  }

  /* Referrers */
  var refs = D.referrers;
  if (refs.length) {
    c = mkChart('chart-referrers');
    if (c) c.setOption({
      grid:{ top:10, right:16, bottom:30, left:180 },
      xAxis:{ type:'value', splitLine:{ lineStyle:{ color:DG2.split } }, axisLabel:{ color:DG2.label } },
      yAxis:{ type:'category', data:refs.slice(0,10).map(function(d){
                var r = d.referrer; return r.length > 40 ? r.substring(0,40) + '...' : r;
              }).reverse(),
              axisLabel:{ color:DG2.label, fontSize:9 } },
      series:[{ type:'bar', data:refs.slice(0,10).map(function(d){ return d.count; }).reverse(),
                itemStyle:{ color:'#00A396' }, barMaxWidth:16 }],
      tooltip:Object.assign({ trigger:'axis', axisPointer:{ type:'shadow' } }, DG2.tooltip),
    });
  }

  /* Heatmap */
  var hm = D.heatmap;
  if (hm.length) {
    var days = ['Sun','Mon','Tue','Wed','Thu','Fri','Sat'];
    var hours = [];
    for (var i = 0; i < 24; i++) hours.push(i + ':00');
    var hmData = hm.map(function(d) { return [d.hour, d.dow, d.count]; });
    var maxVal = Math.max.apply(null, hm.map(function(d) { return d.count; }));
    c = mkChart('chart-heatmap');
    if (c) c.setOption({
      grid:{ top:10, right:20, bottom:30, left:60 },
      xAxis:{ type:'category', data:hours, axisLabel:{ color:DG2.label, fontSize:9 },
              splitArea:{ show:true, areaStyle:{ color:['transparent','rgba(255,255,255,0.02)'] } } },
      yAxis:{ type:'category', data:days, axisLabel:{ color:DG2.label, fontSize:10 } },
      visualMap:{ min:0, max:maxVal || 1, calculable:false, orient:'horizontal',
                  left:'center', bottom:0, show:false,
                  inRange:{ color:['#1C2127','#183B6B','#2D72D2','#4B97F7'] } },
      series:[{ type:'heatmap', data:hmData, label:{ show:false },
                emphasis:{ itemStyle:{ shadowBlur:6, shadowColor:'rgba(45,114,210,0.5)' } } }],
      tooltip:Object.assign({
        formatter:function(p) { return days[p.value[1]] + ' ' + hours[p.value[0]] + '<br><b>' + p.value[2] + '</b> requests'; }
      }, DG2.tooltip),
    });
  }
}

/* ---- Suspicious IPs Table ---- */
function renderSuspicious() {
  var tbody = document.getElementById('suspicious-body');
  if (!tbody || !D.suspicious_ips) return;
  var html = '';
  D.suspicious_ips.forEach(function(s) {
    var tag = s.is_bot ? '<span class="bot-tag">BOT</span>' : (s.banned > 0 || s.rate_limited > 0 ? '<span class="warn-tag">SUSPECT</span>' : '<span class="human-tag">HUMAN</span>');
    html += '<tr>' +
      '<td class="mono"><span class="ip-link" onclick="investigateIP(\\'' + s.ip + '\\')">' + s.ip + '</span></td>' +
      '<td class="r">' + fmtNum(s.total) + '</td>' +
      '<td class="r ' + (s.rate_limited > 0 ? 'status-warn' : '') + '">' + s.rate_limited + '</td>' +
      '<td class="r ' + (s.banned > 0 ? 'status-err' : '') + '">' + s.banned + '</td>' +
      '<td class="r">' + s.errors + '</td>' +
      '<td class="mono" style="font-size:0.7rem;">' + (s.first || '') + '</td>' +
      '<td class="mono" style="font-size:0.7rem;">' + (s.last || '') + '</td>' +
      '<td>' + s.countries + '</td>' +
      '<td>' + tag + '</td></tr>';
  });
  tbody.innerHTML = html;
}

/* ---- Recent Activity Table ---- */
function renderRecent() {
  var tbody = document.getElementById('recent-body');
  if (!tbody) return;
  var html = '';
  D.recent.forEach(function(r) {
    var bot = isBot(r.ua, r.ip);
    var sc = r.status >= 500 ? 'status-err' : r.status >= 400 ? 'status-warn' : 'status-ok';
    html += '<tr>' +
      '<td class="mono" style="font-size:0.7rem;white-space:nowrap;">' + (r.time || '') + '</td>' +
      '<td class="mono" style="font-size:0.7rem;">' + r.ip + '</td>' +
      '<td>' + r.country + '</td>' +
      '<td style="font-size:0.78rem;">' + r.city + '</td>' +
      '<td style="max-width:250px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">' + r.path + '</td>' +
      '<td class="r ' + sc + '">' + r.status + '</td>' +
      '<td class="r">' + (r.ms ? r.ms.toFixed(0) : '-') + '</td>' +
      '<td>' + (bot ? (highVolIPs.has(r.ip) ? '<span class="warn-tag">SUSPECT</span>' : '<span class="bot-tag">BOT</span>') : '<span class="human-tag">HUMAN</span>') + '</td>' +
      '<td style="font-size:0.68rem;color:#5F6B7C;max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">' + r.ua + '</td></tr>';
  });
  tbody.innerHTML = html;
}

/* ---- Visitor Map ---- */
function renderMap() {
  mapboxgl.accessToken = '__MAPBOX_TOKEN__';
  var map = new mapboxgl.Map({
    container:'visitor-map', style:'mapbox://styles/mapbox/dark-v11',
    center:[0,30], zoom:1.8, projection:'globe',
  });
  map.addControl(new mapboxgl.NavigationControl({ showCompass:true }), 'top-right');

  var geo = D.geo;
  if (!geo.length) {
    document.getElementById('geo-note').textContent = 'No geolocation data available.';
    return;
  }

  map.on('load', function() {
    var features = geo.filter(function(g){ return g.lat && g.lon; }).map(function(g) {
      return { type:'Feature', geometry:{ type:'Point', coordinates:[g.lon,g.lat] },
               properties:{ city:g.city||'Unknown', country:g.country, count:g.count, ips:g.ips } };
    });
    map.addSource('visitors', { type:'geojson', data:{ type:'FeatureCollection', features:features } });
    map.addLayer({ id:'visitor-glow', type:'circle', source:'visitors',
      paint:{ 'circle-radius':['interpolate',['linear'],['get','count'],1,6,10,14,50,22,200,30],
              'circle-color':'#2D72D2', 'circle-opacity':0.25, 'circle-blur':0.8 } });
    map.addLayer({ id:'visitor-dots', type:'circle', source:'visitors',
      paint:{ 'circle-radius':['interpolate',['linear'],['get','count'],1,3,10,6,50,10,200,14],
              'circle-color':'#2D72D2', 'circle-opacity':0.85,
              'circle-stroke-width':1, 'circle-stroke-color':'#4B97F7' } });
    map.on('click', 'visitor-dots', function(e) {
      var p = e.features[0].properties;
      new mapboxgl.Popup({ closeButton:false, className:'dark-popup' })
        .setLngLat(e.lngLat)
        .setHTML('<b>' + p.city + ', ' + p.country + '</b><br>' + p.count + ' views, ' + p.ips + ' unique IPs')
        .addTo(map);
    });
    map.on('mouseenter', 'visitor-dots', function() { map.getCanvas().style.cursor = 'pointer'; });
    map.on('mouseleave', 'visitor-dots', function() { map.getCanvas().style.cursor = ''; });
  });
  document.getElementById('geo-note').textContent = geo.length + ' locations tracked // ' + D.geo_countries.length + ' countries';
}

/* ---- Initialize ---- */
function renderAll() {
  document.getElementById('date-range').textContent =
    'Data: ' + (D.date_range.first || 'N/A') + ' to ' + (D.date_range.last || 'N/A') +
    ' // ' + fmtNum(D.total_views) + ' total page views // ' + fmtNum(D.unique_ips) + ' unique IPs';
  highVolIPs = new Set(D.high_volume_ips || []);
  applyFilter(activeRange);
  renderStaticCharts();
  renderSuspicious();
  renderRecent();
}

try {
  renderAll();
  renderMap();
} catch(e) {
  console.error('[Dashboard init error]', e);
  var errDiv = document.createElement('div');
  errDiv.style.cssText = 'background:#3D1F1F;border:1px solid #CD4246;color:#FA999C;padding:12px 16px;margin:12px 24px;border-radius:4px;font-family:Consolas,monospace;font-size:0.82rem;';
  errDiv.textContent = 'JS Init Error: ' + e.message + ' (line ' + (e.lineNumber || '?') + ')';
  document.querySelector('.container').prepend(errDiv);
}

/* ---- Filter Button Events ---- */
document.querySelectorAll('.range-btn').forEach(function(btn) {
  btn.addEventListener('click', function() { applyFilter(btn.dataset.range); });
});

/* ---- IP Investigation ---- */
function investigateIP(hash) {
  var panel = document.getElementById('ip-panel');
  panel.style.display = 'block';
  document.getElementById('ip-panel-hash').textContent = hash;
  document.getElementById('ip-kpis').innerHTML = '<div style="color:#5F6B7C;">Loading...</div>';
  document.getElementById('ip-interval').innerHTML = '';
  document.getElementById('ip-uas').innerHTML = '';
  document.getElementById('ip-paths').innerHTML = '';
  document.getElementById('ip-recent').innerHTML = '';

  fetch('/api/ip/' + hash)
    .then(function(r) { return r.json(); })
    .then(function(d) {
      if (d.error) { document.getElementById('ip-kpis').innerHTML = '<div style="color:#CD4246;">Not found</div>'; return; }

      /* KPI cards */
      var kpis = [
        ['Total Requests', fmtNum(d.total)],
        ['Unique Paths', fmtNum(d.unique_paths)],
        ['Active Days', d.active_days],
        ['Avg Response', (d.avg_ms || 0) + 'ms'],
        ['200 OK', d.status.ok],
        ['429 Rate-Ltd', d.status.rate_limited],
        ['403 Banned', d.status.banned],
        ['404 Not Found', d.status.not_found],
      ];
      var khtml = '';
      kpis.forEach(function(k) {
        var color = '';
        if (k[0].indexOf('429') >= 0 && k[1] > 0) color = ' style="color:#D1980B;"';
        if (k[0].indexOf('403') >= 0 && k[1] > 0) color = ' style="color:#CD4246;"';
        khtml += '<div class="ip-mini-card"><div class="ip-mini-val"' + color + '>' + k[1] + '</div><div class="ip-mini-label">' + k[0] + '</div></div>';
      });
      document.getElementById('ip-kpis').innerHTML = khtml;

      /* Interval analysis */
      if (d.interval) {
        var verdict = d.interval.avg < 5 ? '<span style="color:#CD4246;font-weight:700;">AUTOMATED (avg ' + d.interval.avg + 's between requests)</span>'
                    : d.interval.avg < 30 ? '<span style="color:#D1980B;font-weight:700;">SUSPICIOUS (avg ' + d.interval.avg + 's between requests)</span>'
                    : '<span style="color:#29A634;">Normal browsing pattern (avg ' + d.interval.avg + 's between requests)</span>';
        document.getElementById('ip-interval').innerHTML =
          '<div class="ip-section-title">Request Pattern Analysis</div>' +
          '<div style="background:#252A31;border:1px solid #2F343C;border-radius:4px;padding:10px 14px;font-size:0.82rem;">' +
          verdict + '<br>' +
          '<span style="color:#8F99A8;">Min: ' + d.interval.min + 's &nbsp; Median: ' + d.interval.median + 's &nbsp; Max: ' + d.interval.max + 's</span>' +
          '<br><span style="color:#5F6B7C;">First: ' + d.first_seen + ' &nbsp; Last: ' + d.last_seen + '</span>' +
          '<br><span style="color:#5F6B7C;">Location: ' + d.cities + ', ' + d.countries + '</span></div>';
      }

      /* Activity timeline chart */
      if (d.hourly && d.hourly.length > 1) {
        var el = document.getElementById('ip-timeline');
        var c = echarts.init(el, null, { renderer:'canvas' });
        new ResizeObserver(function() { c.resize(); }).observe(el);
        c.setOption({
          grid:{ top:10, right:16, bottom:30, left:50 },
          xAxis:{ type:'category', data:d.hourly.map(function(h){ return h.hour; }), boundaryGap:false,
                  axisLabel:{ color:DG2.label, fontSize:9, rotate:30 }, axisLine:{ lineStyle:{ color:DG2.axis } } },
          yAxis:{ type:'value', splitLine:{ lineStyle:{ color:DG2.split } }, axisLabel:{ color:DG2.label } },
          series:[{ type:'line', data:d.hourly.map(function(h){ return h.count; }), smooth:true, showSymbol:false,
                    lineStyle:{ color:'#CD4246', width:2 },
                    areaStyle:{ color:{ type:'linear', x:0,y:0,x2:0,y2:1, colorStops:[{offset:0,color:'rgba(205,66,70,0.3)'},{offset:1,color:'rgba(205,66,70,0.03)'}] } } }],
          tooltip:Object.assign({ trigger:'axis' }, DG2.tooltip),
        });
      }

      /* User Agents */
      if (d.user_agents && d.user_agents.length) {
        var uhtml = '<div class="ip-section-title">User Agents (' + d.user_agents.length + ')</div>';
        d.user_agents.forEach(function(ua) { uhtml += '<div class="ip-ua-item">' + ua + '</div>'; });
        document.getElementById('ip-uas').innerHTML = uhtml;
      }

      /* Top Paths */
      if (d.top_paths && d.top_paths.length) {
        var phtml = '<div class="ip-section-title">Top Paths (of ' + fmtNum(d.unique_paths) + ' unique)</div>';
        d.top_paths.forEach(function(p) {
          phtml += '<div class="ip-path-row"><span>' + p.path + '</span><span class="cnt">' + p.count + '</span></div>';
        });
        document.getElementById('ip-paths').innerHTML = phtml;
      }

      /* Recent Requests */
      if (d.recent && d.recent.length) {
        var rhtml = '<div class="ip-section-title">Last ' + d.recent.length + ' Requests</div><table style="font-size:0.75rem;"><thead><tr><th>Time</th><th>Path</th><th class="r">Status</th><th class="r">ms</th></tr></thead><tbody>';
        d.recent.forEach(function(r) {
          var sc = r.status >= 400 ? 'status-err' : 'status-ok';
          rhtml += '<tr><td class="mono" style="font-size:0.68rem;white-space:nowrap;">' + (r.time||'') + '</td><td style="max-width:300px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">' + r.path + '</td><td class="r ' + sc + '">' + r.status + '</td><td class="r">' + (r.ms ? r.ms.toFixed(0) : '-') + '</td></tr>';
        });
        rhtml += '</tbody></table>';
        document.getElementById('ip-recent').innerHTML = rhtml;
      }

      /* Scroll to panel */
      panel.scrollIntoView({ behavior:'smooth', block:'start' });
    })
    .catch(function(e) {
      document.getElementById('ip-kpis').innerHTML = '<div style="color:#CD4246;">Error: ' + e.message + '</div>';
    });
}

/* ---- AJAX Data Refresh ---- */
function refreshData() {
  var statusEl = document.getElementById('refresh-status');
  statusEl.textContent = 'Refreshing...';
  fetch('/api/data')
    .then(function(r) { return r.json(); })
    .then(function(newData) {
      D = newData;
      try { renderAll(); } catch(e) { console.error('[Refresh error]', e); }
      statusEl.textContent = 'Updated ' + new Date().toLocaleTimeString();
      setTimeout(function() {
        if (!refreshTimer) statusEl.textContent = '';
      }, 5000);
    })
    .catch(function(e) { statusEl.textContent = 'Refresh failed'; console.error(e); });
}

var refreshTimer = null;
document.getElementById('refresh-interval').addEventListener('change', function() {
  if (refreshTimer) { clearInterval(refreshTimer); refreshTimer = null; }
  var secs = parseInt(this.value);
  if (secs > 0) {
    var statusEl = document.getElementById('refresh-status');
    statusEl.textContent = 'Auto-refresh: ' + secs + 's';
    refreshTimer = setInterval(refreshData, secs * 1000);
  } else {
    document.getElementById('refresh-status').textContent = '';
  }
});

/* ---- Sync Status Polling ---- */
function updateSyncStatus() {
  fetch('/api/sync-status')
    .then(function(r) { return r.json(); })
    .then(function(s) {
      var el = document.getElementById('sync-status');
      var parts = [];
      if (s.last_sync) parts.push('Last sync: ' + s.last_sync);
      if (s.next_sync) parts.push('Next: ' + s.next_sync);
      if (s.status === 'syncing') parts.push('SYNCING...');
      if (s.status === 'error') parts.push('ERR: ' + (s.error || '').substring(0, 40));
      el.textContent = parts.join(' // ');
      el.style.color = s.status === 'error' ? '#CD4246' : s.status === 'syncing' ? '#D1980B' : '#5F6B7C';
    }).catch(function(){});
}
updateSyncStatus();
setInterval(updateSyncStatus, 15000);

function syncNow() {
  document.getElementById('sync-status').textContent = 'Triggering sync...';
  document.getElementById('sync-status').style.color = '#D1980B';
  fetch('/api/sync-now').then(function() {
    setTimeout(function() { updateSyncStatus(); refreshData(); }, 8000);
  });
}

/* Start auto-refresh at default 5min */
(function() {
  var sel = document.getElementById('refresh-interval');
  var secs = parseInt(sel.value);
  if (secs > 0) {
    document.getElementById('refresh-status').textContent = 'Auto-refresh: ' + secs + 's';
    refreshTimer = setInterval(refreshData, secs * 1000);
  }
})();
</script>
</body>
</html>"""


def query_ip_detail(ip_hash):
    """Get full dossier on a specific IP hash."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    # Summary
    row = conn.execute("""
        SELECT count(*) AS total,
               count(DISTINCT path) AS unique_paths,
               count(DISTINCT date(timestamp)) AS active_days,
               min(timestamp) AS first_seen,
               max(timestamp) AS last_seen,
               group_concat(DISTINCT country) AS countries,
               group_concat(DISTINCT city) AS cities,
               round(avg(response_ms), 1) AS avg_ms,
               sum(CASE WHEN status_code = 200 THEN 1 ELSE 0 END) AS ok,
               sum(CASE WHEN status_code = 429 THEN 1 ELSE 0 END) AS rate_limited,
               sum(CASE WHEN status_code = 403 THEN 1 ELSE 0 END) AS banned,
               sum(CASE WHEN status_code = 404 THEN 1 ELSE 0 END) AS not_found,
               sum(CASE WHEN status_code >= 500 THEN 1 ELSE 0 END) AS server_err
        FROM page_views WHERE ip_hash = ?
    """, (ip_hash,)).fetchone()

    if not row or row["total"] == 0:
        return None

    result = {
        "ip": ip_hash,
        "total": row["total"], "unique_paths": row["unique_paths"],
        "active_days": row["active_days"],
        "first_seen": row["first_seen"], "last_seen": row["last_seen"],
        "countries": row["countries"] or "---", "cities": row["cities"] or "---",
        "avg_ms": row["avg_ms"] or 0,
        "status": {"ok": row["ok"], "rate_limited": row["rate_limited"],
                   "banned": row["banned"], "not_found": row["not_found"],
                   "server_err": row["server_err"]},
    }

    # User agents
    uas = conn.execute(
        "SELECT DISTINCT user_agent FROM page_views WHERE ip_hash = ? AND user_agent IS NOT NULL",
        (ip_hash,)
    ).fetchall()
    result["user_agents"] = [r["user_agent"] for r in uas]

    # Top paths
    paths = conn.execute("""
        SELECT path, count(*) AS cnt FROM page_views
        WHERE ip_hash = ? GROUP BY path ORDER BY cnt DESC LIMIT 20
    """, (ip_hash,)).fetchall()
    result["top_paths"] = [{"path": r["path"], "count": r["cnt"]} for r in paths]

    # Activity by hour (for timeline)
    hours = conn.execute("""
        SELECT strftime('%Y-%m-%d %H:00', timestamp) AS hour, count(*) AS cnt
        FROM page_views WHERE ip_hash = ? GROUP BY hour ORDER BY hour
    """, (ip_hash,)).fetchall()
    result["hourly"] = [{"hour": r["hour"], "count": r["cnt"]} for r in hours]

    # Request interval analysis
    timestamps = conn.execute(
        "SELECT timestamp FROM page_views WHERE ip_hash = ? ORDER BY timestamp",
        (ip_hash,)
    ).fetchall()
    if len(timestamps) > 1:
        from datetime import datetime
        dts = []
        for t in timestamps:
            try:
                dts.append(datetime.strptime(t["timestamp"][:19], "%Y-%m-%d %H:%M:%S"))
            except (ValueError, TypeError):
                pass
        if len(dts) > 1:
            intervals = [(dts[i+1] - dts[i]).total_seconds() for i in range(len(dts)-1)]
            result["interval"] = {
                "avg": round(sum(intervals) / len(intervals), 1),
                "min": round(min(intervals), 1),
                "max": round(max(intervals), 1),
                "median": round(sorted(intervals)[len(intervals)//2], 1),
            }

    # Recent requests (last 30)
    recent = conn.execute("""
        SELECT timestamp, path, status_code, response_ms
        FROM page_views WHERE ip_hash = ?
        ORDER BY id DESC LIMIT 30
    """, (ip_hash,)).fetchall()
    result["recent"] = [{"time": r["timestamp"], "path": r["path"],
                         "status": r["status_code"], "ms": r["response_ms"]} for r in recent]

    conn.close()
    return result


class DashboardHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            data = query_analytics()
            html = DASHBOARD_HTML.replace("__DATA__", json.dumps(data)).replace("__MAPBOX_TOKEN__", MAPBOX_TOKEN)
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
            self.send_header("Pragma", "no-cache")
            self.end_headers()
            self.wfile.write(html.encode())
        elif self.path.startswith("/api/ip/"):
            ip_hash = self.path.split("/api/ip/")[1]
            detail = query_ip_detail(ip_hash)
            self.send_response(200 if detail else 404)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(json.dumps(detail or {"error": "not found"}).encode())
        elif self.path == "/api/data":
            data = query_analytics()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(json.dumps(data).encode())
        elif self.path == "/api/sync-status":
            with _sync_lock:
                status = dict(_sync_status)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(json.dumps(status).encode())
        elif self.path == "/api/sync-now":
            threading.Thread(target=sync_db, daemon=True).start()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"ok": True}).encode())
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass  # suppress request logs


def main():
    if "--no-sync" not in sys.argv:
        sync_db()

    if not os.path.exists(DB_PATH):
        print("[!] No analytics.db found at", DB_PATH)
        sys.exit(1)

    # Start background sync thread (every 5 minutes)
    if "--no-sync" not in sys.argv:
        nxt = (datetime.now() + timedelta(seconds=SYNC_INTERVAL)).strftime("%H:%M:%S")
        _sync_status["next_sync"] = nxt
        t = threading.Thread(target=_background_sync, daemon=True)
        t.start()
        print(f"[*] Background sync every {SYNC_INTERVAL}s — next at {nxt}")

    print(f"[*] Dashboard: http://localhost:{PORT}")
    webbrowser.open(f"http://localhost:{PORT}")

    server = http.server.HTTPServer(("127.0.0.1", PORT), DashboardHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[*] Shutting down")
        server.shutdown()


if __name__ == "__main__":
    main()
