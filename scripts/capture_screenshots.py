"""Capture screenshots of the CIA Factbook webapp for GitHub repo showcase."""
import asyncio
from playwright.async_api import async_playwright

BASE = "http://127.0.0.1:8080"
OUT = "C:/Users/milan/CIA-World-Factbooks-Archive-1990-2025/docs/screenshots"

PAGES = [
    # Core pages
    ("homepage",              "/",                                    None),
    ("search_results",        "/search?q=nuclear",                    None),
    ("search_boolean",        '/search?q="nuclear+weapons"+AND+treaty', None),
    ("about",                 "/about",                               None),

    # Archive section
    ("browse_years",          "/archive",                             None),
    ("country_profile",       "/archive/2025/US",                     None),
    ("country_dictionary",    "/countries",                           None),
    ("field_timeseries",      "/archive/field/US/Population",         3000),
    ("country_export",        "/export",                              None),

    # Intelligence Analysis section
    ("analysis_overview",     "/analysis",                            None),
    ("regional_dashboard",    "/analysis/regional",                   3000),
    ("region_eucom",          "/analysis/region/EUCOM",               3000),
    ("compare_countries",     "/analysis/compare?a=US&b=CN",          None),
    ("timeline_map",          "/analysis/timeline",                   3000),
    ("map_compare",           "/analysis/map-compare",                3000),
    ("communications",        "/analysis/communications",             3000),
    ("dossier",               "/analysis/dossier/US",                 None),
    ("threats",               "/analysis/threats/EUCOM",              None),
]


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={"width": 1920, "height": 1080})

        for name, path, extra_wait in PAGES:
            url = f"{BASE}{path}"
            print(f"  Capturing {name} ... {url}")
            await page.goto(url, wait_until="networkidle")
            if extra_wait:
                await page.wait_for_timeout(extra_wait)
            await page.screenshot(
                path=f"{OUT}/{name}.png",
                full_page=True,
            )
            print(f"    -> {name}.png saved")

        await browser.close()
    print(f"\nDone! {len(PAGES)} screenshots saved to {OUT}")


if __name__ == "__main__":
    asyncio.run(main())
