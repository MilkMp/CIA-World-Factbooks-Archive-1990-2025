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
import webbrowser
from datetime import datetime, timedelta

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

PORT = 8888
DB_PATH = os.path.join(os.path.dirname(__file__), "data", "analytics.db")
MAPBOX_TOKEN = os.getenv("MAPBOX_TOKEN", "")


def sync_db():
    """Download analytics.db from Fly.io."""
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
        print("[+] Synced successfully")
    except subprocess.CalledProcessError as e:
        print(f"[!] Sync failed: {e.stderr.strip()}")
        if os.path.exists(bak):
            os.replace(bak, DB_PATH)
            print("[*] Using cached local copy")
        elif not os.path.exists(DB_PATH):
            print("[!] No local analytics.db found. Run with Fly.io access.")
            sys.exit(1)


def query_analytics():
    """Query analytics.db and return all dashboard data as JSON."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    data = {}

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

    # --- Traffic by day ---
    rows = conn.execute("""
        SELECT date(timestamp) AS day, count(*) AS cnt,
               count(DISTINCT session_id) AS sessions,
               count(DISTINCT ip_hash) AS ips
        FROM page_views GROUP BY day ORDER BY day
    """).fetchall()
    data["traffic_daily"] = [{"day": r["day"], "count": r["cnt"],
                              "sessions": r["sessions"], "ips": r["ips"]} for r in rows]

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
    bot_patterns = ['bot', 'crawl', 'spider', 'slurp', 'semrush', 'ahref',
                    'mj12bot', 'dotbot', 'bytespider', 'claudebot', 'gptbot',
                    'wget', 'curl', 'python-requests', 'scrapy', 'httpx']
    bot_clause = " OR ".join([f"lower(user_agent) LIKE '%{b}%'" for b in bot_patterns])
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

    # --- Recent page views (last 50) ---
    rows = conn.execute("""
        SELECT timestamp, ip_hash, country, city, path, status_code,
               user_agent, response_ms
        FROM page_views ORDER BY id DESC LIMIT 50
    """).fetchall()
    data["recent"] = [{
        "time": r["timestamp"], "ip": r["ip_hash"],
        "country": r["country"] or "---", "city": r["city"] or "---",
        "path": r["path"], "status": r["status_code"],
        "ua": r["user_agent"][:80] if r["user_agent"] else "",
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

    conn.close()
    return data


DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Analytics Dashboard — CIA Factbook Archive</title>
<script src="https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js"></script>
<link href="https://api.mapbox.com/mapbox-gl-js/v3.3.0/mapbox-gl.css" rel="stylesheet">
<script src="https://api.mapbox.com/mapbox-gl-js/v3.3.0/mapbox-gl.js"></script>
<style>
  * { margin:0; padding:0; box-sizing:border-box; }
  body {
    background:#111418; color:#C5CBD3;
    font-family: -apple-system, 'Segoe UI', Roboto, sans-serif;
    font-size: 14px; line-height: 1.5;
  }
  .header {
    padding: 20px 24px 12px;
    border-bottom: 1px solid #2F343C;
  }
  .header h1 { font-size: 1.1rem; font-weight: 600; color: #E4E7EB; }
  .header .meta { font-size: 0.7rem; color: #5F6B7C; text-transform: uppercase; letter-spacing: 1.2px; margin-bottom: 4px; }
  .header .sub { font-size: 0.82rem; color: #8F99A8; margin-top: 4px; }
  .container { max-width: 1600px; margin: 0 auto; padding: 16px 24px; }

  .kpi-grid {
    display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
    gap: 12px; margin: 16px 0;
  }
  .kpi-card {
    background: #1C2127; border: 1px solid #2F343C; border-radius: 4px;
    padding: 12px 16px; text-align: center;
  }
  .kpi-value { font-size: 1.4rem; font-weight: 700; color: #E4E7EB; font-variant-numeric: tabular-nums; }
  .kpi-label { font-size: 0.7rem; color: #5F6B7C; text-transform: uppercase; letter-spacing: 1px; margin-top: 4px; }

  .sec { display:flex; align-items:center; gap:10px; margin:24px 0 12px; }
  .sec-num { font-size:0.68rem; color:#2D72D2; font-weight:700; letter-spacing:1px; }
  .sec-title { font-size:0.72rem; color:#8F99A8; text-transform:uppercase; letter-spacing:1.2px; font-weight:600; }
  .sec-rule { flex:1; border:none; border-top:1px solid #2F343C; }

  .chart-grid {
    display: grid; grid-template-columns: repeat(auto-fit, minmax(480px, 1fr));
    gap: 16px; margin: 16px 0;
  }
  .chart-card {
    background: #1C2127; border: 1px solid #2F343C; border-radius: 4px;
    padding: 14px;
  }
  .chart-card h3 {
    font-size: 0.72rem; font-weight: 600; text-transform: uppercase;
    letter-spacing: 1.2px; color: #8F99A8; margin-bottom: 8px;
  }
  .chart-box { width: 100%; height: 280px; }
  .chart-box.tall { height: 400px; }

  #visitor-map { width: 100%; height: 400px; border-radius: 4px; }
  .mapboxgl-popup-content { background:#1C2127!important; color:#C5CBD3; border:1px solid #2F343C;
    border-radius:4px; font-size:0.82rem; padding:8px 12px; }
  .mapboxgl-popup-tip { border-top-color:#1C2127!important; }
  .dark-popup .mapboxgl-popup-content { box-shadow:0 2px 8px rgba(0,0,0,0.5); }

  table { width: 100%; border-collapse: collapse; font-size: 0.82rem; }
  th { text-align: left; color: #5F6B7C; font-size: 0.7rem; text-transform: uppercase;
       letter-spacing: 1px; padding: 6px 10px; border-bottom: 1px solid #2F343C; }
  td { padding: 5px 10px; border-bottom: 1px solid #252A31; color: #ABB3BF; }
  tr:hover td { background: rgba(45, 114, 210, 0.05); }
  .r { text-align: right; font-variant-numeric: tabular-nums; }
  .bot-tag { background: #CD4246; color: #fff; font-size: 0.65rem; padding: 1px 6px;
             border-radius: 3px; font-weight: 600; }
  .human-tag { background: #29A634; color: #fff; font-size: 0.65rem; padding: 1px 6px;
               border-radius: 3px; font-weight: 600; }
  .status-ok { color: #29A634; }
  .status-err { color: #CD4246; }
  .sync-btn {
    background: #2D72D2; color: #fff; border: none; border-radius: 3px;
    padding: 6px 14px; font-size: 0.78rem; cursor: pointer; float: right;
    margin-top: -4px;
  }
  .sync-btn:hover { background: #215DB0; }
  @media (max-width: 800px) {
    .chart-grid { grid-template-columns: 1fr; }
    .chart-box { height: 220px; }
  }
</style>
</head>
<body>

<div class="header">
  <div class="meta">LOCAL INTELLIGENCE // ANALYTICS DASHBOARD</div>
  <h1>CIA Factbook Archive — Visitor Analytics</h1>
  <div class="sub" id="date-range"></div>
</div>

<div class="container">

<!-- KPI Strip -->
<div class="kpi-grid" id="kpis"></div>

<!-- Section 01: Traffic -->
<div class="sec">
  <span class="sec-num">01</span>
  <span class="sec-title">Traffic</span>
  <hr class="sec-rule">
</div>
<div class="chart-grid">
  <div class="chart-card">
    <h3>Page Views Over Time</h3>
    <div class="chart-box" id="chart-traffic"></div>
  </div>
  <div class="chart-card">
    <h3>Visitors: Bots vs Humans</h3>
    <div class="chart-box" id="chart-visitors"></div>
  </div>
</div>

<!-- Section 02: Bots & Threats -->
<div class="sec">
  <span class="sec-num">02</span>
  <span class="sec-title">Bot Intelligence</span>
  <hr class="sec-rule">
</div>
<div class="chart-grid">
  <div class="chart-card">
    <h3>Bot vs Human Traffic</h3>
    <div class="chart-box" id="chart-bot-pie"></div>
  </div>
  <div class="chart-card">
    <h3>Bot Breakdown</h3>
    <div class="chart-box" id="chart-bot-bar"></div>
  </div>
</div>

<!-- Section 03: Visitor Map -->
<div class="sec">
  <span class="sec-num">03</span>
  <span class="sec-title">Visitor Map</span>
  <hr class="sec-rule">
</div>
<div class="chart-card" style="margin:16px 0;">
  <h3>Geographic Distribution</h3>
  <div id="visitor-map"></div>
  <div id="geo-note" style="font-size:0.75rem;color:#5F6B7C;margin-top:8px;"></div>
</div>

<!-- Section 04: Pages & Performance -->
<div class="sec">
  <span class="sec-num">04</span>
  <span class="sec-title">Pages & Performance</span>
  <hr class="sec-rule">
</div>
<div class="chart-grid">
  <div class="chart-card">
    <h3>Top Pages</h3>
    <div class="chart-box tall" id="chart-pages"></div>
  </div>
  <div class="chart-card">
    <h3>Response Time Distribution</h3>
    <div class="chart-box" id="chart-rt"></div>
  </div>
</div>

<!-- Section 05: Recent Activity -->
<div class="sec">
  <span class="sec-num">05</span>
  <span class="sec-title">Recent Activity</span>
  <hr class="sec-rule">
</div>
<div style="overflow-x:auto;margin:16px 0;">
  <table id="recent-table">
    <thead>
      <tr>
        <th>Time (UTC)</th>
        <th>IP Hash</th>
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

<script>
var D = __DATA__;

/* ── Theme ── */
var DG2 = {
  bg: 'transparent',
  text: '#ABB3BF',
  axis: '#2F343C',
  split: '#252A31',
  label: '#8F99A8',
  palette: ['#2D72D2','#29A634','#D1980B','#D33D17','#9D3F9D','#00A396','#DB2C6F','#7961DB'],
};

function mkChart(id) {
  var el = document.getElementById(id);
  if (!el) return null;
  var c = echarts.init(el, null, { renderer: 'canvas' });
  new ResizeObserver(function() { c.resize(); }).observe(el);
  return c;
}

var botPatterns = ['bot','crawl','spider','slurp','semrush','ahref','mj12bot',
  'dotbot','bytespider','claudebot','gptbot','wget','curl','python-requests','scrapy','httpx'];
function isBot(ua) {
  var low = (ua || '').toLowerCase();
  return botPatterns.some(function(p) { return low.indexOf(p) >= 0; });
}

/* ── KPIs ── */
document.getElementById('date-range').textContent =
  'Data from ' + (D.date_range.first || 'N/A') + ' to ' + (D.date_range.last || 'N/A');

var kpiHtml = [
  ['Page Views', D.total_views],
  ['Unique Sessions', D.unique_sessions],
  ['Unique IPs', D.unique_ips],
  ['Avg Response', D.avg_response_ms + 'ms'],
  ['Humans', D.bot_vs_human.human],
  ['Bots', D.bot_vs_human.bot],
].map(function(k) {
  return '<div class="kpi-card"><div class="kpi-value">' + k[1] + '</div><div class="kpi-label">' + k[0] + '</div></div>';
}).join('');
document.getElementById('kpis').innerHTML = kpiHtml;

/* ── Traffic Chart ── */
(function() {
  var src = D.traffic_hourly.length > 48 ? D.traffic_daily : D.traffic_hourly;
  var labels = src.map(function(d) { return d.hour || d.day; });
  var vals = src.map(function(d) { return d.count; });
  var c = mkChart('chart-traffic');
  c.setOption({
    grid: { top: 10, right: 16, bottom: 30, left: 50 },
    xAxis: { type: 'category', data: labels, axisLabel: { color: DG2.label, fontSize: 9, rotate: 30 },
             axisLine: { lineStyle: { color: DG2.axis } } },
    yAxis: { type: 'value', splitLine: { lineStyle: { color: DG2.split } },
             axisLabel: { color: DG2.label, fontSize: 10 } },
    series: [{ type: 'bar', data: vals, itemStyle: { color: '#2D72D2' }, barMaxWidth: 30 }],
    tooltip: { trigger: 'axis', backgroundColor: '#1C2127', borderColor: '#2F343C',
               textStyle: { color: '#C5CBD3', fontSize: 12 } },
  });
})();

/* ── Visitors Timeline ── */
(function() {
  var vt = D.visitor_timeline;
  var c = mkChart('chart-visitors');
  c.setOption({
    grid: { top: 30, right: 16, bottom: 30, left: 50 },
    legend: { data: ['Humans', 'Bots'], textStyle: { color: DG2.label, fontSize: 10 }, top: 0 },
    xAxis: { type: 'category', data: vt.map(function(d) { return d.hour; }),
             axisLabel: { color: DG2.label, fontSize: 9, rotate: 30 },
             axisLine: { lineStyle: { color: DG2.axis } } },
    yAxis: { type: 'value', splitLine: { lineStyle: { color: DG2.split } },
             axisLabel: { color: DG2.label } },
    series: [
      { name: 'Humans', type: 'bar', stack: 'v', data: vt.map(function(d) { return d.humans; }),
        itemStyle: { color: '#29A634' }, barMaxWidth: 30 },
      { name: 'Bots', type: 'bar', stack: 'v', data: vt.map(function(d) { return d.bots; }),
        itemStyle: { color: '#CD4246' }, barMaxWidth: 30 },
    ],
    tooltip: { trigger: 'axis', backgroundColor: '#1C2127', borderColor: '#2F343C',
               textStyle: { color: '#C5CBD3' } },
  });
})();

/* ── Bot Pie ── */
(function() {
  var c = mkChart('chart-bot-pie');
  c.setOption({
    series: [{
      type: 'pie', radius: ['40%', '70%'], center: ['50%', '55%'],
      data: [
        { name: 'Humans', value: D.bot_vs_human.human, itemStyle: { color: '#29A634' } },
        { name: 'Bots', value: D.bot_vs_human.bot, itemStyle: { color: '#CD4246' } },
      ],
      label: { color: DG2.text, fontSize: 12, formatter: '{b}: {c} ({d}%)' },
    }],
    tooltip: { backgroundColor: '#1C2127', borderColor: '#2F343C',
               textStyle: { color: '#C5CBD3' } },
  });
})();

/* ── Bot Breakdown Bar ── */
(function() {
  var bb = D.bot_breakdown;
  if (!bb.length) return;
  var c = mkChart('chart-bot-bar');
  c.setOption({
    grid: { top: 10, right: 16, bottom: 30, left: 100 },
    xAxis: { type: 'value', splitLine: { lineStyle: { color: DG2.split } },
             axisLabel: { color: DG2.label } },
    yAxis: { type: 'category', data: bb.map(function(d) { return d.name; }).reverse(),
             axisLabel: { color: DG2.label, fontSize: 10 } },
    series: [{ type: 'bar', data: bb.map(function(d) { return d.count; }).reverse(),
               itemStyle: { color: '#CD4246' }, barMaxWidth: 20 }],
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' },
               backgroundColor: '#1C2127', borderColor: '#2F343C',
               textStyle: { color: '#C5CBD3' } },
  });
})();

/* ── Visitor Map (Mapbox GL JS) ── */
(function() {
  mapboxgl.accessToken = '__MAPBOX_TOKEN__';
  var map = new mapboxgl.Map({
    container: 'visitor-map',
    style: 'mapbox://styles/mapbox/dark-v11',
    center: [0, 30], zoom: 1.8,
    projection: 'globe',
  });
  map.addControl(new mapboxgl.NavigationControl(), 'top-right');

  var geo = D.geo;
  if (!geo.length) {
    document.getElementById('geo-note').textContent =
      'No geolocation data yet. Deploy the ip-api.com fix and new visitors will appear on the map.';
    return;
  }

  map.on('load', function() {
    /* Build GeoJSON from analytics data */
    var features = geo.filter(function(g) { return g.lat && g.lon; }).map(function(g) {
      return {
        type: 'Feature',
        geometry: { type: 'Point', coordinates: [g.lon, g.lat] },
        properties: { city: g.city || 'Unknown', country: g.country, count: g.count, ips: g.ips },
      };
    });
    map.addSource('visitors', {
      type: 'geojson',
      data: { type: 'FeatureCollection', features: features },
    });
    /* Glow circle layer */
    map.addLayer({
      id: 'visitor-glow', type: 'circle', source: 'visitors',
      paint: {
        'circle-radius': ['interpolate', ['linear'], ['get', 'count'], 1, 6, 10, 14, 50, 22, 200, 30],
        'circle-color': '#2D72D2',
        'circle-opacity': 0.25,
        'circle-blur': 0.8,
      },
    });
    /* Solid dot layer */
    map.addLayer({
      id: 'visitor-dots', type: 'circle', source: 'visitors',
      paint: {
        'circle-radius': ['interpolate', ['linear'], ['get', 'count'], 1, 3, 10, 6, 50, 10, 200, 14],
        'circle-color': '#2D72D2',
        'circle-opacity': 0.85,
        'circle-stroke-width': 1,
        'circle-stroke-color': '#4B97F7',
      },
    });
    /* Popup on click */
    map.on('click', 'visitor-dots', function(e) {
      var p = e.features[0].properties;
      new mapboxgl.Popup({ closeButton: false, className: 'dark-popup' })
        .setLngLat(e.lngLat)
        .setHTML('<b>' + p.city + ', ' + p.country + '</b><br>' + p.count + ' views, ' + p.ips + ' unique IPs')
        .addTo(map);
    });
    map.on('mouseenter', 'visitor-dots', function() { map.getCanvas().style.cursor = 'pointer'; });
    map.on('mouseleave', 'visitor-dots', function() { map.getCanvas().style.cursor = ''; });
  });
  document.getElementById('geo-note').textContent = geo.length + ' locations tracked.';
})();

/* ── Top Pages ── */
(function() {
  var tp = D.top_pages.slice(0, 15);
  var c = mkChart('chart-pages');
  c.setOption({
    grid: { top: 10, right: 60, bottom: 30, left: 200 },
    xAxis: { type: 'value', splitLine: { lineStyle: { color: DG2.split } },
             axisLabel: { color: DG2.label } },
    yAxis: { type: 'category', data: tp.map(function(d) { return d.path; }).reverse(),
             axisLabel: { color: DG2.label, fontSize: 10, width: 190, overflow: 'truncate' } },
    series: [{ type: 'bar', data: tp.map(function(d) { return d.count; }).reverse(),
               itemStyle: { color: '#2D72D2' }, barMaxWidth: 18,
               label: { show: true, position: 'right', color: DG2.label, fontSize: 10,
                        formatter: function(p) { return p.value; } } }],
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' },
               backgroundColor: '#1C2127', borderColor: '#2F343C',
               textStyle: { color: '#C5CBD3' },
               formatter: function(p) {
                 var idx = tp.length - 1 - p[0].dataIndex;
                 return '<b>' + tp[idx].path + '</b><br>' + tp[idx].count + ' views, ' + tp[idx].avg_ms + 'ms avg';
               } },
  });
})();

/* ── Response Time Dist ── */
(function() {
  var rt = D.response_time_dist;
  var c = mkChart('chart-rt');
  c.setOption({
    grid: { top: 10, right: 16, bottom: 30, left: 50 },
    xAxis: { type: 'category', data: rt.map(function(d) { return d.label; }),
             axisLabel: { color: DG2.label, fontSize: 10 },
             axisLine: { lineStyle: { color: DG2.axis } } },
    yAxis: { type: 'value', splitLine: { lineStyle: { color: DG2.split } },
             axisLabel: { color: DG2.label } },
    series: [{ type: 'bar', data: rt.map(function(d) { return d.count; }),
               itemStyle: { color: '#D1980B' }, barMaxWidth: 40 }],
    tooltip: { trigger: 'axis', backgroundColor: '#1C2127', borderColor: '#2F343C',
               textStyle: { color: '#C5CBD3' } },
  });
})();

/* ── Recent Activity Table ── */
(function() {
  var tbody = document.getElementById('recent-body');
  D.recent.forEach(function(r) {
    var bot = isBot(r.ua);
    var statusClass = r.status >= 400 ? 'status-err' : 'status-ok';
    tbody.innerHTML += '<tr>' +
      '<td style="white-space:nowrap;">' + (r.time || '') + '</td>' +
      '<td style="font-family:monospace;font-size:0.75rem;">' + r.ip + '</td>' +
      '<td>' + r.country + '</td>' +
      '<td>' + r.city + '</td>' +
      '<td>' + r.path + '</td>' +
      '<td class="r ' + statusClass + '">' + r.status + '</td>' +
      '<td class="r">' + (r.ms ? r.ms.toFixed(0) : '-') + '</td>' +
      '<td>' + (bot ? '<span class="bot-tag">BOT</span>' : '<span class="human-tag">HUMAN</span>') + '</td>' +
      '<td style="font-size:0.72rem;color:#5F6B7C;max-width:250px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">' + r.ua + '</td>' +
      '</tr>';
  });
})();
</script>
</body>
</html>"""


class DashboardHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            data = query_analytics()
            html = DASHBOARD_HTML.replace("__DATA__", json.dumps(data)).replace("__MAPBOX_TOKEN__", MAPBOX_TOKEN)
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(html.encode())
        elif self.path == "/api/data":
            data = query_analytics()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(data).encode())
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
