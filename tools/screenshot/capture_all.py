"""
CIA Factbook Archive — Full Page Screenshot Capture
====================================================
Simple page visitor that captures a screenshot of every page in the webapp.
No interactions, just load-and-shoot. For interactive presets, use capture.py.

Usage:
    python capture_all.py                              # Capture all pages
    python capture_all.py --url http://localhost:8000   # Use local server
    python capture_all.py --output ./my_shots           # Custom output dir
    python capture_all.py --headed                      # Visible browser
    python capture_all.py --copy-to DOCS WEB            # Copy to docs/webapp dirs

Requires: playwright (pip install playwright && playwright install chromium)
"""

import argparse
import shutil
import sys
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("ERROR: playwright not installed. Run:")
    print("  pip install playwright")
    print("  playwright install chromium")
    sys.exit(1)


DEFAULT_URL = "http://localhost:8000"
DEFAULT_OUTPUT = Path(__file__).parent / "output"
VIEWPORT = {"width": 1920, "height": 1080}

# (filename, path, wait_ms) — every user-facing page
PAGES = [
    # --- The Archive ---
    ("homepage",            "/",                                              3000),
    ("about",               "/about",                                         2000),
    ("library",             "/countries",                                      3000),
    ("search_results",      "/search?q=nuclear+weapons",                      3000),
    ("search_boolean",      "/search?q=GDP+AND+growth+NOT+decline",           3000),
    ("browse_years",        "/archive",                                       2000),
    ("country_profile",     "/archive/2024/US",                               3000),
    ("country_dictionary",  "/countries",                                      3000),
    ("field_timeseries",    "/archive/field/US/GDP%20(purchasing%20power%20parity)", 3000),
    ("country_export",      "/export",                                        3000),

    # --- Intelligence Analysis ---
    ("analysis_overview",   "/analysis",                                      3000),
    ("regional_dashboard",  "/analysis/regional",                             5000),
    ("region_eucom",        "/analysis/region/EUCOM",                         4000),
    ("timeline_map",        "/analysis/timeline",                             5000),
    ("map_compare",         "/analysis/map-compare",                          5000),
    ("communications",      "/analysis/communications",                       4000),
    ("compare_countries",   "/analysis/compare",                              3000),
    ("rankings",            "/analysis/rankings",                             4000),
    ("global_trends",       "/analysis/trends",                               4000),
    ("field_explorer",      "/analysis/fields",                               3000),
    ("change_detection",    "/analysis/changes",                              3000),
    ("dissolved_states",    "/analysis/dissolved",                             3000),
    ("threats",             "/analysis/threats/EUCOM",                         4000),
    ("dossier",             "/analysis/dossier/US",                            4000),
    ("quiz",                "/analysis/quiz",                                 3000),
    ("trade_networks",      "/analysis/networks",                             6000),
    ("query_builder",       "/analysis/query-builder",                        3000),
    ("text_diff",           "/analysis/diff",                                 3000),
    ("atlas",               "/analysis/atlas",                                6000),

    # --- World Leaders ---
    ("world_leaders",              "/analysis/world-leaders",                  4000),
    ("world_leaders_browse",       "/analysis/world-leaders/browse",           4000),
    ("world_leaders_governance",   "/analysis/world-leaders/governance",       4000),
    ("world_leaders_concentration","/analysis/world-leaders/concentration",    4000),
    ("world_leaders_security",     "/analysis/world-leaders/security",         4000),
    ("world_leaders_map",          "/analysis/world-leaders/map",              5000),

    # --- Demographics & Development ---
    ("demographics",        "/analysis/demographics",                         4000),
    ("development",         "/analysis/development",                          4000),
    ("coverage",            "/analysis/coverage",                             4000),

    # --- Political & Resources ---
    ("political",           "/analysis/political",                            5000),
    ("resources",           "/analysis/resources",                            5000),

    # --- Advanced Analysis ---
    ("scatter",             "/analysis/scatter",                              4000),
    ("explorer",            "/analysis/explorer",                             5000),
    ("dashboard_builder",   "/analysis/dashboard-builder",                    4000),
    ("structured_data",     "/analysis/structured-data",                      4000),

    # --- CSI (CIA Studies in Intelligence) ---
    ("csi_search",          "/analysis/csi",                                  3000),
    ("csi_browse",          "/analysis/csi/browse",                           3000),
    ("csi_dashboard",       "/analysis/csi/dashboard",                        4000),

    # --- Maps ---
    ("maps_gallery",        "/maps",                                          3000),
    ("maps_country",        "/maps/CN",                                       3000),
]


def main():
    parser = argparse.ArgumentParser(
        description="Capture screenshots of every page in the CIA Factbook Archive webapp."
    )
    parser.add_argument(
        "--url", default=DEFAULT_URL,
        help=f"Base URL (default: {DEFAULT_URL})"
    )
    parser.add_argument(
        "--output", type=Path, default=DEFAULT_OUTPUT,
        help=f"Output directory (default: {DEFAULT_OUTPUT})"
    )
    parser.add_argument(
        "--headed", action="store_true",
        help="Run browser in headed mode."
    )
    parser.add_argument(
        "--copy-to", nargs="*", metavar="DIR",
        help="Additional directories to copy screenshots to."
    )
    args = parser.parse_args()

    args.output.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not args.headed)
        context = browser.new_context(
            viewport=VIEWPORT,
            device_scale_factor=2,
            color_scheme="dark",
        )
        page = context.new_page()

        ok, failed = 0, 0
        for name, path, wait_ms in PAGES:
            url = args.url.rstrip("/") + path
            print(f"[*] {name:35s} {url}")
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=60000)
                page.wait_for_timeout(wait_ms)

                fpath = args.output / f"{name}.png"
                page.screenshot(path=str(fpath), full_page=False)
                size_kb = fpath.stat().st_size / 1024
                print(f"    -> {size_kb:.0f} KB")

                # Copy to additional dirs
                for dest in (args.copy_to or []):
                    dest_path = Path(dest)
                    dest_path.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(str(fpath), str(dest_path / f"{name}.png"))

                ok += 1
            except Exception as e:
                print(f"    [!] FAILED: {e}")
                failed += 1

        browser.close()

    print(f"\nDone! {ok}/{ok + failed} screenshots captured.")
    print(f"Output: {args.output}")
    if args.copy_to:
        for d in args.copy_to:
            print(f"Copied to: {d}")


if __name__ == "__main__":
    main()
