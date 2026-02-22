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
from urllib.parse import urlparse, parse_qs

# Import shared bot taxonomy (standalone script, so handle import path)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from webapp.bot_taxonomy import (
    get_all_patterns, get_bot_sql_clause, get_bot_sql_case,
    BOT_TAXONOMY, CATEGORY_LABELS, CATEGORY_COLORS,
)

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

    # Bot detection: UA patterns from shared taxonomy + behavioral (high-volume IPs)
    ua_clause = get_bot_sql_clause()

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

    # --- Bot breakdown by category ---
    bot_case = get_bot_sql_case()
    rows = conn.execute(f"""
        SELECT {bot_case} AS bot_category, count(*) AS cnt
        FROM page_views
        WHERE {bot_clause}
        GROUP BY bot_category ORDER BY cnt DESC
    """).fetchall()
    data["bot_breakdown"] = [{"name": r["bot_category"], "count": r["cnt"]} for r in rows]
    data["category_colors"] = CATEGORY_COLORS

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

    # --- Geographic data (with threat classification) ---
    rows = conn.execute(f"""
        SELECT country, city, latitude, longitude,
               count(*) AS cnt, count(DISTINCT ip_hash) AS ips,
               sum(CASE WHEN ({bot_clause}) THEN 1 ELSE 0 END) AS bot_count,
               sum(CASE WHEN status_code = 429 THEN 1 ELSE 0 END) AS rate_limited,
               sum(CASE WHEN status_code = 403 THEN 1 ELSE 0 END) AS banned,
               sum(CASE WHEN status_code >= 400 THEN 1 ELSE 0 END) AS errors,
               count(DISTINCT session_id) AS sessions
        FROM page_views
        WHERE country IS NOT NULL
        GROUP BY country, city
        ORDER BY cnt DESC
    """).fetchall()
    geo_data = []
    for r in rows:
        bot_pct = (r["bot_count"] / r["cnt"] * 100) if r["cnt"] > 0 else 0
        if r["banned"] > 0 or r["rate_limited"] > 5 or bot_pct > 80:
            threat = 3  # Hostile
        elif r["bot_count"] > 0 and (bot_pct > 50 or r["rate_limited"] > 0 or r["cnt"] > 50):
            threat = 2  # Suspicious
        elif r["cnt"] > 20 or bot_pct > 20:
            threat = 1  # Elevated
        else:
            threat = 0  # Normal
        geo_data.append({
            "country": r["country"], "city": r["city"],
            "lat": r["latitude"], "lon": r["longitude"],
            "count": r["cnt"], "ips": r["ips"],
            "bots": r["bot_count"], "rate_limited": r["rate_limited"],
            "banned": r["banned"], "errors": r["errors"],
            "sessions": r["sessions"], "threat": threat,
        })
    data["geo"] = geo_data

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
  *{margin:0;padding:0;box-sizing:border-box;}
  body{background:#111418;color:#ABB3BF;font-family:'Segoe UI',system-ui,-apple-system,sans-serif;font-size:13px;line-height:1.5;overflow-y:auto;min-height:100vh;}

  /* Shell */
  .shell{max-width:1600px;margin:0 auto;padding:0 16px 40px;}

  /* Header */
  .hdr{position:sticky;top:0;z-index:50;display:flex;align-items:center;justify-content:space-between;padding:8px 16px;background:#1C2127;border-bottom:1px solid #2F343C;}
  .hdr-left{display:flex;align-items:baseline;gap:16px;}
  .hdr-id{font-family:Consolas,monospace;font-size:0.55rem;color:#5C7080;letter-spacing:2px;}
  .hdr h1{font-size:0.85rem;font-weight:600;color:#E6EDF3;white-space:nowrap;}
  .hdr-right{display:flex;align-items:center;gap:6px;}
  .rbtn{background:transparent;border:1px solid #2F343C;border-radius:3px;color:#ABB3BF;padding:3px 10px;font-size:0.65rem;cursor:pointer;font-weight:700;letter-spacing:0.5px;transition:all 0.15s;}
  .rbtn:hover{border-color:#2D72D2;color:#E6EDF3;}
  .rbtn.active{background:#2D72D2;border-color:#2D72D2;color:#fff;}
  .hdr select{background:#111418;border:1px solid #2F343C;border-radius:3px;color:#ABB3BF;padding:3px 6px;font-size:0.65rem;}
  .hdr .si{font-size:0.58rem;color:#5C7080;font-family:Consolas,monospace;}
  .sync-btn{background:#238551;color:#fff;border:none;border-radius:3px;padding:3px 10px;font-size:0.65rem;cursor:pointer;font-weight:700;letter-spacing:0.5px;}
  .sync-btn:hover{background:#29A634;}

  /* KPI Strip */
  .kpi-strip{display:flex;background:#1C2127;margin-top:12px;border-radius:4px;border:1px solid #2F343C;overflow:hidden;}
  .kpi-cell{flex:1;padding:8px 10px;text-align:center;border-right:1px solid #2F343C;}
  .kpi-cell:last-child{border-right:none;}
  .kpi-val{font-size:1.15rem;font-weight:700;color:#E6EDF3;font-variant-numeric:tabular-nums;}
  .kpi-lbl{font-size:0.5rem;color:#5C7080;text-transform:uppercase;letter-spacing:1.5px;font-weight:700;margin-top:2px;}
  .kpi-bar{height:2px;background:#252A31;margin-top:4px;border-radius:1px;overflow:hidden;}
  .kpi-bar-fill{height:100%;border-radius:1px;transition:width 0.3s;}

  /* Map Section */
  .map-section{height:550px;position:relative;margin-top:12px;border-radius:4px;overflow:hidden;border:1px solid #2F343C;background:#111418;}
  #visitor-map{width:100%;height:100%;}
  .mc{position:absolute;top:8px;left:10px;z-index:5;display:flex;gap:4px;}
  .mt{border:none;border-radius:3px;color:#fff;padding:2px 6px;font-size:0.52rem;cursor:pointer;font-weight:800;letter-spacing:0.5px;opacity:0.3;transition:opacity 0.15s;}
  .mt.active{opacity:1;}
  .mp{position:absolute;top:0;right:0;width:340px;height:100%;background:rgba(17,20,24,0.95);border-left:1px solid #2F343C;z-index:10;transform:translateX(100%);transition:transform 0.2s ease;overflow-y:auto;padding:12px;}
  .mp.open{transform:translateX(0);}
  .mp-x{position:absolute;top:6px;right:6px;background:#2F343C;border:none;color:#ABB3BF;width:20px;height:20px;border-radius:3px;cursor:pointer;font-size:0.85rem;display:flex;align-items:center;justify-content:center;}
  .mp-x:hover{background:#CD4246;}
  .mp h4{font-size:0.85rem;color:#E6EDF3;font-weight:600;margin:0 0 4px;padding-right:28px;}
  .mp .sub{font-size:0.65rem;color:#5C7080;margin-bottom:10px;}
  .mapboxgl-popup-content{background:#1C2127!important;color:#ABB3BF;border:1px solid #2F343C;border-radius:4px;font-size:0.75rem;padding:8px 12px;}
  .mapboxgl-popup-tip{border-top-color:#1C2127!important;}

  /* Sections */
  .section{background:#1C2127;border:1px solid #2F343C;border-radius:4px;margin-top:12px;overflow:hidden;}
  .section-header{font:700 0.6rem Consolas,'Courier New',monospace;color:#5C7080;letter-spacing:2px;text-transform:uppercase;padding:10px 14px 0;flex-shrink:0;}
  .chart-body{padding:4px 10px 8px;}
  .chart-body > div{width:100%;height:100%;}

  /* Multi-column rows */
  .row-2{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:12px;}
  .row-3{display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px;margin-top:12px;}
  .row-2 > .section,.row-3 > .section{margin-top:0;}

  /* Threat */
  .tb{display:inline-block;padding:2px 8px;border-radius:3px;font-size:0.52rem;font-weight:800;letter-spacing:0.5px;}
  .t0{background:#238551;color:#fff;} .t1{background:#D1980B;color:#111418;} .t2{background:#EC9A3C;color:#111418;} .t3{background:#CD4246;color:#fff;}

  /* Tags */
  .tag-bot{background:#CD4246;color:#fff;font-size:0.52rem;padding:2px 5px;border-radius:3px;font-weight:800;}
  .tag-human{background:#238551;color:#fff;font-size:0.52rem;padding:2px 5px;border-radius:3px;font-weight:800;}
  .tag-warn{background:#D1980B;color:#111418;font-size:0.52rem;padding:2px 5px;border-radius:3px;font-weight:800;}

  /* Tables */
  table{width:100%;border-collapse:collapse;font-size:0.72rem;}
  thead th{text-align:left;color:#5C7080;font-size:0.52rem;text-transform:uppercase;letter-spacing:0.8px;padding:4px 6px;border-bottom:1px solid #2F343C;font-weight:800;position:sticky;top:0;background:#1C2127;cursor:pointer;white-space:nowrap;user-select:none;}
  thead th:hover{color:#ABB3BF;}
  thead th.sorted{color:#2D72D2;}
  td{padding:3px 6px;border-bottom:1px solid rgba(47,52,60,0.5);color:#ABB3BF;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
  tr:hover td{background:rgba(45,114,210,0.06);}
  .r{text-align:right;font-variant-numeric:tabular-nums;}
  .mono{font-family:Consolas,'Courier New',monospace;font-size:0.65rem;}
  .ip-link{color:#2D72D2;cursor:pointer;text-decoration:none;}
  .ip-link:hover{text-decoration:underline;}
  .st-ok{color:#238551;} .st-w{color:#D1980B;} .st-e{color:#CD4246;}
  .table-body{padding:0 8px 8px;}

  /* IP Dossier Overlay */
  .ov{display:none;position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.75);z-index:100;overflow-y:auto;padding:30px;}
  .ov.open{display:flex;align-items:flex-start;justify-content:center;}
  .dossier{background:#1C2127;border:1px solid #2F343C;border-radius:6px;width:100%;max-width:1100px;padding:20px;position:relative;}
  .dossier-x{position:absolute;top:10px;right:10px;background:#2F343C;border:none;color:#ABB3BF;width:26px;height:26px;border-radius:4px;cursor:pointer;font-size:1.1rem;}
  .dossier-x:hover{background:#CD4246;}
  .mc2{background:#111418;border:1px solid #2F343C;border-radius:4px;padding:8px 10px;text-align:center;}
  .mc2v{font-size:0.95rem;font-weight:700;color:#E6EDF3;font-variant-numeric:tabular-nums;}
  .mc2l{font-size:0.48rem;color:#5C7080;text-transform:uppercase;letter-spacing:0.8px;margin-top:2px;font-weight:700;}
  .sec-t{font-size:0.55rem;color:#5C7080;text-transform:uppercase;letter-spacing:1.5px;font-weight:800;margin-bottom:4px;font-family:Consolas,monospace;}
  .ua-item{font-size:0.62rem;color:#ABB3BF;background:#111418;border:1px solid #2F343C;border-radius:3px;padding:4px 8px;margin-bottom:3px;word-break:break-all;font-family:Consolas,monospace;}
  .path-row{display:flex;justify-content:space-between;padding:3px 0;border-bottom:1px solid rgba(47,52,60,0.5);font-size:0.68rem;}
  .path-row .c{color:#2D72D2;font-weight:700;font-variant-numeric:tabular-nums;}

  /* Scrollbar */
  ::-webkit-scrollbar{width:6px;height:6px;}
  ::-webkit-scrollbar-track{background:#111418;}
  ::-webkit-scrollbar-thumb{background:#2F343C;border-radius:3px;}
  ::-webkit-scrollbar-thumb:hover{background:#404850;}
</style>
</head>
<body>
<div class="shell">

<!-- Header -->
<div class="hdr">
  <div class="hdr-left">
    <span class="hdr-id">DOC-7741 // ANALYTICS</span>
    <h1>CIA Factbook Archive &mdash; Visitor Intelligence</h1>
    <span class="si" id="date-range"></span>
  </div>
  <div class="hdr-right">
    <button class="rbtn" data-range="24h">24H</button>
    <button class="rbtn active" data-range="7d">7D</button>
    <button class="rbtn" data-range="30d">30D</button>
    <button class="rbtn" data-range="all">ALL</button>
    <span style="width:1px;height:16px;background:#2F343C;display:inline-block;"></span>
    <select id="refresh-interval">
      <option value="0">Off</option>
      <option value="30">30s</option>
      <option value="60">1m</option>
      <option value="300" selected>5m</option>
    </select>
    <span id="refresh-status" class="si"></span>
    <span id="sync-status" class="si"></span>
    <button class="sync-btn" onclick="syncNow()">SYNC</button>
  </div>
</div>

<!-- KPI Strip -->
<div class="kpi-strip" id="kpis"></div>

<!-- Hero: Globe Map -->
<div class="map-section">
  <div class="mc">
    <button class="mt active" data-threat="0" style="background:#238551;" onclick="toggleThreatLayer(0,this)">NRM</button>
    <button class="mt active" data-threat="1" style="background:#D1980B;" onclick="toggleThreatLayer(1,this)">ELV</button>
    <button class="mt active" data-threat="2" style="background:#EC9A3C;" onclick="toggleThreatLayer(2,this)">SUS</button>
    <button class="mt active" data-threat="3" style="background:#CD4246;" onclick="toggleThreatLayer(3,this)">HST</button>
    <button class="mt" style="background:#2D72D2;" id="arc-toggle" onclick="toggleArcs(this)">ARC</button>
  </div>
  <div id="visitor-map"></div>
  <div id="map-panel" class="mp">
    <button class="mp-x" onclick="closeMapPanel()">&times;</button>
    <div id="map-panel-content"></div>
  </div>
  <div id="geo-note" style="position:absolute;bottom:6px;left:10px;font-size:0.55rem;color:#5C7080;font-family:Consolas,monospace;z-index:5;"></div>
</div>

<!-- Section 01: Traffic Timeline -->
<div class="section" style="height:300px;">
  <div class="section-header">01 // Traffic Timeline &mdash; Human vs Bot</div>
  <div class="chart-body" style="height:calc(100% - 30px);"><div id="chart-traffic"></div></div>
</div>

<!-- Row: Bot Intel + Heatmap + Response Time -->
<div class="row-3">
  <div class="section" style="height:280px;">
    <div class="section-header">02 // Bot Intelligence</div>
    <div class="chart-body" style="height:calc(100% - 30px);display:flex;">
      <div id="chart-bot-pie" style="flex:1;min-width:0;"></div>
      <div id="chart-bot-bar" style="flex:1;min-width:0;"></div>
    </div>
  </div>
  <div class="section" style="height:280px;">
    <div class="section-header">03 // Activity Heatmap</div>
    <div class="chart-body" style="height:calc(100% - 30px);"><div id="chart-heatmap"></div></div>
  </div>
  <div class="section" style="height:280px;">
    <div class="section-header">04 // Response Time</div>
    <div class="chart-body" style="height:calc(100% - 30px);"><div id="chart-response"></div></div>
  </div>
</div>

<!-- Section 05: Suspicious IPs -->
<div class="section">
  <div class="section-header">05 // Suspicious IPs &mdash; Click to Investigate</div>
  <div class="table-body" style="max-height:400px;overflow-y:auto;">
    <table>
      <thead><tr>
        <th onclick="sortSusp('ip')">IP Hash</th>
        <th class="r" onclick="sortSusp('total')">Reqs</th>
        <th class="r" onclick="sortSusp('rate_limited')">429</th>
        <th class="r" onclick="sortSusp('banned')">403</th>
        <th onclick="sortSusp('last')">Last Seen</th>
        <th>Type</th>
      </tr></thead>
      <tbody id="suspicious-body"></tbody>
    </table>
  </div>
</div>

<!-- Row: Top Pages + Status & Referrers -->
<div class="row-2">
  <div class="section" style="height:280px;">
    <div class="section-header">06 // Top Pages</div>
    <div class="chart-body" style="height:calc(100% - 30px);"><div id="chart-pages"></div></div>
  </div>
  <div class="section" style="height:280px;">
    <div class="section-header">07 // HTTP Status &amp; Referrers</div>
    <div class="chart-body" style="height:calc(100% - 30px);display:flex;">
      <div id="chart-status" style="flex:1;min-width:0;"></div>
      <div id="chart-referrers" style="flex:1;min-width:0;"></div>
    </div>
  </div>
</div>

<!-- Section 08: Live Feed -->
<div class="section">
  <div class="section-header">08 // Live Feed</div>
  <div class="table-body" style="max-height:350px;overflow-y:auto;">
    <table>
      <thead><tr>
        <th>Time</th>
        <th>IP</th>
        <th>Location</th>
        <th style="max-width:140px;">Path</th>
        <th class="r">Status</th>
        <th>Type</th>
      </tr></thead>
      <tbody id="recent-body"></tbody>
    </table>
  </div>
</div>

</div><!-- /shell -->

<!-- IP Investigation Overlay -->
<div id="ip-overlay" class="ov" onclick="if(event.target===this)closeIPDossier()">
  <div class="dossier">
    <button class="dossier-x" onclick="closeIPDossier()">&times;</button>
    <div id="ip-dossier-content"></div>
  </div>
</div>

<script>
var D = __DATA__;
var activeRange = '7d';
var charts = {};

/* ---- Theme (DG2 Dark) ---- */
var DG2 = {
  bg:'transparent', text:'#ABB3BF', axis:'#2F343C', split:'#252A31', label:'#5C7080',
  palette:['#2D72D2','#238551','#D1980B','#CD4246','#7C3AED','#29A634','#EC9A3C','#9D78D2'],
  tooltip:{ backgroundColor:'#111418', borderColor:'#2F343C', textStyle:{ color:'#E6EDF3', fontSize:11 } },
};
var threatColors = {0:'#238551',1:'#D1980B',2:'#EC9A3C',3:'#CD4246'};
var threatLabels = {0:'Normal',1:'Elevated',2:'Suspicious',3:'Hostile'};
var threatRGBA = {0:'35,133,81',1:'209,152,11',2:'236,154,60',3:'205,66,70'};

function mkChart(id) {
  var el = document.getElementById(id);
  if (!el) return null;
  var c = echarts.init(el, null, {renderer:'canvas'});
  new ResizeObserver(function(){c.resize();}).observe(el);
  charts[id] = c;
  return c;
}

var botPatterns = __BOT_PATTERNS__;
var highVolIPs = new Set(D.high_volume_ips || []);
function isBot(ua, ip) {
  if (ip && highVolIPs.has(ip)) return true;
  var low = (ua || '').toLowerCase();
  return botPatterns.some(function(p){return low.indexOf(p) >= 0;});
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
function filterDaily(range) { var c = getCutoff(range); return D.traffic_daily.filter(function(d){return d.day >= c;}); }
function filterHourly(range) { var c = getCutoff(range); return D.traffic_hourly.filter(function(d){return d.hour >= c;}); }
function filterVisitors(range) { var c = getCutoff(range); return D.visitor_timeline.filter(function(d){return d.hour >= c;}); }

/* ---- KPIs ---- */
function updateKPIs(daily) {
  var views=0, sessions=0, bots=0, humans=0, msSum=0, msCount=0;
  daily.forEach(function(d) {
    views += d.count; sessions += d.sessions; bots += d.bots; humans += d.humans;
    if (d.avg_ms > 0) { msSum += d.avg_ms * d.count; msCount += d.count; }
  });
  var avgMs = msCount > 0 ? Math.round(msSum / msCount) : 0;
  var days = daily.length || 1;
  var vpd = Math.round(views / days);
  var total = views || 1;
  var humanPct = Math.round(humans / total * 100);
  var botPct = 100 - humanPct;

  /* Threat score: 0-100 based on bot%, rate-limited, banned */
  var rlCount = 0, banCount = 0;
  (D.suspicious_ips || []).forEach(function(s) { rlCount += s.rate_limited; banCount += s.banned; });
  var threat = Math.min(100, Math.round(botPct * 0.6 + Math.min(rlCount, 50) * 0.5 + Math.min(banCount, 20) * 1.0));
  var tColor = threat < 25 ? '#238551' : threat < 50 ? '#D1980B' : threat < 75 ? '#EC9A3C' : '#CD4246';

  var kpis = [
    {v:fmtNum(views), l:'Page Views', c:''},
    {v:fmtNum(vpd), l:'Views / Day', c:''},
    {v:fmtNum(sessions), l:'Sessions', c:''},
    {v:avgMs+'ms', l:'Avg Response', c:''},
    {v:humanPct+'%', l:'Human Traffic', c:'#238551', bar:humanPct},
    {v:botPct+'%', l:'Bot Traffic', c:'#CD4246', bar:botPct},
    {v:threat, l:'Threat Level', c:tColor, bar:threat},
  ];
  var html = '';
  kpis.forEach(function(k) {
    html += '<div class="kpi-cell"><div class="kpi-val"' + (k.c ? ' style="color:'+k.c+'"' : '') + '>' + k.v + '</div>';
    html += '<div class="kpi-lbl">' + k.l + '</div>';
    if (k.bar !== undefined) html += '<div class="kpi-bar"><div class="kpi-bar-fill" style="width:'+k.bar+'%;background:'+(k.c||'#2D72D2')+'"></div></div>';
    html += '</div>';
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
      grid:{top:8,right:12,bottom:24,left:40},
      xAxis:{type:'category',data:src.map(function(d){return d.hour.substring(11);}),boundaryGap:false,
        axisLabel:{color:DG2.label,fontSize:9},axisLine:{lineStyle:{color:DG2.axis}}},
      yAxis:{type:'value',splitLine:{lineStyle:{color:DG2.split}},axisLabel:{color:DG2.label,fontSize:9}},
      series:[{type:'line',data:src.map(function(d){return d.count;}),smooth:true,showSymbol:false,
        lineStyle:{color:'#2D72D2',width:1.5},
        areaStyle:{color:{type:'linear',x:0,y:0,x2:0,y2:1,colorStops:[{offset:0,color:'rgba(45,114,210,0.3)'},{offset:1,color:'rgba(45,114,210,0.02)'}]}}}],
      tooltip:Object.assign({trigger:'axis'},DG2.tooltip),legend:{show:false},
    }, true);
  } else {
    c.setOption({
      grid:{top:20,right:12,bottom:24,left:40},
      legend:{data:['Humans','Bots'],textStyle:{color:DG2.label,fontSize:10},top:0,right:0,itemWidth:10,itemHeight:8},
      xAxis:{type:'category',data:src.map(function(d){return d.day.substring(5);}),boundaryGap:false,
        axisLabel:{color:DG2.label,fontSize:9},axisLine:{lineStyle:{color:DG2.axis}}},
      yAxis:{type:'value',splitLine:{lineStyle:{color:DG2.split}},axisLabel:{color:DG2.label,fontSize:9}},
      series:[
        {name:'Humans',type:'line',stack:'t',data:src.map(function(d){return d.humans;}),
          smooth:true,showSymbol:false,lineStyle:{width:1,color:'#238551'},
          areaStyle:{color:{type:'linear',x:0,y:0,x2:0,y2:1,colorStops:[{offset:0,color:'rgba(35,133,81,0.4)'},{offset:1,color:'rgba(35,133,81,0.03)'}]}}},
        {name:'Bots',type:'line',stack:'t',data:src.map(function(d){return d.bots;}),
          smooth:true,showSymbol:false,lineStyle:{width:1,color:'#CD4246'},
          areaStyle:{color:{type:'linear',x:0,y:0,x2:0,y2:1,colorStops:[{offset:0,color:'rgba(205,66,70,0.4)'},{offset:1,color:'rgba(205,66,70,0.03)'}]}}},
      ],
      tooltip:Object.assign({trigger:'axis'},DG2.tooltip),
    }, true);
  }
}

/* ---- Apply Filter ---- */
function applyFilter(range) {
  activeRange = range;
  document.querySelectorAll('.rbtn').forEach(function(b){b.classList.toggle('active',b.dataset.range===range);});
  var daily = filterDaily(range);
  updateKPIs(daily);
  renderTraffic(range);
}

/* ---- Static Charts ---- */
function renderStaticCharts() {
  /* Bot Pie */
  var c = mkChart('chart-bot-pie');
  if (c) c.setOption({
    series:[{type:'pie',radius:['40%','68%'],center:['50%','55%'],
      data:[
        {name:'Humans',value:D.bot_vs_human.human,itemStyle:{color:'#238551'}},
        {name:'Bots',value:D.bot_vs_human.bot,itemStyle:{color:'#CD4246'}},
      ],
      label:{color:DG2.text,fontSize:10,formatter:'{b}\\n{d}%'},
      emphasis:{scaleSize:4},
    }],
    tooltip:DG2.tooltip,
  });

  /* Bot Breakdown by Category */
  var bb = D.bot_breakdown;
  var catColors = D.category_colors || {};
  var catColorMap = {'Search Engine':'#2D72D2','AI Crawler':'#7C3AED','AI Search':'#9D79EF',
    'SEO Tool':'#D1980B','Social Preview':'#2D72D2','Monitor':'#238551','Feed Fetcher':'#238551',
    'Archiver':'#5C7080','Security Scanner':'#CD4246','Scraper':'#CD4246','Other Bot':'#5C7080'};
  if (bb.length) {
    c = mkChart('chart-bot-bar');
    if (c) c.setOption({
      grid:{top:4,right:10,bottom:4,left:90},
      xAxis:{type:'value',show:false},
      yAxis:{type:'category',data:bb.map(function(d){return d.name;}).reverse(),
        axisLabel:{color:DG2.label,fontSize:9},axisLine:{show:false},axisTick:{show:false}},
      series:[{type:'bar',data:bb.map(function(d){
        return {value:d.count,itemStyle:{color:catColorMap[d.name]||'#5C7080'}};
      }).reverse(),
        barMaxWidth:12,
        label:{show:true,position:'right',color:DG2.label,fontSize:9}}],
      tooltip:Object.assign({trigger:'axis',axisPointer:{type:'shadow'}},DG2.tooltip),
    });
  }

  /* Top Pages */
  var tp = D.top_pages.slice(0,12);
  c = mkChart('chart-pages');
  if (c) c.setOption({
    grid:{top:4,right:40,bottom:4,left:140},
    xAxis:{type:'value',show:false},
    yAxis:{type:'category',data:tp.map(function(d){return d.path;}).reverse(),
      axisLabel:{color:DG2.label,fontSize:8,width:135,overflow:'truncate'},axisLine:{show:false},axisTick:{show:false}},
    series:[{type:'bar',data:tp.map(function(d){return d.count;}).reverse(),
      itemStyle:{color:'#2D72D2'},barMaxWidth:12,
      label:{show:true,position:'right',color:DG2.label,fontSize:8}}],
    tooltip:Object.assign({trigger:'axis',axisPointer:{type:'shadow'}},DG2.tooltip),
  });

  /* Status Codes */
  var sc = D.status_codes;
  if (sc.length) {
    var sColors = {200:'#238551',304:'#238551',301:'#2D72D2',302:'#2D72D2',404:'#D1980B',429:'#CD4246',403:'#CD4246',500:'#7C3AED'};
    c = mkChart('chart-status');
    if (c) c.setOption({
      series:[{type:'pie',radius:['35%','62%'],center:['50%','55%'],
        data:sc.map(function(s){return {name:s.code+'',value:s.count,itemStyle:{color:sColors[s.code]||'#5C7080'}};}),
        label:{color:DG2.text,fontSize:9,formatter:'{b}: {c}'},
      }],
      tooltip:DG2.tooltip,
    });
  }

  /* Referrers */
  var refs = D.referrers;
  if (refs.length) {
    c = mkChart('chart-referrers');
    if (c) c.setOption({
      grid:{top:4,right:10,bottom:4,left:100},
      xAxis:{type:'value',show:false},
      yAxis:{type:'category',data:refs.slice(0,8).map(function(d){
        var r=d.referrer;return r.length>25?r.substring(0,25)+'...':r;}).reverse(),
        axisLabel:{color:DG2.label,fontSize:8},axisLine:{show:false},axisTick:{show:false}},
      series:[{type:'bar',data:refs.slice(0,8).map(function(d){return d.count;}).reverse(),
        itemStyle:{color:'#29A634'},barMaxWidth:10,
        label:{show:true,position:'right',color:DG2.label,fontSize:8}}],
      tooltip:Object.assign({trigger:'axis',axisPointer:{type:'shadow'}},DG2.tooltip),
    });
  }

  /* Heatmap */
  var hm = D.heatmap;
  if (hm.length) {
    var dnames = ['Sun','Mon','Tue','Wed','Thu','Fri','Sat'];
    var hrs = []; for (var i=0;i<24;i++) hrs.push(i+'');
    var hmData = hm.map(function(d){return [d.hour,d.dow,d.count];});
    var maxVal = Math.max.apply(null,hm.map(function(d){return d.count;}));
    c = mkChart('chart-heatmap');
    if (c) c.setOption({
      grid:{top:4,right:8,bottom:20,left:36},
      xAxis:{type:'category',data:hrs,axisLabel:{color:DG2.label,fontSize:8},
        splitArea:{show:false},axisLine:{lineStyle:{color:DG2.axis}}},
      yAxis:{type:'category',data:dnames,axisLabel:{color:DG2.label,fontSize:9},axisLine:{show:false}},
      visualMap:{min:0,max:maxVal||1,show:false,inRange:{color:['#111418','#0E3A16','#238551','#29A634']}},
      series:[{type:'heatmap',data:hmData,label:{show:false},
        emphasis:{itemStyle:{shadowBlur:4,shadowColor:'rgba(45,114,210,0.4)'}}}],
      tooltip:Object.assign({formatter:function(p){return dnames[p.value[1]]+' '+hrs[p.value[0]]+'h<br><b>'+p.value[2]+'</b> requests';}},DG2.tooltip),
    });
  }

  /* Response Time Distribution */
  renderResponseTime();
}

/* ---- Response Time Distribution Chart ---- */
function renderResponseTime() {
  var rt = D.response_time_dist;
  if (!rt || !rt.length) return;
  var c = mkChart('chart-response');
  if (!c) return;
  var colors = ['#238551','#29A634','#D1980B','#D1980B','#EC9A3C','#CD4246','#CD4246'];
  c.setOption({
    grid:{top:8,right:12,bottom:28,left:40},
    xAxis:{type:'category',data:rt.map(function(d){return d.label;}),
      axisLabel:{color:DG2.label,fontSize:8,rotate:25},axisLine:{lineStyle:{color:DG2.axis}}},
    yAxis:{type:'value',splitLine:{lineStyle:{color:DG2.split}},axisLabel:{color:DG2.label,fontSize:9}},
    series:[{type:'bar',data:rt.map(function(d,i){return {value:d.count,itemStyle:{color:colors[i]||'#5C7080'}};}),
      barMaxWidth:24,
      label:{show:true,position:'top',color:DG2.label,fontSize:8}}],
    tooltip:Object.assign({trigger:'axis',axisPointer:{type:'shadow'}},DG2.tooltip),
  });
}

/* ---- Suspicious IPs Table ---- */
var suspSort = {key:'total', dir:-1};
function sortSusp(key) {
  if (suspSort.key === key) suspSort.dir *= -1;
  else { suspSort.key = key; suspSort.dir = -1; }
  renderSuspicious();
}
function renderSuspicious() {
  var tbody = document.getElementById('suspicious-body');
  if (!tbody || !D.suspicious_ips) return;
  var items = D.suspicious_ips.slice().sort(function(a,b) {
    var va = a[suspSort.key], vb = b[suspSort.key];
    if (typeof va === 'string') return suspSort.dir * va.localeCompare(vb);
    return suspSort.dir * ((va||0) - (vb||0));
  });
  var ths = tbody.closest('table').querySelectorAll('thead th');
  ths.forEach(function(th){th.classList.remove('sorted');});

  var html = '';
  items.forEach(function(s) {
    var tag = s.is_bot ? '<span class="tag-bot">BOT</span>' : (s.banned > 0 || s.rate_limited > 0 ? '<span class="tag-warn">SUSPECT</span>' : '<span class="tag-human">HUMAN</span>');
    html += '<tr>' +
      '<td class="mono"><span class="ip-link" onclick="investigateIP(\\'' + s.ip + '\\')">' + s.ip.substring(0,10) + '..</span></td>' +
      '<td class="r">' + fmtNum(s.total) + '</td>' +
      '<td class="r' + (s.rate_limited > 0 ? ' st-w' : '') + '">' + s.rate_limited + '</td>' +
      '<td class="r' + (s.banned > 0 ? ' st-e' : '') + '">' + s.banned + '</td>' +
      '<td class="mono" style="font-size:0.58rem;">' + (s.last || '').substring(5,16) + '</td>' +
      '<td>' + tag + '</td></tr>';
  });
  tbody.innerHTML = html;
}

/* ---- Recent Activity ---- */
function renderRecent() {
  var tbody = document.getElementById('recent-body');
  if (!tbody) return;
  var html = '';
  D.recent.slice(0,50).forEach(function(r) {
    var bot = isBot(r.ua, r.ip);
    var sc = r.status >= 500 ? 'st-e' : r.status >= 400 ? 'st-w' : 'st-ok';
    var tag = bot ? (highVolIPs.has(r.ip) ? '<span class="tag-warn">SUS</span>' : '<span class="tag-bot">BOT</span>') : '<span class="tag-human">OK</span>';
    html += '<tr>' +
      '<td class="mono" style="font-size:0.55rem;">' + (r.time || '').substring(11,19) + '</td>' +
      '<td class="mono" style="font-size:0.55rem;">' + r.ip.substring(0,8) + '</td>' +
      '<td style="font-size:0.6rem;">' + (r.city !== '---' ? r.city : r.country) + '</td>' +
      '<td style="font-size:0.6rem;max-width:120px;overflow:hidden;text-overflow:ellipsis;">' + r.path + '</td>' +
      '<td class="r ' + sc + '">' + r.status + '</td>' +
      '<td>' + tag + '</td></tr>';
  });
  tbody.innerHTML = html;
}

/* ---- Visitor Map ---- */
var mapInstance = null;
var arcVisible = false;

function renderMap() {
  mapboxgl.accessToken = '__MAPBOX_TOKEN__';
  var map = new mapboxgl.Map({
    container:'visitor-map', style:'mapbox://styles/mapbox/dark-v11',
    center:[0,30], zoom:1.8, projection:'globe', maxZoom:22,
  });
  mapInstance = map;
  map.addControl(new mapboxgl.NavigationControl({showCompass:true,visualizePitch:false}), 'top-right');

  /* Atmospheric fog effect */
  map.on('style.load', function() {
    map.setFog({
      color:'#111418',
      'high-color':'#1C2127',
      'horizon-blend':0.04,
      'space-color':'#0a0e12',
      'star-intensity':0.15
    });
  });

  var geo = D.geo;
  if (!geo.length) { document.getElementById('geo-note').textContent = 'No geolocation data.'; return; }

  map.on('load', function() {
    var features = geo.filter(function(g){return g.lat && g.lon;}).map(function(g) {
      return {type:'Feature',geometry:{type:'Point',coordinates:[g.lon,g.lat]},
        properties:{city:g.city||'Unknown',country:g.country,count:g.count,ips:g.ips,
          bots:g.bots||0,rate_limited:g.rate_limited||0,banned:g.banned||0,
          errors:g.errors||0,sessions:g.sessions||0,threat:g.threat||0}};
    });

    map.addSource('visitors',{type:'geojson',data:{type:'FeatureCollection',features:features}});

    /* Threat-colored layers */
    [0,1,2,3].forEach(function(t) {
      map.addLayer({id:'tg-'+t,type:'circle',source:'visitors',filter:['==',['get','threat'],t],
        paint:{'circle-radius':['interpolate',['linear'],['get','count'],1,8,10,16,50,24,200,32],
          'circle-color':threatColors[t],'circle-opacity':0.15,'circle-blur':0.8}});
      map.addLayer({id:'td-'+t,type:'circle',source:'visitors',filter:['==',['get','threat'],t],
        paint:{'circle-radius':['interpolate',['linear'],['get','count'],1,3,10,6,50,10,200,14],
          'circle-color':threatColors[t],'circle-opacity':0.85,
          'circle-stroke-width':1,'circle-stroke-color':threatColors[t]}});
    });

    /* Connection arcs to server (iad) */
    var sLoc = [-77.46, 38.95];
    var arcF = features.map(function(f){
      return {type:'Feature',geometry:{type:'LineString',coordinates:[f.geometry.coordinates,sLoc]},
        properties:{threat:f.properties.threat,count:f.properties.count}};
    });
    map.addSource('arcs',{type:'geojson',data:{type:'FeatureCollection',features:arcF}});
    [0,1,2,3].forEach(function(t) {
      map.addLayer({id:'arc-'+t,type:'line',source:'arcs',filter:['==',['get','threat'],t],
        layout:{visibility:'none'},
        paint:{'line-color':threatColors[t],
          'line-opacity':['interpolate',['linear'],['get','count'],1,0.05,50,0.18,200,0.3],
          'line-width':['interpolate',['linear'],['get','count'],1,0.5,50,1.5,200,2.5]}});
    });

    /* Server marker */
    map.addSource('server',{type:'geojson',data:{type:'FeatureCollection',features:[
      {type:'Feature',geometry:{type:'Point',coordinates:sLoc},properties:{}}]}});
    map.addLayer({id:'srv-glow',type:'circle',source:'server',layout:{visibility:'none'},
      paint:{'circle-radius':10,'circle-color':'#2D72D2','circle-opacity':0.2,'circle-blur':0.6}});
    map.addLayer({id:'srv-dot',type:'circle',source:'server',layout:{visibility:'none'},
      paint:{'circle-radius':5,'circle-color':'#2D72D2','circle-stroke-width':2,'circle-stroke-color':'#E6EDF3'}});

    /* Hover tooltip */
    var popup = new mapboxgl.Popup({closeButton:false,closeOnClick:false,offset:12});
    ['td-0','td-1','td-2','td-3'].forEach(function(lid) {
      map.on('click',lid,function(e) {
        var p = e.features[0].properties;
        openMapPanel(p.country,p.city||'Unknown',p);
        map.flyTo({center:e.lngLat,zoom:Math.max(map.getZoom(),4),speed:0.8,curve:1.2,duration:800});
      });
      map.on('mouseenter',lid,function(e){
        map.getCanvas().style.cursor='pointer';
        var p = e.features[0].properties;
        popup.setLngLat(e.lngLat)
          .setHTML('<b>'+(p.city||'Unknown')+', '+p.country+'</b><br>'+p.count+' requests &middot; '+p.ips+' IPs')
          .addTo(map);
      });
      map.on('mouseleave',lid,function(){
        map.getCanvas().style.cursor='';
        popup.remove();
      });
    });
  });

  var tc={0:0,1:0,2:0,3:0};
  geo.forEach(function(g){tc[g.threat]++;});
  document.getElementById('geo-note').textContent =
    geo.length+' LOC // '+D.geo_countries.length+' COUNTRIES // '+tc[3]+' HST '+tc[2]+' SUS '+tc[1]+' ELV '+tc[0]+' NRM';
}

function toggleThreatLayer(level,btn) {
  if (!mapInstance) return;
  btn.classList.toggle('active');
  var vis = btn.classList.contains('active') ? 'visible' : 'none';
  ['tg-'+level,'td-'+level].forEach(function(id){if(mapInstance.getLayer(id))mapInstance.setLayoutProperty(id,'visibility',vis);});
  if (arcVisible && mapInstance.getLayer('arc-'+level)) mapInstance.setLayoutProperty('arc-'+level,'visibility',vis);
}
function toggleArcs(btn) {
  if (!mapInstance) return;
  arcVisible = !arcVisible;
  btn.classList.toggle('active',arcVisible);
  [0,1,2,3].forEach(function(t){
    var db = document.querySelector('.mt[data-threat="'+t+'"]');
    var vis = arcVisible && db && db.classList.contains('active') ? 'visible' : 'none';
    if (mapInstance.getLayer('arc-'+t)) mapInstance.setLayoutProperty('arc-'+t,'visibility',vis);
  });
  ['srv-glow','srv-dot'].forEach(function(id){if(mapInstance.getLayer(id))mapInstance.setLayoutProperty(id,'visibility',arcVisible?'visible':'none');});
}
function closeMapPanel(){document.getElementById('map-panel').classList.remove('open');}

function openMapPanel(country,city,props) {
  var panel = document.getElementById('map-panel');
  var content = document.getElementById('map-panel-content');
  var threat = Number(props.threat)||0;
  content.innerHTML =
    '<h4>'+city+', '+country+'</h4>'+
    '<div class="sub"><span class="tb t'+threat+'">'+threatLabels[threat]+'</span></div>'+
    '<div style="display:grid;grid-template-columns:1fr 1fr;gap:4px;margin-bottom:10px;">'+
      '<div class="mc2"><div class="mc2v">'+fmtNum(props.count)+'</div><div class="mc2l">Requests</div></div>'+
      '<div class="mc2"><div class="mc2v">'+fmtNum(props.ips)+'</div><div class="mc2l">Unique IPs</div></div>'+
      '<div class="mc2"><div class="mc2v">'+fmtNum(props.sessions||0)+'</div><div class="mc2l">Sessions</div></div>'+
      '<div class="mc2"><div class="mc2v">'+fmtNum(props.bots||0)+'</div><div class="mc2l">Bot Reqs</div></div>'+
      '<div class="mc2"><div class="mc2v"'+(Number(props.rate_limited)>0?' style="color:#D1980B;"':'')+'>'+
        (props.rate_limited||0)+'</div><div class="mc2l">429s</div></div>'+
      '<div class="mc2"><div class="mc2v"'+(Number(props.banned)>0?' style="color:#CD4246;"':'')+'>'+
        (props.banned||0)+'</div><div class="mc2l">403s</div></div>'+
    '</div>'+
    '<div id="pda" style="color:#5C7080;font-size:0.62rem;text-align:center;">Loading...</div>';
  panel.classList.add('open');

  fetch('/api/location?country='+encodeURIComponent(country)+'&city='+encodeURIComponent(city||''))
    .then(function(r){return r.json();})
    .then(function(d) {
      if (d.error){document.getElementById('pda').textContent='No detail data.';return;}
      var h='';
      if (d.hourly && d.hourly.length > 1) {
        h += '<div class="sec-t" style="margin-top:4px;">Activity Timeline</div>'+
          '<div id="mp-chart" style="height:110px;margin-bottom:8px;"></div>';
      }
      if (d.top_paths && d.top_paths.length) {
        h += '<div class="sec-t">Top Paths</div>';
        d.top_paths.slice(0,6).forEach(function(p){
          h += '<div class="path-row"><span style="max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">'+p.path+'</span><span class="c">'+p.count+'</span></div>';
        });
      }
      if (d.ips && d.ips.length) {
        h += '<div class="sec-t" style="margin-top:8px;">IPs ('+d.ips.length+')</div><div style="max-height:160px;overflow-y:auto;">';
        d.ips.forEach(function(ip){
          var tag = ip.is_bot ? '<span class="tag-bot">BOT</span>' : '<span class="tag-human">OK</span>';
          h += '<div style="display:flex;justify-content:space-between;align-items:center;padding:2px 0;border-bottom:1px solid rgba(47,52,60,0.5);font-size:0.62rem;">'+
            '<span class="mono ip-link" onclick="closeMapPanel();investigateIP(\\''+ip.ip+'\\')" style="font-size:0.58rem;">'+ip.ip.substring(0,10)+'..</span>'+
            '<span>'+tag+'</span><span class="r" style="color:#ABB3BF;">'+ip.total+'</span></div>';
        });
        h += '</div>';
      }
      if (d.user_agents && d.user_agents.length) {
        h += '<div class="sec-t" style="margin-top:8px;">UAs ('+d.user_agents.length+')</div>';
        d.user_agents.slice(0,3).forEach(function(ua){
          h += '<div class="ua-item">'+((ua.ua||'').substring(0,70)+(ua.ua&&ua.ua.length>70?'...':''))+' <span style="color:#2D72D2;">('+ua.count+')</span></div>';
        });
      }
      document.getElementById('pda').outerHTML = h;
      /* Render timeline */
      if (d.hourly && d.hourly.length > 1) {
        var el = document.getElementById('mp-chart');
        if (el) {
          var ch = echarts.init(el,null,{renderer:'canvas'});
          new ResizeObserver(function(){ch.resize();}).observe(el);
          ch.setOption({
            grid:{top:4,right:6,bottom:16,left:30},
            xAxis:{type:'category',data:d.hourly.map(function(h){return h.hour.substring(5);}),boundaryGap:false,
              axisLabel:{color:DG2.label,fontSize:7,rotate:30},axisLine:{lineStyle:{color:DG2.axis}}},
            yAxis:{type:'value',splitLine:{lineStyle:{color:DG2.split}},axisLabel:{color:DG2.label,fontSize:8}},
            series:[{type:'line',data:d.hourly.map(function(h){return h.count;}),smooth:true,showSymbol:false,
              lineStyle:{color:threatColors[threat],width:1.5},
              areaStyle:{color:{type:'linear',x:0,y:0,x2:0,y2:1,colorStops:[
                {offset:0,color:'rgba('+threatRGBA[threat]+',0.3)'},
                {offset:1,color:'rgba('+threatRGBA[threat]+',0.02)'}]}}}],
            tooltip:Object.assign({trigger:'axis'},DG2.tooltip),
          });
        }
      }
    }).catch(function(e){console.error('Location detail error:',e);});
}

/* ---- IP Investigation (Full Dossier Overlay) ---- */
function closeIPDossier(){document.getElementById('ip-overlay').classList.remove('open');}

function investigateIP(hash) {
  var overlay = document.getElementById('ip-overlay');
  var content = document.getElementById('ip-dossier-content');
  content.innerHTML = '<div style="text-align:center;padding:40px;color:#5C7080;">Loading dossier for <span style="color:#2D72D2;font-family:Consolas,monospace;">'+hash+'</span>...</div>';
  overlay.classList.add('open');

  fetch('/api/ip/'+hash)
    .then(function(r){return r.json();})
    .then(function(d) {
      if (d.error){content.innerHTML='<div style="color:#CD4246;padding:20px;">IP not found.</div>';return;}

      var verdict = '';
      if (d.interval) {
        if (d.interval.avg < 5) verdict = '<span class="tag-bot">AUTOMATED</span> avg '+d.interval.avg+'s between requests';
        else if (d.interval.avg < 30) verdict = '<span class="tag-warn">SUSPICIOUS</span> avg '+d.interval.avg+'s between requests';
        else verdict = '<span class="tag-human">NORMAL</span> avg '+d.interval.avg+'s between requests';
      }

      var h = '<div style="display:flex;align-items:center;gap:12px;margin-bottom:14px;">'+
        '<div><div class="hdr-id">IP DOSSIER // INVESTIGATION</div>'+
        '<h1 style="font-size:1rem;font-weight:600;color:#E6EDF3;font-family:Consolas,monospace;">'+hash+'</h1></div></div>';

      /* KPI grid */
      var kpis = [
        ['Total Requests',fmtNum(d.total),''],
        ['Unique Paths',fmtNum(d.unique_paths),''],
        ['Active Days',d.active_days,''],
        ['Avg Response',(d.avg_ms||0)+'ms',''],
        ['200 OK',d.status.ok,'#238551'],
        ['429 Rate-Ltd',d.status.rate_limited,d.status.rate_limited>0?'#D1980B':''],
        ['403 Banned',d.status.banned,d.status.banned>0?'#CD4246':''],
        ['404 Not Found',d.status.not_found,''],
      ];
      h += '<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:6px;margin-bottom:14px;">';
      kpis.forEach(function(k){
        h += '<div class="mc2"><div class="mc2v"'+(k[2]?' style="color:'+k[2]+'"':'')+'>'+k[1]+'</div><div class="mc2l">'+k[0]+'</div></div>';
      });
      h += '</div>';

      /* Verdict */
      if (verdict) {
        h += '<div style="background:#111418;border:1px solid #2F343C;border-radius:4px;padding:8px 12px;margin-bottom:14px;font-size:0.75rem;">'+
          '<div class="sec-t" style="margin-bottom:4px;">Request Pattern Analysis</div>'+verdict+
          '<div style="color:#5C7080;font-size:0.65rem;margin-top:4px;">Min: '+d.interval.min+'s &middot; Median: '+d.interval.median+'s &middot; Max: '+d.interval.max+'s'+
          '<br>First: '+d.first_seen+' &middot; Last: '+d.last_seen+
          '<br>Location: '+(d.cities||'---')+', '+(d.countries||'---')+'</div></div>';
      }

      /* Timeline + Details in 2-col layout */
      h += '<div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;">';

      /* Left: Timeline */
      h += '<div>';
      if (d.hourly && d.hourly.length > 1) {
        h += '<div class="sec-t">Activity Timeline</div><div id="ip-chart" style="height:180px;margin-bottom:12px;"></div>';
      }
      /* Top Paths */
      if (d.top_paths && d.top_paths.length) {
        h += '<div class="sec-t">Top Paths ('+fmtNum(d.unique_paths)+' unique)</div>';
        d.top_paths.slice(0,10).forEach(function(p){
          h += '<div class="path-row"><span>'+p.path+'</span><span class="c">'+p.count+'</span></div>';
        });
      }
      h += '</div>';

      /* Right: UAs + Recent */
      h += '<div>';
      if (d.user_agents && d.user_agents.length) {
        h += '<div class="sec-t">User Agents ('+d.user_agents.length+')</div>';
        d.user_agents.forEach(function(ua){h += '<div class="ua-item">'+ua+'</div>';});
      }
      if (d.recent && d.recent.length) {
        h += '<div class="sec-t" style="margin-top:10px;">Last '+d.recent.length+' Requests</div>'+
          '<div style="max-height:200px;overflow-y:auto;"><table><thead><tr><th>Time</th><th>Path</th><th class="r">St</th><th class="r">ms</th></tr></thead><tbody>';
        d.recent.forEach(function(r){
          var sc = r.status >= 400 ? 'st-e' : 'st-ok';
          h += '<tr><td class="mono" style="font-size:0.55rem;">'+((r.time||'').substring(11,19))+'</td>'+
            '<td style="max-width:200px;overflow:hidden;text-overflow:ellipsis;">'+r.path+'</td>'+
            '<td class="r '+sc+'">'+r.status+'</td>'+
            '<td class="r">'+(r.ms?r.ms.toFixed(0):'-')+'</td></tr>';
        });
        h += '</tbody></table></div>';
      }
      h += '</div></div>';

      content.innerHTML = h;

      /* Render IP timeline chart */
      if (d.hourly && d.hourly.length > 1) {
        var el = document.getElementById('ip-chart');
        if (el) {
          var ch = echarts.init(el,null,{renderer:'canvas'});
          new ResizeObserver(function(){ch.resize();}).observe(el);
          ch.setOption({
            grid:{top:8,right:12,bottom:24,left:40},
            xAxis:{type:'category',data:d.hourly.map(function(h){return h.hour;}),boundaryGap:false,
              axisLabel:{color:DG2.label,fontSize:8,rotate:30},axisLine:{lineStyle:{color:DG2.axis}}},
            yAxis:{type:'value',splitLine:{lineStyle:{color:DG2.split}},axisLabel:{color:DG2.label,fontSize:9}},
            series:[{type:'line',data:d.hourly.map(function(h){return h.count;}),smooth:true,showSymbol:false,
              lineStyle:{color:'#CD4246',width:2},
              areaStyle:{color:{type:'linear',x:0,y:0,x2:0,y2:1,colorStops:[
                {offset:0,color:'rgba(205,66,70,0.3)'},{offset:1,color:'rgba(205,66,70,0.02)'}]}}}],
            tooltip:Object.assign({trigger:'axis'},DG2.tooltip),
          });
        }
      }
    })
    .catch(function(e){content.innerHTML='<div style="color:#CD4246;padding:20px;">Error: '+e.message+'</div>';});
}

/* ---- Render All ---- */
function renderAll() {
  document.getElementById('date-range').textContent =
    (D.date_range.first||'N/A')+' to '+(D.date_range.last||'N/A')+' // '+fmtNum(D.total_views)+' views // '+fmtNum(D.unique_ips)+' IPs';
  highVolIPs = new Set(D.high_volume_ips || []);
  applyFilter(activeRange);
  renderStaticCharts();
  renderSuspicious();
  renderRecent();
}

try { renderAll(); renderMap(); } catch(e) {
  console.error('[Dashboard init error]',e);
  var d=document.createElement('div');
  d.style.cssText='background:#3D1F1F;border:1px solid #CD4246;color:#FA999C;padding:10px;margin:10px;border-radius:4px;font-family:Consolas,monospace;font-size:0.75rem;';
  d.textContent='Init Error: '+e.message;
  document.querySelector('.shell').prepend(d);
}

/* ---- Filter Buttons ---- */
document.querySelectorAll('.rbtn').forEach(function(btn){
  btn.addEventListener('click',function(){applyFilter(btn.dataset.range);});
});

/* ---- AJAX Refresh ---- */
function refreshData() {
  var st = document.getElementById('refresh-status');
  st.textContent = 'Refreshing...';
  fetch('/api/data')
    .then(function(r){return r.json();})
    .then(function(nd){
      D = nd;
      try{renderAll();}catch(e){console.error('[Refresh error]',e);}
      st.textContent = 'Updated '+new Date().toLocaleTimeString();
      setTimeout(function(){if(!refreshTimer)st.textContent='';},5000);
    })
    .catch(function(e){st.textContent='Refresh failed';console.error(e);});
}

var refreshTimer = null;
document.getElementById('refresh-interval').addEventListener('change',function(){
  if(refreshTimer){clearInterval(refreshTimer);refreshTimer=null;}
  var secs=parseInt(this.value);
  if(secs>0){
    document.getElementById('refresh-status').textContent='Auto: '+secs+'s';
    refreshTimer=setInterval(refreshData,secs*1000);
  } else {document.getElementById('refresh-status').textContent='';}
});

/* ---- Sync Status ---- */
function updateSyncStatus() {
  fetch('/api/sync-status').then(function(r){return r.json();}).then(function(s){
    var el=document.getElementById('sync-status');
    var p=[];
    if(s.last_sync)p.push('Sync: '+s.last_sync);
    if(s.status==='syncing')p.push('SYNCING...');
    if(s.status==='error')p.push('ERR: '+(s.error||'').substring(0,30));
    el.textContent=p.join(' // ');
    el.style.color=s.status==='error'?'#CD4246':s.status==='syncing'?'#D1980B':'#5C7080';
  }).catch(function(){});
}
updateSyncStatus();
setInterval(updateSyncStatus,15000);

function syncNow(){
  document.getElementById('sync-status').textContent='Syncing...';
  document.getElementById('sync-status').style.color='#D1980B';
  fetch('/api/sync-now').then(function(){
    setTimeout(function(){updateSyncStatus();refreshData();},8000);
  });
}

/* Start auto-refresh */
(function(){
  var sel=document.getElementById('refresh-interval');
  var secs=parseInt(sel.value);
  if(secs>0){
    document.getElementById('refresh-status').textContent='Auto: '+secs+'s';
    refreshTimer=setInterval(refreshData,secs*1000);
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


def query_location_detail(country, city):
    """Get detailed analytics for a specific geographic location."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    ua_clause = get_bot_sql_clause()
    vol_rows = conn.execute(
        "SELECT ip_hash FROM page_views GROUP BY ip_hash HAVING count(*) > 50"
    ).fetchall()
    high_vol_ips = {r["ip_hash"] for r in vol_rows}
    if high_vol_ips:
        ip_list = ",".join([f"'{ip}'" for ip in high_vol_ips])
        bot_clause = f"({ua_clause}) OR ip_hash IN ({ip_list})"
    else:
        bot_clause = ua_clause

    where = "country = ?"
    params = [country]
    if city:
        where += " AND city = ?"
        params.append(city)
    else:
        where += " AND (city IS NULL OR city = '')"

    # IP breakdown
    ips = conn.execute(f"""
        SELECT ip_hash, count(*) AS total,
               sum(CASE WHEN ({bot_clause}) THEN 1 ELSE 0 END) AS bot_hits,
               sum(CASE WHEN status_code >= 400 THEN 1 ELSE 0 END) AS errors,
               min(timestamp) AS first_seen, max(timestamp) AS last_seen
        FROM page_views WHERE {where}
        GROUP BY ip_hash ORDER BY total DESC LIMIT 20
    """, params).fetchall()

    # Hourly timeline
    hours = conn.execute(f"""
        SELECT strftime('%Y-%m-%d %H:00', timestamp) AS hour, count(*) AS cnt
        FROM page_views WHERE {where}
        GROUP BY hour ORDER BY hour
    """, params).fetchall()

    # Top paths
    paths = conn.execute(f"""
        SELECT path, count(*) AS cnt
        FROM page_views WHERE {where}
        GROUP BY path ORDER BY cnt DESC LIMIT 15
    """, params).fetchall()

    # User agents
    uas = conn.execute(f"""
        SELECT user_agent AS ua, count(*) AS cnt
        FROM page_views WHERE {where} AND user_agent IS NOT NULL
        GROUP BY user_agent ORDER BY cnt DESC LIMIT 10
    """, params).fetchall()

    conn.close()

    return {
        "ips": [{"ip": r["ip_hash"], "total": r["total"],
                 "is_bot": r["bot_hits"] > 0, "errors": r["errors"],
                 "first": r["first_seen"], "last": r["last_seen"]} for r in ips],
        "hourly": [{"hour": r["hour"], "count": r["cnt"]} for r in hours],
        "top_paths": [{"path": r["path"], "count": r["cnt"]} for r in paths],
        "user_agents": [{"ua": r["ua"], "count": r["cnt"]} for r in uas],
    }


class DashboardHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            data = query_analytics()
            bot_patterns_js = json.dumps(get_all_patterns())
            html = (DASHBOARD_HTML
                    .replace("__DATA__", json.dumps(data))
                    .replace("__MAPBOX_TOKEN__", MAPBOX_TOKEN)
                    .replace("__BOT_PATTERNS__", bot_patterns_js))
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
            self.send_header("Pragma", "no-cache")
            self.end_headers()
            self.wfile.write(html.encode())
        elif self.path.startswith("/api/location"):
            qs = parse_qs(urlparse(self.path).query)
            country = qs.get("country", [""])[0]
            city = qs.get("city", [""])[0]
            detail = query_location_detail(country, city) if country else None
            self.send_response(200 if detail else 404)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(json.dumps(detail or {"error": "not found"}).encode())
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
