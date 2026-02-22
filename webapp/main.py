import asyncio
import logging
import os
import urllib.request
import json
import time
import uuid
from collections import defaultdict
from pathlib import Path
from fastapi import FastAPI, Request, Form
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse, Response, PlainTextResponse
from webapp.config import settings
from webapp.database import sql, sql_one
from webapp.routers import archive, countries, analysis, analysis2, analysis3, analysis4, export
from webapp.routers import analytics as analytics_router
from webapp.bot_taxonomy import classify_ua, BOT_TAXONOMY

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(title=settings.APP_TITLE)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

# --- Targeted rate limiter: only on heavy scrape-prone endpoints ---
_rate_buckets: dict = defaultdict(list)
_last_cleanup: float = time.time()
BUCKET_MAX_AGE = 300

# (path_prefix, max_requests, window_seconds)
# Generous limits — real users browse fast; only block actual scrapers
RATE_RULES = [
    ("/export/",         20, 60.0),   # bulk CSV/XLSX downloads
    ("/archive/field/",  40, 60.0),   # individual field pages
    ("/archive/",        40, 60.0),   # country archive pages
    ("/countries",       40, 60.0),   # country listing pages
    ("/api/",            80, 60.0),   # API endpoints (pages make multiple calls)
]

# Bot classification is now in webapp/bot_taxonomy.py
# Actions: "allow" (exempt from limits), "rate_limit" (tighter limits), "block" (instant ban)

# --- Honeypot: fake paths only scrapers follow (listed as Disallow in robots.txt) ---
HONEYPOT_PATHS = ("/admin", "/database", "/wp-admin", "/wp-login", "/.env", "/backup")

# --- Admin bypass: scripts with this header skip all rate limiting/bans ---
ADMIN_KEY = os.environ.get("ADMIN_KEY", "")

# --- Escalating ban: too many 429s = full block ---
_ban_strikes: dict = defaultdict(list)   # ip -> list of 429 timestamps
_banned_until: dict = {}                  # ip -> ban expiry timestamp
_ban_count: dict = defaultdict(int)       # ip -> cumulative ban count (for escalation)
_ban_count_ts: dict = {}                  # ip -> first ban timestamp (reset after 24h)
BAN_STRIKE_LIMIT = 15                     # 429 hits before ban
BAN_STRIKE_WINDOW = 300.0                 # count strikes in 5-min window
BAN_DURATIONS = [300, 1800, 7200, 86400]  # escalating: 5min, 30min, 2hr, 24hr
TARPIT_DELAY = 5.0                        # seconds to delay banned/honeypot responses

# --- Global per-IP rate limit (catches bots that spread across endpoints) ---
_ip_global: dict = defaultdict(list)      # ip -> list of timestamps for all page loads
IP_GLOBAL_LIMIT = 100                     # max non-API page loads in window
IP_GLOBAL_WINDOW = 1800.0                 # 30-minute window
# Paths excluded from global counter (API calls are triggered by page loads, not direct)
GLOBAL_SKIP = ("/static/", "/favicon.ico", "/health", "/metrics", "/api/")

# --- Persistent ban data: survives server restarts ---
BANDATA_PATH = os.environ.get("BANDATA_PATH", "/data/bandata.json")


def _load_bandata():
    """Load persistent ban/escalation data from disk."""
    try:
        with open(BANDATA_PATH) as f:
            data = json.load(f)
        return (
            defaultdict(int, {k: int(v) for k, v in data.get("ban_count", {}).items()}),
            data.get("ban_count_ts", {}),
            {k: float(v) for k, v in data.get("banned_until", {}).items()},
        )
    except (FileNotFoundError, json.JSONDecodeError, ValueError):
        return defaultdict(int), {}, {}


def _save_bandata():
    """Persist ban data to disk (non-blocking, best-effort)."""
    try:
        data = {
            "ban_count": dict(_ban_count),
            "ban_count_ts": _ban_count_ts,
            "banned_until": _banned_until,
        }
        with open(BANDATA_PATH, "w") as f:
            json.dump(data, f)
    except Exception:
        pass  # don't break the server if save fails


# Load persistent bans on startup
_bc, _bcts, _bu = _load_bandata()
if _bc:
    _ban_count.update(_bc)
    _ban_count_ts.update(_bcts)
    _banned_until.update(_bu)
    logger.info("Loaded %d ban records, %d active bans from disk", len(_bc), len(_bu))

# --- Report form: max 5 submissions per IP per hour ---
_report_buckets: dict = defaultdict(list)
REPORT_LIMIT = 5
REPORT_WINDOW = 3600.0

SECURITY_HEADERS = {
    "X-Frame-Options": "DENY",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
}


ANALYTICS_SKIP = ("/static/", "/favicon.ico", "/health", "/metrics", "/api/analytics/")


@app.middleware("http")
async def security_middleware(request: Request, call_next):
    global _last_cleanup
    now = time.time()
    path = request.url.path
    ua = (request.headers.get("user-agent") or "").lower()
    bot_category, bot_action = classify_ua(ua)
    is_bot = bot_category != "human"

    # --- Admin bypass: skip ALL rate limiting and bans ---
    if ADMIN_KEY and request.headers.get("x-admin-key") == ADMIN_KEY:
        response = await call_next(request)
        return response

    # Extract visitor IP once — used by rate limiter + analytics
    ip = (
        request.headers.get("fly-client-ip")
        or request.headers.get("x-forwarded-for", "").split(",")[0].strip()
        or request.client.host
    )

    # --- Honeypot: instant ban, only scrapers hit these ---
    if any(path.startswith(hp) for hp in HONEYPOT_PATHS):
        _ban_count[ip] += 1
        _ban_count_ts.setdefault(ip, now)
        dur = BAN_DURATIONS[min(_ban_count[ip] - 1, len(BAN_DURATIONS) - 1)]
        _banned_until[ip] = now + dur
        _save_bandata()
        logger.warning("HONEYPOT ip=%s path=%s — ban #%d (%ds)", ip, path, _ban_count[ip], dur)
        await asyncio.sleep(TARPIT_DELAY)
        return PlainTextResponse("", status_code=404)

    # --- Check escalating ban (expires naturally — does NOT reset on every hit) ---
    ban_expiry = _banned_until.get(ip)
    if ban_expiry and now < ban_expiry:
        await asyncio.sleep(TARPIT_DELAY)
        return PlainTextResponse("Forbidden", status_code=403)
    elif ban_expiry:
        del _banned_until[ip]  # ban expired, clean up

    # --- Block bad bots: scrapers + security scanners ---
    if not path.startswith("/static/") and bot_action == "block":
        _ban_count[ip] += 1
        _ban_count_ts.setdefault(ip, now)
        dur = BAN_DURATIONS[min(_ban_count[ip] - 1, len(BAN_DURATIONS) - 1)]
        _banned_until[ip] = now + dur
        _save_bandata()
        logger.warning("BLOCKED %s ip=%s ua=%s — ban #%d (%ds)", bot_category, ip, ua, _ban_count[ip], dur)
        await asyncio.sleep(TARPIT_DELAY)
        return PlainTextResponse("Forbidden", status_code=403)

    # --- Global per-IP rate limit (catches bots spreading across endpoints) ---
    # Allow-action bots (search engines, social preview, etc.) skip global limit
    if bot_action != "allow" and not any(path.startswith(p) for p in GLOBAL_SKIP):
        _ip_global[ip] = [t for t in _ip_global[ip] if now - t < IP_GLOBAL_WINDOW]
        if len(_ip_global[ip]) >= IP_GLOBAL_LIMIT:
            _ban_count[ip] += 1
            _ban_count_ts.setdefault(ip, now)
            dur = BAN_DURATIONS[min(_ban_count[ip] - 1, len(BAN_DURATIONS) - 1)]
            _banned_until[ip] = now + dur
            _save_bandata()
            logger.warning("GLOBAL_BAN ip=%s ban #%d (%ds) — %d page reqs in 30min", ip, _ban_count[ip], dur, len(_ip_global[ip]))
            return PlainTextResponse("Forbidden", status_code=403)
        _ip_global[ip].append(now)

    # --- Targeted rate limit per endpoint group, skip good bots ---
    if not is_bot:
        for prefix, limit, window in RATE_RULES:
            if path.startswith(prefix):
                key = (ip, prefix)
                _rate_buckets[key] = [t for t in _rate_buckets[key] if now - t < window]
                bucket_size = len(_rate_buckets[key])
                logger.info("RATELIMIT ip=%s prefix=%s bucket=%d/%d path=%s", ip, prefix, bucket_size, limit, path)
                if bucket_size >= limit:
                    # Record strike for escalating ban
                    _ban_strikes[ip] = [t for t in _ban_strikes[ip] if now - t < BAN_STRIKE_WINDOW]
                    _ban_strikes[ip].append(now)
                    if len(_ban_strikes[ip]) >= BAN_STRIKE_LIMIT:
                        _ban_count[ip] += 1
                        _ban_count_ts.setdefault(ip, now)
                        dur = BAN_DURATIONS[min(_ban_count[ip] - 1, len(BAN_DURATIONS) - 1)]
                        _banned_until[ip] = now + dur
                        _save_bandata()
                        logger.warning("BANNED ip=%s ban #%d (%ds) after %d strikes", ip, _ban_count[ip], dur, len(_ban_strikes[ip]))
                        return PlainTextResponse("Forbidden", status_code=403)
                    return PlainTextResponse("Too Many Requests — slow down", status_code=429)
                _rate_buckets[key].append(now)
                break

    # --- Rate limit /report POST (spam protection) ---
    if path == "/report" and request.method == "POST":
        _report_buckets[ip] = [t for t in _report_buckets[ip] if now - t < REPORT_WINDOW]
        if len(_report_buckets[ip]) >= REPORT_LIMIT:
            return PlainTextResponse("Too Many Requests — try again later", status_code=429)
        _report_buckets[ip].append(now)

    response = await call_next(request)

    # --- Security headers on all responses ---
    for header, value in SECURITY_HEADERS.items():
        response.headers[header] = value

    # --- Cache-Control: let browsers/CDN cache archive pages (read-only data) ---
    if path.startswith("/archive/") or path.startswith("/countries"):
        response.headers["Cache-Control"] = "public, max-age=3600, stale-while-revalidate=86400"

    # --- Analytics: record page view (skip static, bots, internal endpoints) ---
    if not any(path.startswith(p) for p in ANALYTICS_SKIP) and not is_bot:
        elapsed_ms = (time.time() - now) * 1000
        session_id = request.cookies.get("session_id", "")
        try:
            analytics_router.record_page_view(
                ip=ip, path=path, method=request.method,
                status_code=response.status_code,
                referrer=request.headers.get("referer", ""),
                user_agent=request.headers.get("user-agent", "")[:500],
                session_id=session_id,
                response_ms=round(elapsed_ms, 1),
            )
        except Exception:
            pass  # never break the response for analytics

        # Set session cookie if missing
        if not session_id:
            response.set_cookie(
                "session_id", str(uuid.uuid4()),
                max_age=365 * 24 * 3600,
                httponly=True,
                samesite="lax",
            )

    # --- Periodic cleanup of stale rate bucket entries (every 5 min) ---
    if now - _last_cleanup > BUCKET_MAX_AGE:
        cutoff = now - BUCKET_MAX_AGE
        stale_keys = [k for k, ts in _rate_buckets.items() if not ts or max(ts) < cutoff]
        for k in stale_keys:
            del _rate_buckets[k]
        stale_r = [k for k, ts in _report_buckets.items() if not ts or max(ts) < cutoff]
        for k in stale_r:
            del _report_buckets[k]
        stale_s = [k for k, ts in _ban_strikes.items() if not ts or max(ts) < cutoff]
        for k in stale_s:
            del _ban_strikes[k]
        expired_bans = [k for k, exp in _banned_until.items() if now >= exp]
        for k in expired_bans:
            del _banned_until[k]
        # Clean up global per-IP buckets
        stale_g = [k for k, ts in _ip_global.items() if not ts or max(ts) < cutoff]
        for k in stale_g:
            del _ip_global[k]
        # Clean up ban counts older than 24 hours (let persistent bots accumulate)
        stale_bc = [k for k, ts in _ban_count_ts.items() if now - ts > 86400]
        for k in stale_bc:
            del _ban_count[k]
            del _ban_count_ts[k]
        _save_bandata()  # periodic persist
        _last_cleanup = now

    return response

templates = Jinja2Templates(directory=BASE_DIR / "templates")

# Include routers
app.include_router(archive.router)
app.include_router(countries.router)
app.include_router(analysis.router)
app.include_router(analysis2.router)
app.include_router(analysis3.router)
app.include_router(analysis4.router)
app.include_router(export.router)
app.include_router(analytics_router.router)


@app.get("/api", include_in_schema=False)
async def api_docs_page(request: Request):
    return templates.TemplateResponse("api_docs.html", {"request": request})


@app.get("/sources")
async def sources(request: Request):
    return templates.TemplateResponse("sources.html", {"request": request})


@app.get("/about")
async def about(request: Request):
    return templates.TemplateResponse("about.html", {"request": request})


@app.get("/report")
async def report_bug_page(request: Request):
    return templates.TemplateResponse("report.html", {
        "request": request, "submitted": False,
    })


CATEGORY_LABELS = {
    "bug": "bug",
    "data": "data issue",
    "ui": "ui",
    "feature": "enhancement",
    "other": "question",
}


def _create_github_issue(category: str, description: str, page_url: str):
    """Create a GitHub Issue via the REST API. Returns True on success."""
    token = settings.GITHUB_TOKEN
    if not token:
        logger.warning("GITHUB_TOKEN not set -- bug report not filed")
        return False

    label = CATEGORY_LABELS.get(category, "bug")
    title_prefix = {
        "bug": "Bug",
        "data": "Data Issue",
        "ui": "UI Issue",
        "feature": "Feature Request",
        "other": "Feedback",
    }.get(category, "Bug")

    # Title: first 80 chars of description
    summary = description.split("\n")[0][:80]
    title = f"[{title_prefix}] {summary}"

    body = f"**Category:** {category}\n"
    if page_url:
        body += f"**Page:** `{page_url}`\n"
    body += f"\n---\n\n{description}\n\n---\n*Submitted via the bug report form.*"

    payload = json.dumps({
        "title": title,
        "body": body,
        "labels": [label, "user-report"],
    }).encode()

    req = urllib.request.Request(
        f"https://api.github.com/repos/{settings.GITHUB_REPO}/issues",
        data=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        resp = urllib.request.urlopen(req, timeout=10)
        return resp.getcode() == 201
    except Exception as e:
        logger.error("Failed to create GitHub Issue: %s", e)
        return False


@app.post("/report")
async def report_bug_submit(request: Request,
                            page_url: str = Form(""),
                            category: str = Form("bug"),
                            description: str = Form("")):
    if description.strip():
        _create_github_issue(category.strip(), description.strip(), page_url.strip())
    return templates.TemplateResponse("report.html", {
        "request": request, "submitted": True,
    })


BASE_URL = "https://cia-factbook-archive.fly.dev"

STATIC_PAGES = [
    ("/", "1.0", "weekly"),
    ("/archive", "0.9", "weekly"),
    ("/archive/library", "0.9", "weekly"),
    ("/countries", "0.9", "monthly"),
    ("/search", "0.8", "monthly"),
    ("/analysis", "0.9", "weekly"),
    ("/analysis/regional", "0.9", "weekly"),
    ("/analysis/timeline", "0.8", "monthly"),
    ("/analysis/map-compare", "0.8", "monthly"),
    ("/analysis/rankings", "0.8", "weekly"),
    ("/analysis/compare", "0.8", "monthly"),
    ("/analysis/communications", "0.7", "monthly"),
    ("/analysis/changes", "0.7", "monthly"),
    ("/analysis/dissolved", "0.6", "monthly"),
    ("/analysis/trends", "0.8", "weekly"),
    ("/analysis/fields", "0.7", "monthly"),
    ("/analysis/explorer", "0.7", "monthly"),
    ("/analysis/query-builder", "0.7", "monthly"),
    ("/analysis/networks", "0.7", "monthly"),
    ("/analysis/quiz", "0.6", "monthly"),
    ("/analysis/diff", "0.7", "monthly"),
    ("/export", "0.7", "monthly"),
    ("/api", "0.5", "monthly"),
    ("/about", "0.4", "yearly"),
    ("/sources", "0.4", "yearly"),
    ("/report", "0.3", "yearly"),
]


@app.get("/sitemap.xml", include_in_schema=False)
async def sitemap():
    urls = []
    for path, priority, freq in STATIC_PAGES:
        urls.append(
            f'  <url><loc>{BASE_URL}{path}</loc>'
            f'<changefreq>{freq}</changefreq>'
            f'<priority>{priority}</priority></url>'
        )

    # Dynamic: /archive/{year}
    years = sql("SELECT DISTINCT Year FROM Countries ORDER BY Year")
    for row in years:
        y = row["Year"]
        urls.append(
            f'  <url><loc>{BASE_URL}/archive/{y}</loc>'
            f'<changefreq>yearly</changefreq><priority>0.6</priority></url>'
        )

    # Dynamic: /archive/{year}/{code} for latest year
    if years:
        latest = years[-1]["Year"]
        country_years = sql(
            "SELECT DISTINCT mc.ISOAlpha2 AS code FROM Countries c JOIN MasterCountries mc ON c.MasterCountryID = mc.MasterCountryID WHERE c.Year = ? AND mc.ISOAlpha2 IS NOT NULL",
            (latest,)
        )
        for row in country_years:
            urls.append(
                f'  <url><loc>{BASE_URL}/archive/{latest}/{row["code"]}</loc>'
                f'<changefreq>yearly</changefreq><priority>0.5</priority></url>'
            )

    # Dynamic: /analysis/dossier/{code}
    master = sql("SELECT ISOAlpha2 AS code FROM MasterCountries WHERE EntityType = 'sovereign' AND ISOAlpha2 IS NOT NULL ORDER BY ISOAlpha2")
    for row in master:
        urls.append(
            f'  <url><loc>{BASE_URL}/analysis/dossier/{row["code"]}</loc>'
            f'<changefreq>monthly</changefreq><priority>0.6</priority></url>'
        )

    xml = '<?xml version="1.0" encoding="UTF-8"?>\n'
    xml += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    xml += '\n'.join(urls)
    xml += '\n</urlset>'
    return Response(content=xml, media_type="application/xml")


@app.get("/robots.txt", include_in_schema=False)
async def robots_txt():
    # Build AI crawler blocks from taxonomy
    ai_blocks = ""
    for bot in BOT_TAXONOMY["ai_crawler"]["patterns"]:
        ai_blocks += f"User-agent: {bot}\nDisallow: /\n\n"

    content = (
        # Google — crawl freely, no delay
        "User-agent: Googlebot\n"
        "Allow: /\n"
        "Disallow: /api/\n"
        "Disallow: /report\n"
        "Disallow: /export/bulk/\n"
        "Disallow: /export/print\n"
        "\n"
        # Bing — crawl freely, no delay
        "User-agent: Bingbot\n"
        "Allow: /\n"
        "Disallow: /api/\n"
        "Disallow: /report\n"
        "Disallow: /export/bulk/\n"
        "Disallow: /export/print\n"
        "\n"
        # AI crawlers — block entirely (training data scrapers)
        + ai_blocks +
        # All other bots — 2 second crawl delay
        "User-agent: *\n"
        "Allow: /\n"
        "Disallow: /api/\n"
        "Disallow: /report\n"
        "Disallow: /export/bulk/\n"
        "Disallow: /export/print\n"
        "Disallow: /admin\n"
        "Disallow: /database\n"
        "Disallow: /wp-admin\n"
        "Disallow: /wp-login\n"
        "Disallow: /.env\n"
        "Disallow: /backup\n"
        "Crawl-delay: 2\n"
        "\n"
        f"Sitemap: {BASE_URL}/sitemap.xml\n"
    )
    return Response(content=content, media_type="text/plain")


@app.get("/")
async def index(request: Request):
    stats = sql_one("""
        SELECT
            (SELECT COUNT(*) FROM MasterCountries) AS master_countries,
            (SELECT COUNT(*) FROM Countries) AS country_years,
            (SELECT COUNT(DISTINCT Year) FROM Countries) AS years_covered,
            (SELECT MIN(Year) FROM Countries) AS first_year,
            (SELECT MAX(Year) FROM Countries) AS last_year,
            (SELECT COUNT(*) FROM CountryFields) AS total_fields,
            (SELECT COUNT(*) FROM FieldNameMappings WHERE IsNoise = 0) AS canonical_fields
    """)
    return templates.TemplateResponse("index.html", {"request": request, "stats": stats})
