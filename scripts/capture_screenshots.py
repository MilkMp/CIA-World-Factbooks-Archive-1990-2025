"""Capture screenshots + animated GIF demos of the CIA Factbook webapp."""
import asyncio
import io
import os
import shutil
from PIL import Image
from playwright.async_api import async_playwright

BASE = "https://worldfactbookarchive.org"
OUT = "C:/Users/milan/CIA_Factbook_Archive/docs/screenshots"
WEBAPP_IMG = "C:/Users/milan/cia-factbook-webapp/webapp/static/img/screenshots"

# (name, path, extra_wait_ms, full_page)
PAGES = [
    # Core pages
    ("homepage",              "/",                                       None,  False),
    ("search_results",        "/search?q=nuclear",                       None,  False),
    ("search_boolean",        '/search?q="nuclear+weapons"+AND+treaty',  None,  False),
    ("about",                 "/about",                                  None,  False),

    # Archive section
    ("library",               "/archive/library",                        None,  False),
    ("browse_years",          "/archive",                                None,  False),
    ("country_profile",       "/archive/2025/US",                        None,  False),
    ("country_dictionary",    "/countries",                              None,  False),
    ("field_timeseries",      "/archive/field/US/Population",            3000,  False),
    ("country_export",        "/export",                                 None,  False),
    ("text_diff",             "/diff?a=US&ya=2000&b=US&yb=2025&section=Economy",  2000,  False),
    ("quiz",                  "/quiz",                                   None,  False),

    # Intelligence Analysis section
    ("analysis_overview",     "/analysis",                               None,  False),
    ("regional_dashboard",    "/analysis/regional",                      4000,  False),
    ("region_eucom",          "/analysis/region/EUCOM",                  4000,  False),
    ("rankings",              "/analysis/rankings",                      None,  False),
    ("global_trends",         "/analysis/trends",                        3000,  False),
    ("compare_countries",     "/analysis/compare?a=US&b=CN",             None,  False),
    ("timeline_map",          "/analysis/timeline",                      4000,  False),
    ("map_compare",           "/analysis/map-compare",                   4000,  False),
    ("communications",        "/analysis/communications",                4000,  False),
    ("trade_networks",        "/analysis/networks/trade",                3000,  False),
    ("org_networks",          "/analysis/networks/organizations",        3000,  False),
    ("change_detection",      "/analysis/changes",                       None,  False),
    ("dissolved_states",      "/analysis/dissolved",                     None,  False),
    ("field_explorer",        "/analysis/field-explorer",                None,  False),
    ("query_builder",         "/analysis/query-builder",                 None,  False),
    ("dossier",               "/analysis/dossier/US",                    None,  False),
    ("threats",               "/analysis/threats/EUCOM",                 None,  False),
]

# GIF demos: (name, path, wait_before_ms, record_actions, duration_frames, fps)
# Each record_actions is an async function(page) that performs interactions.
FRAME_INTERVAL = 200  # ms between frames


async def gif_regional_dashboard(page):
    """Pan the Mapbox globe and hover regions."""
    await page.wait_for_timeout(2000)
    frames = []
    # Capture initial view
    for _ in range(8):
        frames.append(await page.screenshot())
        await page.wait_for_timeout(FRAME_INTERVAL)
    # Click a region chip if available
    chip = page.locator('.region-chip, .region-btn, [data-region]').first
    if await chip.count() > 0:
        await chip.click()
        await page.wait_for_timeout(2000)
        for _ in range(10):
            frames.append(await page.screenshot())
            await page.wait_for_timeout(FRAME_INTERVAL)
    else:
        # Just scroll down slowly
        for _ in range(10):
            await page.mouse.wheel(0, 120)
            await page.wait_for_timeout(300)
            frames.append(await page.screenshot())
    return frames


async def gif_timeline_map(page):
    """Click the play button on the timeline map."""
    await page.wait_for_timeout(3000)
    frames = []
    # Capture initial state
    for _ in range(5):
        frames.append(await page.screenshot())
        await page.wait_for_timeout(FRAME_INTERVAL)
    # Click play button
    play = page.locator('#play-btn, .play-btn, button:has-text("Play"), [aria-label="Play"]').first
    if await play.count() > 0:
        await play.click()
        await page.wait_for_timeout(500)
        for _ in range(25):
            frames.append(await page.screenshot())
            await page.wait_for_timeout(400)
    return frames


async def gif_map_compare(page):
    """Switch indicators on the map compare page."""
    await page.wait_for_timeout(4000)
    frames = []
    for _ in range(5):
        frames.append(await page.screenshot())
        await page.wait_for_timeout(FRAME_INTERVAL)
    # Click through indicator pills
    buttons = page.locator('.indicator-pill')
    count = await buttons.count()
    for i in range(min(count, 4)):
        await buttons.nth(i).click()
        await page.wait_for_timeout(2500)
        for _ in range(6):
            frames.append(await page.screenshot())
            await page.wait_for_timeout(FRAME_INTERVAL)
    return frames


async def gif_trade_networks(page):
    """Interact with the trade network graph."""
    await page.wait_for_timeout(3000)
    frames = []
    for _ in range(5):
        frames.append(await page.screenshot())
        await page.wait_for_timeout(FRAME_INTERVAL)
    # Try clicking a country node or changing commodity
    selector = page.locator('select, .commodity-select').first
    if await selector.count() > 0:
        options = await selector.locator('option').all()
        for opt in options[1:4]:
            val = await opt.get_attribute('value')
            if val:
                await selector.select_option(val)
                await page.wait_for_timeout(2000)
                for _ in range(5):
                    frames.append(await page.screenshot())
                    await page.wait_for_timeout(FRAME_INTERVAL)
    else:
        # Just capture the animation
        for _ in range(20):
            frames.append(await page.screenshot())
            await page.wait_for_timeout(300)
    return frames


async def gif_org_networks(page):
    """Interact with the organization network graph."""
    await page.wait_for_timeout(3000)
    frames = []
    for _ in range(5):
        frames.append(await page.screenshot())
        await page.wait_for_timeout(FRAME_INTERVAL)
    # Try clicking org selector
    selector = page.locator('select').first
    if await selector.count() > 0:
        options = await selector.locator('option').all()
        for opt in options[1:4]:
            val = await opt.get_attribute('value')
            if val:
                await selector.select_option(val)
                await page.wait_for_timeout(2000)
                for _ in range(5):
                    frames.append(await page.screenshot())
                    await page.wait_for_timeout(FRAME_INTERVAL)
    else:
        for _ in range(20):
            frames.append(await page.screenshot())
            await page.wait_for_timeout(300)
    return frames


GIF_DEMOS = [
    ("regional_dashboard_demo", "/analysis/regional",              gif_regional_dashboard),
    ("timeline_map_demo",       "/analysis/timeline",              gif_timeline_map),
    ("map_compare_demo",        "/analysis/map-compare",           gif_map_compare),
    ("trade_networks_demo",     "/analysis/networks/trade",        gif_trade_networks),
    ("org_networks_demo",       "/analysis/networks/organizations", gif_org_networks),
]


def frames_to_gif(frame_bytes_list, output_path, fps=5):
    """Convert a list of PNG screenshot bytes into an animated GIF using Pillow."""
    images = []
    for fb in frame_bytes_list:
        img = Image.open(io.BytesIO(fb))
        # Resize to 1280px wide for smaller GIFs
        w, h = img.size
        new_w = 1280
        new_h = int(h * new_w / w)
        img = img.resize((new_w, new_h), Image.LANCZOS)
        # Convert to palette mode for smaller file size
        img = img.convert("RGB").quantize(colors=128, method=Image.Quantize.MEDIANCUT)
        images.append(img)
    if images:
        duration = int(1000 / fps)
        images[0].save(
            output_path,
            save_all=True,
            append_images=images[1:],
            duration=duration,
            loop=0,
            optimize=True,
        )


async def capture_screenshots(page):
    """Capture all static screenshots."""
    print(f"\n{'='*60}")
    print(f"  STATIC SCREENSHOTS ({len(PAGES)} pages)")
    print(f"{'='*60}\n")

    for name, path, extra_wait, full_page in PAGES:
        url = f"{BASE}{path}"
        print(f"  Capturing {name} ... {url}")
        try:
            await page.goto(url, wait_until="networkidle", timeout=30000)
            if extra_wait:
                await page.wait_for_timeout(extra_wait)
            await page.screenshot(path=f"{OUT}/{name}.png", full_page=full_page)
            print(f"    -> {name}.png saved")
        except Exception as e:
            print(f"    !! FAILED: {e}")

    print(f"\n  {len(PAGES)} screenshots saved to {OUT}")


async def capture_gifs(page):
    """Capture animated GIF demos."""
    print(f"\n{'='*60}")
    print(f"  ANIMATED GIF DEMOS ({len(GIF_DEMOS)} demos)")
    print(f"{'='*60}\n")

    for name, path, action_fn in GIF_DEMOS:
        url = f"{BASE}{path}"
        print(f"  Recording {name} ... {url}")
        try:
            await page.goto(url, wait_until="networkidle", timeout=30000)
            frames = await action_fn(page)
            if frames:
                gif_path = f"{OUT}/{name}.gif"
                frames_to_gif(frames, gif_path, fps=5)
                print(f"    -> {name}.gif saved ({len(frames)} frames)")
                # Copy to webapp static dir too
                webapp_path = f"{WEBAPP_IMG}/{name}.gif"
                if os.path.exists(os.path.dirname(webapp_path)):
                    shutil.copy2(gif_path, webapp_path)
                    print(f"    -> copied to webapp static/img/screenshots/")
            else:
                print(f"    !! No frames captured")
        except Exception as e:
            print(f"    !! FAILED: {e}")

    print(f"\n  GIF demos saved to {OUT}")


async def main():
    os.makedirs(OUT, exist_ok=True)

    async with async_playwright() as p:
        # Use headed mode with GPU for proper Mapbox WebGL rendering (globe fog, atmosphere)
        browser = await p.chromium.launch(
            headless=False,
            args=["--use-gl=angle", "--use-angle=d3d11"],
        )
        page = await browser.new_page(viewport={"width": 1920, "height": 1080})

        await capture_screenshots(page)
        await capture_gifs(page)

        await browser.close()

    print(f"\n{'='*60}")
    print(f"  ALL DONE!")
    print(f"{'='*60}")


if __name__ == "__main__":
    asyncio.run(main())
