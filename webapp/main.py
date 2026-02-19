import logging
import urllib.request
import json
from pathlib import Path
from fastapi import FastAPI, Request, Form
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse
from webapp.config import settings
from webapp.database import sql_one
from webapp.routers import archive, countries, analysis, analysis2, export

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(title=settings.APP_TITLE)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

templates = Jinja2Templates(directory=BASE_DIR / "templates")

# Include routers
app.include_router(archive.router)
app.include_router(countries.router)
app.include_router(analysis.router)
app.include_router(analysis2.router)
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
