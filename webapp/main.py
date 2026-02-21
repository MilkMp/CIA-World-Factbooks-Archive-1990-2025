import logging
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

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(title=settings.APP_TITLE)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

# --- Targeted rate limiter: only on heavy scrape-prone endpoints ---
# Keyed by (ip, prefix). Since Fly.io internal proxy masks real IPs,
# we limit only endpoints no real user hits 10+ times per minute.
_rate_buckets: dict = defaultdict(list)
_last_cleanup: float = time.time()
BUCKET_MAX_AGE = 300

# (path_prefix, max_requests, window_seconds)
RATE_RULES = [
    ("/export/",         5,  60.0),   # bulk CSV/XLSX downloads
    ("/archive/field/",  6,  60.0),   # individual field pages
    ("/archive/",        6,  60.0),   # country archive pages
    ("/countries",       6,  60.0),   # country listing pages
    ("/api/",            15, 60.0),   # API endpoints
    # No catch-all — Fly.io proxy shares 172.16.8.250 across all users
]

GOOD_BOTS = ("googlebot", "bingbot", "slurp", "duckduckbot")

# Block requests with no UA or known scraper/bot UAs
BAD_BOTS = ("python-requests", "scrapy", "python-urllib", "go-http-client",
            "java/", "libwww-perl", "wget", "httpx")

# --- Escalating ban: too many 429s = full block ---
_ban_strikes: dict = defaultdict(list)   # ip -> list of 429 timestamps
_banned_until: dict = {}                  # ip -> ban expiry timestamp
BAN_STRIKE_LIMIT = 6                      # 429 hits before ban
BAN_STRIKE_WINDOW = 300.0                 # count strikes in 5-min window
BAN_DURATION = 3600.0                     # banned for 1 hour

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
    is_bot = any(bot in ua for bot in GOOD_BOTS)

    # Extract visitor IP once — used by rate limiter + analytics
    ip = (
        request.headers.get("fly-client-ip")
        or request.headers.get("x-forwarded-for", "").split(",")[0].strip()
        or request.client.host
    )

    # --- Check escalating ban first (resets on every hit — must stop to get unbanned) ---
    ban_expiry = _banned_until.get(ip)
    if ban_expiry and now < ban_expiry:
        _banned_until[ip] = now + BAN_DURATION  # reset the clock
        return PlainTextResponse("Forbidden", status_code=403)
    elif ban_expiry:
        del _banned_until[ip]  # ban expired, clean up

    # --- Block known bad bots (scraper libraries) ---
    # Don't block empty UA — Fly.io health checks and probes may not send one
    if not path.startswith("/static/") and not is_bot:
        if ua and any(bot in ua for bot in BAD_BOTS):
            return PlainTextResponse("Forbidden", status_code=403)

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
                        _banned_until[ip] = now + BAN_DURATION
                        logger.warning("BANNED ip=%s for %ds after %d strikes", ip, BAN_DURATION, len(_ban_strikes[ip]))
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
        # All other bots — 2 second crawl delay
        "User-agent: *\n"
        "Allow: /\n"
        "Disallow: /api/\n"
        "Disallow: /report\n"
        "Disallow: /export/bulk/\n"
        "Disallow: /export/print\n"
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
