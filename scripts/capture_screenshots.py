"""Capture screenshots of the CIA Factbook webapp for GitHub repo showcase."""
import asyncio
from playwright.async_api import async_playwright

BASE = "http://127.0.0.1:8000"
OUT = "C:/Users/milan/CIA_Factbook_Archive/docs/screenshots"

# (name, path, extra_wait_ms, full_page)
# full_page=False captures only the viewport (1920x1080) — cleaner for README
PAGES = [
    # Core pages
    ("homepage",              "/",                                      None,  False),
    ("search_results",        "/search?q=nuclear",                      None,  False),
    ("search_boolean",        '/search?q="nuclear+weapons"+AND+treaty',  None,  False),
    ("about",                 "/about",                                 None,  False),

    # Archive section
    ("browse_years",          "/archive",                               None,  False),
    ("country_profile",       "/archive/2025/US",                       None,  False),
    ("country_dictionary",    "/countries",                             None,  False),
    ("field_timeseries",      "/archive/field/US/Population",           3000,  False),
    ("country_export",        "/export",                                None,  False),

    # Intelligence Analysis section
    ("analysis_overview",     "/analysis",                              None,  False),
    ("regional_dashboard",    "/analysis/regional",                     3000,  False),
    ("region_eucom",          "/analysis/region/EUCOM",                 3000,  False),
    ("compare_countries",     "/analysis/compare?a=US&b=CN",            None,  False),
    ("timeline_map",          "/analysis/timeline",                     3000,  False),
    ("map_compare",           "/analysis/map-compare",                  3000,  False),
    ("communications",        "/analysis/communications",               3000,  False),
    ("dossier",               "/analysis/dossier/US",                   None,  False),
    ("threats",               "/analysis/threats/EUCOM",                None,  False),
]


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={"width": 1920, "height": 1080})

        for name, path, extra_wait, full_page in PAGES:
            url = f"{BASE}{path}"
            print(f"  Capturing {name} ... {url}")
            await page.goto(url, wait_until="networkidle")
            if extra_wait:
                await page.wait_for_timeout(extra_wait)
            await page.screenshot(
                path=f"{OUT}/{name}.png",
                full_page=full_page,
            )
            print(f"    -> {name}.png saved")

        await browser.close()
    print(f"\nDone! {len(PAGES)} screenshots saved to {OUT}")


if __name__ == "__main__":
    asyncio.run(main())
