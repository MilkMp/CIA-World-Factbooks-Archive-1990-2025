#!/usr/bin/env python3
"""Capture animated GIF demos for README and homepage using Playwright.

Each demo clicks into actual countries/nodes to show the detail trail --
not just panning, but the full interactive workflow.
"""
import asyncio
import os
import shutil
import numpy as np
from PIL import Image
import imageio
from playwright.async_api import async_playwright

BASE = "https://cia-factbook-archive.fly.dev"
DOCS_DIR = os.path.join(os.path.dirname(__file__), "docs", "screenshots")
WEB_DIR = os.path.join(os.path.dirname(__file__), "webapp", "static", "img", "screenshots")
TEMP_DIR = os.path.join(os.path.dirname(__file__), "data", "gif_frames")

FPS = 5


def frames_to_gif(frame_dir, output_path, fps=FPS, max_width=1280):
    """Convert a directory of PNG frames to an optimized GIF."""
    frames = sorted(f for f in os.listdir(frame_dir) if f.endswith(".png"))
    if not frames:
        print(f"    [!] No frames found in {frame_dir}")
        return

    images = []
    for f in frames:
        img = Image.open(os.path.join(frame_dir, f))
        if img.width > max_width:
            ratio = max_width / img.width
            img = img.resize((max_width, int(img.height * ratio)), Image.LANCZOS)
        img = img.convert("RGB")
        images.append(img)

    quantized = [np.array(img.quantize(colors=192, method=2).convert("RGB")) for img in images]
    imageio.mimsave(output_path, quantized, duration=1.0 / fps, loop=0)
    size_kb = os.path.getsize(output_path) // 1024
    print(f"    -> {output_path} ({size_kb}KB, {len(images)} frames, {fps}fps)")


async def clear_frames(name):
    d = os.path.join(TEMP_DIR, name)
    os.makedirs(d, exist_ok=True)
    for f in os.listdir(d):
        os.remove(os.path.join(d, f))
    return d


async def shot(page, frame_dir, idx):
    await page.screenshot(
        path=os.path.join(frame_dir, f"frame_{idx:04d}.png"),
        full_page=False,
    )
    return idx + 1


async def hold(page, frame_dir, idx, n=8, delay=200):
    """Capture n static frames (hold on current state)."""
    for _ in range(n):
        idx = await shot(page, frame_dir, idx)
        await page.wait_for_timeout(delay)
    return idx


async def click_country_on_map(page, map_var, lng, lat, container_sel):
    """Click a specific country on a Mapbox map using map.project()."""
    # Get the map container's bounding box for offset calculation
    pos = await page.evaluate(f"""
        (() => {{
            const m = {map_var};
            if (!m) return null;
            const pt = m.project([{lng}, {lat}]);
            const el = document.querySelector('{container_sel}');
            if (!el) return null;
            const r = el.getBoundingClientRect();
            return {{ x: r.left + pt.x, y: r.top + pt.y }};
        }})()
    """)
    if pos:
        await page.mouse.click(pos["x"], pos["y"])
        return True
    return False


async def click_graph_node(page, graph_container_sel, detail_sel, max_attempts=20):
    """Try clicking at various positions on a force-graph canvas until the
    detail sidebar opens (gains .open class). Returns True if a node was hit."""
    container = await page.query_selector(graph_container_sel)
    if not container:
        return False
    box = await container.bounding_box()
    if not box:
        return False

    # Check for .open class to confirm sidebar actually opened (not just exists in DOM)
    open_sel = detail_sel + ".open"

    # Try a wider grid of positions across the graph area
    cx, cy = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
    offsets = [
        (0, 0), (40, -30), (-40, 30), (80, 0), (-80, 0),
        (0, 60), (0, -60), (60, 40), (-60, -40), (120, -20),
        (-120, 20), (40, 80), (-40, -80), (100, 60), (-100, -60),
        (150, 0), (-150, 0), (0, 100), (80, -80), (-80, 80),
    ]

    for dx, dy in offsets[:max_attempts]:
        x, y = cx + dx, cy + dy
        await page.mouse.click(x, y)
        await page.wait_for_timeout(1000)
        # Check if sidebar gained .open class
        is_open = await page.evaluate(f'document.querySelector("{detail_sel}")?.classList.contains("open") ?? false')
        if is_open:
            return True

    return False


# ─── DEMO: Trade Networks ───────────────────────────────────────────

async def demo_trade_networks(page):
    """Trade Networks: click a node -> sidebar shows partners -> navigate."""
    name = "trade_networks_demo"
    print(f"[*] Recording {name}")
    frame_dir = await clear_frames(name)

    await page.goto(BASE + "/analysis/networks", wait_until="networkidle", timeout=30000)
    await page.wait_for_timeout(6000)

    idx = 0

    # 1. Initial graph state — let viewers absorb the layout
    idx = await hold(page, frame_dir, idx, n=20, delay=200)

    # 2. Click a node on the trade graph to open the detail sidebar
    print("    Searching for trade node...")
    hit = await click_graph_node(page, "#trade-graph", "#trade-detail")
    if hit:
        print("    -> Node found, sidebar open")
        await page.wait_for_timeout(1500)
        idx = await hold(page, frame_dir, idx, n=25, delay=200)

        # 3. Click a partner in the sidebar list to navigate to that node
        partner = page.locator('.nd-list-item').first
        if await partner.is_visible():
            await partner.click()
            await page.wait_for_timeout(2000)
            idx = await hold(page, frame_dir, idx, n=20, delay=200)

        # 4. Click another partner to show navigation trail
        partner2 = page.locator('.nd-list-item').nth(2)
        if await partner2.count() > 0 and await partner2.is_visible():
            await partner2.click()
            await page.wait_for_timeout(2000)
            idx = await hold(page, frame_dir, idx, n=20, delay=200)
    else:
        print("    -> No node hit, showing graph interaction")
        idx = await hold(page, frame_dir, idx, n=15, delay=200)

    # 5. Switch to Imports
    direction_select = page.locator('#trade-direction')
    if await direction_select.is_visible():
        await direction_select.select_option('imports')
        await page.wait_for_timeout(3000)
        idx = await hold(page, frame_dir, idx, n=20, delay=200)

    # 6. Hold final
    idx = await hold(page, frame_dir, idx, n=10, delay=200)

    return name


# ─── DEMO: Organization Networks ────────────────────────────────────

async def demo_org_networks(page):
    """Org Networks: switch tab -> click node -> sidebar with members -> click member
    -> navigate -> click another member (same flow as trade networks)."""
    name = "org_networks_demo"
    print(f"[*] Recording {name}")
    frame_dir = await clear_frames(name)

    await page.goto(BASE + "/analysis/networks", wait_until="networkidle", timeout=30000)
    await page.wait_for_timeout(5000)

    idx = 0

    # 1. Show trade tab briefly
    idx = await hold(page, frame_dir, idx, n=12, delay=200)

    # 2. Switch to Organization tab
    tab = page.locator('[data-tab="orgs"]')
    if await tab.is_visible():
        await tab.click()
        await page.wait_for_timeout(5000)
    idx = await hold(page, frame_dir, idx, n=15, delay=200)

    # 3. Click a node in the org graph to open sidebar
    print("    Searching for org node...")
    hit = await click_graph_node(page, "#org-graph", "#org-detail")
    if hit:
        print("    -> Org node found, sidebar open")
        # Wait longer for member list to populate
        await page.wait_for_timeout(2000)
        # Wait for list items to appear (the sidebar JS populates them async)
        for _ in range(10):
            item_count = await page.evaluate('document.querySelectorAll("#od-list .nd-list-item").length')
            if item_count > 0:
                break
            await page.wait_for_timeout(500)
        idx = await hold(page, frame_dir, idx, n=25, delay=200)

        # 4. Click a member in the sidebar to navigate to that node
        member = page.locator('#od-list .nd-list-item').first
        if await member.count() > 0 and await member.is_visible():
            await member.click()
            await page.wait_for_timeout(2000)
            # Wait for new list items
            for _ in range(10):
                item_count = await page.evaluate('document.querySelectorAll("#od-list .nd-list-item").length')
                if item_count > 0:
                    break
                await page.wait_for_timeout(500)
            idx = await hold(page, frame_dir, idx, n=20, delay=200)

        # 5. Click another member to keep navigating the trail
        member2 = page.locator('#od-list .nd-list-item').nth(2)
        if await member2.count() > 0 and await member2.is_visible():
            await member2.click()
            await page.wait_for_timeout(2000)
            for _ in range(10):
                item_count = await page.evaluate('document.querySelectorAll("#od-list .nd-list-item").length')
                if item_count > 0:
                    break
                await page.wait_for_timeout(500)
            idx = await hold(page, frame_dir, idx, n=20, delay=200)

        # 6. Click yet another to show the drill-down trail
        member3 = page.locator('#od-list .nd-list-item').nth(1)
        if await member3.count() > 0 and await member3.is_visible():
            await member3.click()
            await page.wait_for_timeout(2000)
            idx = await hold(page, frame_dir, idx, n=15, delay=200)
    else:
        print("    -> No org node hit")
        idx = await hold(page, frame_dir, idx, n=15, delay=200)

    # 7. Toggle a category filter to show the graph reshaping
    cat_btn = page.locator('.region-btn[data-cat]').nth(1)
    if await cat_btn.is_visible():
        await cat_btn.click()
        await page.wait_for_timeout(3000)
        idx = await hold(page, frame_dir, idx, n=15, delay=200)

    idx = await hold(page, frame_dir, idx, n=10, delay=200)
    return name


# ─── DEMO: Timeline Map ─────────────────────────────────────────────

async def demo_timeline_map(page):
    """Timeline: play animation -> click France -> click China -> chart builds."""
    name = "timeline_map_demo"
    print(f"[*] Recording {name}")
    frame_dir = await clear_frames(name)

    await page.goto(BASE + "/analysis/timeline", wait_until="networkidle", timeout=30000)
    await page.wait_for_timeout(5000)

    idx = 0

    # 1. Initial state — let viewers see the starting map
    idx = await hold(page, frame_dir, idx, n=15, delay=200)

    # 2. Click PLAY and let it run for a bit
    play_btn = page.locator('#play-btn')
    if await play_btn.is_visible():
        await play_btn.click()
        await page.wait_for_timeout(300)
        # Capture ~5 seconds of animation
        for _ in range(40):
            idx = await shot(page, frame_dir, idx)
            await page.wait_for_timeout(130)
        # Pause
        await play_btn.click()
        await page.wait_for_timeout(500)

    idx = await hold(page, frame_dir, idx, n=15, delay=200)

    # 3. Click on France (2.3, 48.8) to add it to time series
    print("    Clicking France on timeline map...")
    clicked = await click_country_on_map(page, "map", 2.3, 48.8, "#timeline-map")
    if clicked:
        await page.wait_for_timeout(2500)
        idx = await hold(page, frame_dir, idx, n=20, delay=200)

    # 4. Click on China (104, 35) to add it to time series
    print("    Clicking China on timeline map...")
    clicked = await click_country_on_map(page, "map", 104.0, 35.0, "#timeline-map")
    if clicked:
        await page.wait_for_timeout(2500)
        idx = await hold(page, frame_dir, idx, n=20, delay=200)

    # 5. Click on Brazil (-47.9, -15.8) to add it
    print("    Clicking Brazil on timeline map...")
    clicked = await click_country_on_map(page, "map", -47.9, -15.8, "#timeline-map")
    if clicked:
        await page.wait_for_timeout(2500)
        idx = await hold(page, frame_dir, idx, n=20, delay=200)

    # 6. Change indicator to GDP per capita
    indicator = page.locator('#tl-indicator')
    if await indicator.is_visible():
        await indicator.select_option(index=2)
        await page.wait_for_timeout(3000)
        idx = await hold(page, frame_dir, idx, n=20, delay=200)

    idx = await hold(page, frame_dir, idx, n=10, delay=200)
    return name


# ─── DEMO: Regional Dashboard ───────────────────────────────────────

async def demo_regional_dashboard(page):
    """Dashboard: click EUCOM -> click France -> country card -> INDOPACOM -> click China.
    Slower pacing so viewers can read each state."""
    name = "regional_dashboard_demo"
    print(f"[*] Recording {name}")
    frame_dir = await clear_frames(name)

    await page.goto(BASE + "/analysis/regional", wait_until="networkidle", timeout=30000)
    await page.wait_for_timeout(5000)

    idx = 0

    # 1. Initial globe -- hold longer so viewers see the starting state
    idx = await hold(page, frame_dir, idx, n=15, delay=200)

    # 2. Click EUCOM region card -> map flies to Europe
    eucom = page.locator('.region-card[data-region="EUCOM"]')
    if await eucom.is_visible():
        await eucom.click()
        await page.wait_for_timeout(3500)
        # Hold on Europe view so they can see the region
        idx = await hold(page, frame_dir, idx, n=20, delay=200)

    # 3. Click on France (2.3, 48.8) -> country card opens
    print("    Clicking France on dashboard...")
    clicked = await click_country_on_map(page, "map", 2.3, 48.8, "#world-map")
    if clicked:
        await page.wait_for_timeout(2500)
        # Hold on country card so viewers can read the stats
        idx = await hold(page, frame_dir, idx, n=25, delay=200)

    # 4. Close the country card
    close = page.locator('.cc-close')
    if await close.is_visible():
        await close.click()
        await page.wait_for_timeout(800)

    # 5. Click on Germany (10.4, 51.1) -> another country card
    print("    Clicking Germany on dashboard...")
    clicked = await click_country_on_map(page, "map", 10.4, 51.1, "#world-map")
    if clicked:
        await page.wait_for_timeout(2500)
        idx = await hold(page, frame_dir, idx, n=25, delay=200)

    # 6. Close and switch to INDOPACOM
    close = page.locator('.cc-close')
    if await close.is_visible():
        await close.click()
        await page.wait_for_timeout(800)

    indopacom = page.locator('.region-card[data-region="INDOPACOM"]')
    if await indopacom.is_visible():
        await indopacom.click()
        await page.wait_for_timeout(3500)
        # Hold on Asia-Pacific view
        idx = await hold(page, frame_dir, idx, n=20, delay=200)

    # 7. Click China (104, 35)
    print("    Clicking China on dashboard...")
    clicked = await click_country_on_map(page, "map", 104.0, 35.0, "#world-map")
    if clicked:
        await page.wait_for_timeout(2500)
        idx = await hold(page, frame_dir, idx, n=25, delay=200)

    idx = await hold(page, frame_dir, idx, n=10, delay=200)
    return name


# ─── DEMO: Map Compare ──────────────────────────────────────────────

async def demo_map_compare(page):
    """Map Compare: switch indicators, change years, click countries on both maps."""
    name = "map_compare_demo"
    print(f"[*] Recording {name}")
    frame_dir = await clear_frames(name)

    await page.goto(BASE + "/analysis/map-compare", wait_until="networkidle", timeout=30000)
    await page.wait_for_timeout(5000)

    idx = 0

    # 1. Initial side-by-side — let viewers see both maps
    idx = await hold(page, frame_dir, idx, n=15, delay=200)

    # 2. Click GDP indicator pill
    pills = page.locator('.indicator-pill')
    count = await pills.count()
    if count >= 2:
        await pills.nth(1).click()
        await page.wait_for_timeout(3000)
        idx = await hold(page, frame_dir, idx, n=20, delay=200)

    # 3. Click on a country on the left map (US) to show popup
    print("    Clicking US on map A...")
    clicked = await click_country_on_map(page, "mapA", -98.0, 39.0, "#map-a")
    if clicked:
        await page.wait_for_timeout(2500)
        idx = await hold(page, frame_dir, idx, n=20, delay=200)

    # 4. Change Year A to 2000
    year_a = page.locator('#year-a')
    if await year_a.is_visible():
        await year_a.select_option('2000')
        await page.wait_for_timeout(3000)
        idx = await hold(page, frame_dir, idx, n=20, delay=200)

    # 5. Click on China on the right map to show comparison popup
    print("    Clicking China on map B...")
    clicked = await click_country_on_map(page, "mapB", 104.0, 35.0, "#map-b")
    if clicked:
        await page.wait_for_timeout(2500)
        idx = await hold(page, frame_dir, idx, n=20, delay=200)

    # 6. Switch to Military % pill
    if count >= 4:
        await pills.nth(3).click()
        await page.wait_for_timeout(3000)
        idx = await hold(page, frame_dir, idx, n=20, delay=200)

    idx = await hold(page, frame_dir, idx, n=10, delay=200)
    return name


# ─────────────────────────────────────────────────────────────────────

async def main():
    os.makedirs(TEMP_DIR, exist_ok=True)
    os.makedirs(DOCS_DIR, exist_ok=True)
    os.makedirs(WEB_DIR, exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            device_scale_factor=2,
            color_scheme="dark",
        )
        page = await context.new_page()

        demos = [
            demo_trade_networks,
            demo_org_networks,
            demo_timeline_map,
            demo_regional_dashboard,
            demo_map_compare,
        ]

        for demo_fn in demos:
            try:
                name = await demo_fn(page)
                if name:
                    frame_dir = os.path.join(TEMP_DIR, name)
                    gif_path = os.path.join(DOCS_DIR, f"{name}.gif")
                    frames_to_gif(frame_dir, gif_path)
                    web_gif = os.path.join(WEB_DIR, f"{name}.gif")
                    shutil.copy2(gif_path, web_gif)
            except Exception as e:
                print(f"    [!] FAILED: {e}")

        await browser.close()

    print("\n[+] Done! GIFs saved to docs/screenshots/ and webapp/static/img/screenshots/")


if __name__ == "__main__":
    asyncio.run(main())
