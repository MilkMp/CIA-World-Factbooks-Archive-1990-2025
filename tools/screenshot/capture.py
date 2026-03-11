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

    # ─── World Leaders ───────────────────────────────────────────────
    "world_leaders_china": {
        "name": "world_leaders_china",
        "description": "World Leaders: China government roster with structure chart",
        "path": "/analysis/world-leaders",
        "wait_for_load": 4000,
        "actions": [
            {"type": "js", "code": """
                var sel = document.getElementById('wl-country-select');
                if (sel) {
                    for (var i = 0; i < sel.options.length; i++) {
                        if (sel.options[i].text.includes('China')) {
                            sel.value = sel.options[i].value;
                            sel.dispatchEvent(new Event('change'));
                            break;
                        }
                    }
                }
            """, "wait": 3000},
        ],
        "wait_after": 3000,
    },
    "world_leaders_analysis": {
        "name": "world_leaders_analysis",
        "description": "World Leaders: Comparative analysis tab with charts",
        "path": "/analysis/world-leaders",
        "wait_for_load": 4000,
        "actions": [
            {"type": "js", "code": """
                var tabs = document.querySelectorAll('.wl-tab[data-panel]');
                for (var t of tabs) {
                    if (t.dataset.panel === 'analysis-panel') { t.click(); break; }
                }
            """, "wait": 3000},
        ],
        "wait_after": 3000,
    },
    "world_leaders_map_complexity": {
        "name": "world_leaders_map_complexity",
        "description": "World Leaders Map: Globe choropleth by governance complexity",
        "path": "/analysis/world-leaders/map",
        "wait_for_load": 5000,
        "actions": [],
        "wait_after": 3000,
    },
    "world_leaders_map_security": {
        "name": "world_leaders_map_security",
        "description": "World Leaders Map: Globe choropleth by security ratio",
        "path": "/analysis/world-leaders/map",
        "wait_for_load": 5000,
        "actions": [
            {"type": "js", "code": """
                var sel = document.getElementById('metricSelect');
                if (sel) { sel.value = 'security_ratio'; sel.dispatchEvent(new Event('change')); }
            """, "wait": 2000},
        ],
        "wait_after": 3000,
    },
    "world_leaders_governance": {
        "name": "world_leaders_governance",
        "description": "World Leaders: Governance structure donut + regional breakdown",
        "path": "/analysis/world-leaders/governance",
        "wait_for_load": 4000,
        "actions": [],
        "wait_after": 3000,
    },
    "world_leaders_concentration": {
        "name": "world_leaders_concentration",
        "description": "World Leaders: Power concentration analysis",
        "path": "/analysis/world-leaders/concentration",
        "wait_for_load": 4000,
        "actions": [],
        "wait_after": 3000,
    },
    "world_leaders_security": {
        "name": "world_leaders_security",
        "description": "World Leaders: Security apparatus analysis",
        "path": "/analysis/world-leaders/security",
        "wait_for_load": 4000,
        "actions": [],
        "wait_after": 3000,
    },

    # ─── Demographics ────────────────────────────────────────────────
    "demographics_us_china": {
        "name": "demographics_us_china",
        "description": "Demographics: US vs China population pyramids + timeline",
        "path": "/analysis/demographics",
        "wait_for_load": 4000,
        "actions": [
            {"type": "js", "code": """
                var a = document.getElementById('country-a');
                if (a) { a.value = 'US'; a.dispatchEvent(new Event('change')); }
            """, "wait": 2000},
            {"type": "js", "code": """
                var b = document.getElementById('country-b');
                if (b) { b.value = 'CH'; b.dispatchEvent(new Event('change')); }
            """, "wait": 2000},
        ],
        "wait_after": 3000,
    },

    # ─── Political ───────────────────────────────────────────────────
    "political": {
        "name": "political",
        "description": "Political Change Over Time: regime shifts and political indicators",
        "path": "/analysis/political",
        "wait_for_load": 5000,
        "actions": [],
        "wait_after": 3000,
    },

    # ─── Development ─────────────────────────────────────────────────
    "development_overview": {
        "name": "development_overview",
        "description": "Development & Inequality: overview tab with availability heatmap",
        "path": "/analysis/development",
        "wait_for_load": 5000,
        "actions": [],
        "wait_after": 3000,
    },
    "development_health": {
        "name": "development_health",
        "description": "Development: Health tab with charts",
        "path": "/analysis/development",
        "wait_for_load": 5000,
        "actions": [
            {"type": "js", "code": """
                var tabs = document.querySelectorAll('.dev-tab[data-tab]');
                for (var t of tabs) {
                    if (t.dataset.tab === 'health') { t.click(); break; }
                }
            """, "wait": 3000},
        ],
        "wait_after": 3000,
    },

    # ─── Resources ───────────────────────────────────────────────────
    "resources_map": {
        "name": "resources_map",
        "description": "Natural Resources: World map with resource categories",
        "path": "/analysis/resources",
        "wait_for_load": 5000,
        "actions": [],
        "wait_after": 3000,
    },
    "resources_curse": {
        "name": "resources_curse",
        "description": "Natural Resources: Resource curse scatter plot",
        "path": "/analysis/resources",
        "wait_for_load": 5000,
        "actions": [
            {"type": "js", "code": "switchTab('curse')", "wait": 3000},
        ],
        "wait_after": 3000,
    },

    # ─── Scatter Plot ────────────────────────────────────────────────
    "scatter_gdp_lifeexp": {
        "name": "scatter_gdp_lifeexp",
        "description": "Scatter: GDP per capita vs Life Expectancy, 2025",
        "path": "/analysis/scatter",
        "wait_for_load": 4000,
        "actions": [
            {"type": "js", "code": "loadScatter()", "wait": 4000},
        ],
        "wait_after": 3000,
    },

    # ─── CSI (CIA Studies in Intelligence) ───────────────────────────
    "csi_search": {
        "name": "csi_search",
        "description": "CSI: Studies in Intelligence search interface",
        "path": "/analysis/csi",
        "wait_for_load": 4000,
        "actions": [],
        "wait_after": 2000,
    },
    "csi_dashboard": {
        "name": "csi_dashboard",
        "description": "CSI: Dashboard with publication stats and trends",
        "path": "/analysis/csi/dashboard",
        "wait_for_load": 5000,
        "actions": [],
        "wait_after": 3000,
    },

    # ─── Explorer & Structured Data ──────────────────────────────────
    "explorer": {
        "name": "explorer",
        "description": "Advanced Analytics Explorer with multi-panel analysis",
        "path": "/analysis/explorer",
        "wait_for_load": 5000,
        "actions": [],
        "wait_after": 3000,
    },
    "structured_data": {
        "name": "structured_data",
        "description": "Structured Field Data: parsed sub-fields with charts",
        "path": "/analysis/structured-data",
        "wait_for_load": 5000,
        "actions": [],
        "wait_after": 3000,
    },
    "coverage": {
        "name": "coverage",
        "description": "Intelligence Gap Analysis: entity coverage heatmap",
        "path": "/analysis/coverage",
        "wait_for_load": 5000,
        "actions": [],
        "wait_after": 3000,
    },

    # ─── Maps ────────────────────────────────────────────────────────
    "maps_gallery": {
        "name": "maps_gallery",
        "description": "CIA Reference Maps: gallery with carousel browser",
        "path": "/maps",
        "wait_for_load": 4000,
        "actions": [],
        "wait_after": 2000,
    },
    "maps_country_china": {
        "name": "maps_country_china",
        "description": "CIA Maps: China admin, physiography, and transport maps",
        "path": "/maps/CN",
        "wait_for_load": 4000,
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
