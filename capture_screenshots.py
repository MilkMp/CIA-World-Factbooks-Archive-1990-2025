#!/usr/bin/env python3
"""Capture all screenshots for README and homepage gallery using Playwright."""
import asyncio
import os
import shutil
from playwright.async_api import async_playwright

BASE = "https://cia-factbook-archive.fly.dev"
ADMIN_KEY = os.environ.get("ADMIN_KEY", "")
DOCS_DIR = os.path.join(os.path.dirname(__file__), "docs", "screenshots")
WEB_DIR = os.path.join(os.path.dirname(__file__), "webapp", "static", "img", "screenshots")

# (filename, path)
SCREENSHOTS = [
    # --- The Archive ---
    ("homepage",            "/"),
    ("about",               "/about"),
    ("library",             "/countries"),
    ("search_results",      "/search?q=nuclear+weapons"),
    ("search_boolean",      "/search?q=GDP+AND+growth+NOT+decline"),
    ("browse_years",        "/archive"),
    ("country_profile",     "/archive/2024/US"),
    ("country_dictionary",  "/countries"),
    ("field_timeseries",    "/archive/field/US/GDP%20(purchasing%20power%20parity)"),
    ("country_export",      "/export"),

    # --- Intelligence Analysis ---
    ("analysis_overview",   "/analysis"),
    ("regional_dashboard",  "/analysis/regional"),
    ("region_eucom",        "/analysis/region/EUCOM"),
    ("timeline_map",        "/analysis/timeline"),
    ("map_compare",         "/analysis/map-compare"),
    ("communications",      "/analysis/communications"),
    ("compare_countries",   "/analysis/compare"),
    ("rankings",            "/analysis/rankings"),
    ("global_trends",       "/analysis/trends"),
    ("field_explorer",      "/analysis/fields"),
    ("change_detection",    "/analysis/changes"),
    ("dissolved_states",    "/analysis/dissolved"),
    ("threats",             "/analysis/threats/EUCOM"),
    ("dossier",             "/analysis/dossier/US"),
    ("quiz",                "/analysis/quiz"),

    # --- NEW pages ---
    ("trade_networks",      "/analysis/networks"),
    ("query_builder",       "/analysis/query-builder"),
    ("text_diff",           "/analysis/diff"),
]


async def main():
    os.makedirs(DOCS_DIR, exist_ok=True)
    os.makedirs(WEB_DIR, exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        headers = {"x-admin-key": ADMIN_KEY} if ADMIN_KEY else {}
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            device_scale_factor=2,
            color_scheme="dark",
            extra_http_headers=headers,
        )
        page = await context.new_page()

        for name, path in SCREENSHOTS:
            url = BASE + path
            print(f"[*] Capturing {name} -- {url}")
            try:
                await page.goto(url, wait_until="networkidle", timeout=30000)
                await page.wait_for_timeout(3000)

                fpath = os.path.join(DOCS_DIR, f"{name}.png")
                await page.screenshot(path=fpath, full_page=False)
                shutil.copy2(fpath, os.path.join(WEB_DIR, f"{name}.png"))
                sz = os.path.getsize(fpath) // 1024
                print(f"    -> {sz}KB")
            except Exception as e:
                print(f"    [!] FAILED: {e}")

        # --- Organization Network (tab click) ---
        print("[*] Capturing org_networks")
        await page.goto(BASE + "/analysis/networks", wait_until="networkidle", timeout=30000)
        await page.wait_for_timeout(4000)
        tab = page.locator('[data-tab="orgs"]')
        if await tab.is_visible():
            await tab.click()
            await page.wait_for_timeout(5000)
        fpath = os.path.join(DOCS_DIR, "org_networks.png")
        await page.screenshot(path=fpath, full_page=False)
        shutil.copy2(fpath, os.path.join(WEB_DIR, "org_networks.png"))
        sz = os.path.getsize(fpath) // 1024
        print(f"    -> {sz}KB")

        await browser.close()

    print(f"\n[+] Done! {len(SCREENSHOTS) + 1} screenshots captured at 2x resolution.")


if __name__ == "__main__":
    asyncio.run(main())
