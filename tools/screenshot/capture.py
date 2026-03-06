"""
CIA Factbook Archive — Automated Screenshot Tool
=================================================
Captures screenshots of the webapp with specific features toggled on.

Usage:
    python capture.py                          # Run all presets
    python capture.py atlas_eucom              # Run one preset
    python capture.py --list                   # List available presets
    python capture.py --url http://localhost:8000  # Use local dev server
    python capture.py --output ./my_shots      # Custom output directory

Requires: playwright (pip install playwright && playwright install chromium)
"""

import argparse
import json
import sys
import time
from pathlib import Path
from datetime import datetime

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("ERROR: playwright not installed. Run:")
    print("  pip install playwright")
    print("  playwright install chromium")
    sys.exit(1)


# ─── Default config ───────────────────────────────────────────────────────────

DEFAULT_URL = "https://worldfactbookarchive.org"
DEFAULT_OUTPUT = Path(__file__).parent / "output"
VIEWPORT = {"width": 1920, "height": 1080}
WAIT_MS = 3000  # default wait after actions


# ─── Preset definitions ──────────────────────────────────────────────────────
# Each preset is a dict with:
#   name:        filename-safe identifier
#   description: human-readable description
#   path:        URL path to navigate to
#   actions:     list of actions to perform (JS evals, clicks, waits)
#   viewport:    optional override for viewport size
#   wait_after:  ms to wait after all actions before screenshot

PRESETS = {
    "atlas_eucom_osint": {
        "name": "atlas_eucom_osint",
        "description": "Atlas: EUCOM region with military bases, nuclear facilities, and mining/resources",
        "path": "/analysis/atlas",
        "wait_for_load": 6000,
        "actions": [
            {"type": "js", "code": "toggleLayer('milbases')", "wait": 2000},
            {"type": "js", "code": "toggleLayer('nuclear')", "wait": 2000},
            {"type": "js", "code": "toggleLayer('mining')", "wait": 2000},
            {"type": "js", "code": "flyToRegion('EUCOM')", "wait": 4000},
        ],
        "wait_after": 3000,
    },
    "atlas_indopacom_military": {
        "name": "atlas_indopacom_military",
        "description": "Atlas: INDOPACOM region with military bases and missile ranges",
        "path": "/analysis/atlas",
        "wait_for_load": 6000,
        "actions": [
            {"type": "js", "code": "toggleLayer('milbases')", "wait": 2000},
            {"type": "js", "code": "toggleLayer('missiles')", "wait": 2000},
            {"type": "js", "code": "toggleLayer('ranges')", "wait": 2000},
            {"type": "js", "code": "flyToRegion('INDOPACOM')", "wait": 4000},
        ],
        "wait_after": 3000,
    },
    "atlas_global_nightlights": {
        "name": "atlas_global_nightlights",
        "description": "Atlas: Global view with NASA VIIRS night lights",
        "path": "/analysis/atlas",
        "wait_for_load": 6000,
        "actions": [
            {"type": "js", "code": "toggleLayer('nightlights')", "wait": 3000},
            {"type": "js", "code": "flyToRegion('World')", "wait": 3000},
        ],
        "wait_after": 3000,
    },
    "atlas_centcom_missiles": {
        "name": "atlas_centcom_missiles",
        "description": "Atlas: CENTCOM with missile sites and range rings",
        "path": "/analysis/atlas",
        "wait_for_load": 6000,
        "actions": [
            {"type": "js", "code": "toggleLayer('msites')", "wait": 2000},
            {"type": "js", "code": "toggleLayer('ranges')", "wait": 2000},
            {"type": "js", "code": "toggleLayer('cocom')", "wait": 2000},
            {"type": "js", "code": "flyToRegion('CENTCOM')", "wait": 4000},
        ],
        "wait_after": 3000,
    },
    "atlas_cables_shipping": {
        "name": "atlas_cables_shipping",
        "description": "Atlas: Submarine cables and shipping routes",
        "path": "/analysis/atlas",
        "wait_for_load": 6000,
        "actions": [
            {"type": "js", "code": "toggleLayer('cables')", "wait": 2000},
            {"type": "js", "code": "toggleLayer('shipping')", "wait": 2000},
            {"type": "js", "code": "flyToRegion('World')", "wait": 3000},
        ],
        "wait_after": 3000,
    },
    "dashboard_germany_deepdive": {
        "name": "dashboard_germany_deepdive",
        "description": "Dashboard Builder: Deep Dive preset for Germany (EUCOM)",
        "path": "/analysis/dashboard-builder",
        "wait_for_load": 3000,
        "actions": [
            # Select Germany in the country dropdown
            {"type": "js", "code": """
                var sel = document.getElementById('db-preset-country');
                if (sel) {
                    for (var i = 0; i < sel.options.length; i++) {
                        if (sel.options[i].text.includes('Germany')) {
                            sel.value = sel.options[i].value;
                            break;
                        }
                    }
                }
            """, "wait": 500},
            # Select 2025 year
            {"type": "js", "code": """
                var yr = document.getElementById('db-preset-year');
                if (yr) { yr.value = '2025'; }
            """, "wait": 500},
            # Click Deep Dive preset
            {"type": "js", "code": "dbPreset()", "wait": 5000},
        ],
        "wait_after": 5000,
    },
    "dashboard_china_deepdive": {
        "name": "dashboard_china_deepdive",
        "description": "Dashboard Builder: Deep Dive preset for China",
        "path": "/analysis/dashboard-builder",
        "wait_for_load": 3000,
        "actions": [
            {"type": "js", "code": """
                var sel = document.getElementById('db-preset-country');
                if (sel) {
                    for (var i = 0; i < sel.options.length; i++) {
                        if (sel.options[i].text.includes('China')) {
                            sel.value = sel.options[i].value;
                            break;
                        }
                    }
                }
            """, "wait": 500},
            {"type": "js", "code": """
                var yr = document.getElementById('db-preset-year');
                if (yr) { yr.value = '2025'; }
            """, "wait": 500},
            {"type": "js", "code": "dbPreset()", "wait": 5000},
        ],
        "wait_after": 5000,
    },
    "trends_population": {
        "name": "trends_population",
        "description": "Trend Analysis: Population for US, China, India, Russia",
        "path": "/analysis/trends?indicator=population&countries=US,CH,IN,RS&start=1990&end=2025",
        "wait_for_load": 5000,
        "actions": [],
        "wait_after": 3000,
    },
    "rankings_gdp_2025": {
        "name": "rankings_gdp_2025",
        "description": "Rankings: GDP (PPP) for 2025, top 20",
        "path": "/analysis/rankings?indicator=gdp_ppp&year=2025&limit=20",
        "wait_for_load": 5000,
        "actions": [],
        "wait_after": 3000,
    },
    "country_soviet_1991": {
        "name": "country_soviet_1991",
        "description": "Country page: Soviet Union, 1991 (final edition)",
        "path": "/country/XX/1991",
        "wait_for_load": 3000,
        "actions": [],
        "wait_after": 2000,
    },
}


# ─── Core screenshot engine ──────────────────────────────────────────────────

def capture_preset(page, preset: dict, base_url: str, output_dir: Path) -> Path:
    """Navigate to a page, execute actions, and capture a screenshot."""
    name = preset["name"]
    url = base_url.rstrip("/") + preset["path"]

    print(f"  [{name}] Navigating to {url}")
    page.goto(url, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(preset.get("wait_for_load", 3000))

    # Execute each action
    for i, action in enumerate(preset.get("actions", [])):
        if action["type"] == "js":
            print(f"  [{name}] Action {i+1}: JS eval")
            page.evaluate(action["code"])
        elif action["type"] == "click":
            print(f"  [{name}] Action {i+1}: Click {action['selector']}")
            page.click(action["selector"])
        page.wait_for_timeout(action.get("wait", 1000))

    # Final wait for animations/renders to settle
    page.wait_for_timeout(preset.get("wait_after", WAIT_MS))

    # Capture
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{name}_{timestamp}.png"
    filepath = output_dir / filename
    page.screenshot(path=str(filepath), full_page=False)
    size_kb = filepath.stat().st_size / 1024
    print(f"  [{name}] Saved: {filepath.name} ({size_kb:.0f} KB)")
    return filepath


def run(preset_names: list, base_url: str, output_dir: Path, headless: bool = True):
    """Run one or more preset captures."""
    output_dir.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context(
            viewport=VIEWPORT,
            device_scale_factor=2,  # Retina-quality screenshots
        )
        page = context.new_page()

        results = []
        for name in preset_names:
            preset = PRESETS[name]
            print(f"\n{'='*60}")
            print(f"Capturing: {preset['description']}")
            print(f"{'='*60}")
            try:
                path = capture_preset(page, preset, base_url, output_dir)
                results.append({"preset": name, "file": str(path), "status": "ok"})
            except Exception as e:
                print(f"  ERROR: {e}")
                results.append({"preset": name, "error": str(e), "status": "failed"})

        browser.close()

    # Summary
    print(f"\n{'='*60}")
    print(f"Done. {len([r for r in results if r['status']=='ok'])}/{len(results)} screenshots captured.")
    print(f"Output: {output_dir}")
    print(f"{'='*60}")
    return results


# ─── CLI ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Capture screenshots of the CIA Factbook Archive webapp."
    )
    parser.add_argument(
        "presets", nargs="*", default=[],
        help="Preset names to capture (default: all). Use --list to see options."
    )
    parser.add_argument(
        "--list", action="store_true",
        help="List all available presets and exit."
    )
    parser.add_argument(
        "--url", default=DEFAULT_URL,
        help=f"Base URL of the webapp (default: {DEFAULT_URL})"
    )
    parser.add_argument(
        "--output", type=Path, default=DEFAULT_OUTPUT,
        help=f"Output directory for screenshots (default: {DEFAULT_OUTPUT})"
    )
    parser.add_argument(
        "--headed", action="store_true",
        help="Run browser in headed mode (visible window) for debugging."
    )
    args = parser.parse_args()

    if args.list:
        print("Available presets:\n")
        for name, preset in PRESETS.items():
            print(f"  {name:35s} {preset['description']}")
        print(f"\nTotal: {len(PRESETS)} presets")
        return

    preset_names = args.presets if args.presets else list(PRESETS.keys())

    # Validate preset names
    for name in preset_names:
        if name not in PRESETS:
            print(f"ERROR: Unknown preset '{name}'")
            print(f"Use --list to see available presets.")
            sys.exit(1)

    run(preset_names, args.url, args.output, headless=not args.headed)


if __name__ == "__main__":
    main()
