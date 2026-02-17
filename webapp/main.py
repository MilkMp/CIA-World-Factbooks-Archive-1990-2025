from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from webapp.config import settings
from webapp.database import sql_one
from webapp.routers import archive, countries, analysis, analysis2, export

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
