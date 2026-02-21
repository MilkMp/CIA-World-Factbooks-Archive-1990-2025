import logging
import urllib.request
import json
import time
from collections import defaultdict
from pathlib import Path
from fastapi import FastAPI, Request, Form
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse, Response, PlainTextResponse
from webapp.config import settings
from webapp.database import sql, sql_one
from webapp.routers import archive, countries, analysis, analysis2, analysis3, analysis4, export

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(title=settings.APP_TITLE)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

# --- Global rate limiter: max 30 req/min per IP across all endpoints ---
_rate_buckets: dict = defaultdict(list)
_last_cleanup: float = time.time()
RATE_LIMIT = 30
RATE_WINDOW = 60.0
BUCKET_MAX_AGE = 300  # prune IPs inactive for 5 minutes

# Paths exempt from global rate limiting (static assets, health checks)
RATE_EXEMPT_PREFIXES = ("/static/",)

GOOD_BOTS = ("googlebot", "bingbot", "slurp", "duckduckbot")

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


@app.middleware("http")
async def security_middleware(request: Request, call_next):
    global _last_cleanup
    now = time.time()

    # --- Global rate limit: 30 req/min per IP, skip static assets and good bots ---
    path = request.url.path
    if not any(path.startswith(p) for p in RATE_EXEMPT_PREFIXES):
        ua = (request.headers.get("user-agent") or "").lower()
        if not any(bot in ua for bot in GOOD_BOTS):
            ip = request.headers.get("x-forwarded-for", request.client.host).split(",")[0].strip()
            _rate_buckets[ip] = [t for t in _rate_buckets[ip] if now - t < RATE_WINDOW]
            if len(_rate_buckets[ip]) >= RATE_LIMIT:
                return PlainTextResponse("Too Many Requests — slow down", status_code=429)
            _rate_buckets[ip].append(now)

    # --- Rate limit /report POST (spam protection) ---
    if request.url.path == "/report" and request.method == "POST":
        ip = request.headers.get("x-forwarded-for", request.client.host).split(",")[0].strip()
        _report_buckets[ip] = [t for t in _report_buckets[ip] if now - t < REPORT_WINDOW]
        if len(_report_buckets[ip]) >= REPORT_LIMIT:
            return PlainTextResponse("Too Many Requests — try again later", status_code=429)
        _report_buckets[ip].append(now)

    response = await call_next(request)

    # --- Security headers on all responses ---
    for header, value in SECURITY_HEADERS.items():
        response.headers[header] = value

    # --- Periodic cleanup of stale rate bucket entries (every 5 min) ---
    if now - _last_cleanup > BUCKET_MAX_AGE:
        cutoff = now - BUCKET_MAX_AGE
        stale = [ip for ip, ts in _rate_buckets.items() if not ts or max(ts) < cutoff]
        for ip in stale:
            del _rate_buckets[ip]
        stale_r = [ip for ip, ts in _report_buckets.items() if not ts or max(ts) < cutoff]
        for ip in stale_r:
            del _report_buckets[ip]
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
