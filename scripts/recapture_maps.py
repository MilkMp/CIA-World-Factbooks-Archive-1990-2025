"""Re-capture map screenshots and GIF demos with GPU rendering (headed mode)."""
import asyncio
import io
import os
import shutil
from PIL import Image
from playwright.async_api import async_playwright

BASE = "https://worldfactbookarchive.org"
OUT = "C:/Users/milan/CIA_Factbook_Archive/docs/screenshots"
WEBAPP_IMG = "C:/Users/milan/cia-factbook-webapp/webapp/static/img/screenshots"

MAP_PAGES = [
    ("regional_dashboard", "/analysis/regional", 6000),
    ("region_eucom", "/analysis/region/EUCOM", 6000),
    ("timeline_map", "/analysis/timeline", 6000),
    ("map_compare", "/analysis/map-compare", 6000),
    ("communications", "/analysis/communications", 6000),
]


def frames_to_gif(frame_bytes_list, output_path, fps=5):
    images = []
    for fb in frame_bytes_list:
        img = Image.open(io.BytesIO(fb))
        w, h = img.size
        new_w = 1280
        new_h = int(h * new_w / w)
        img = img.resize((new_w, new_h), Image.LANCZOS)
        img = img.convert("RGB").quantize(colors=128, method=Image.Quantize.MEDIANCUT)
        images.append(img)
    if images:
        duration = int(1000 / fps)
        images[0].save(
            output_path, save_all=True, append_images=images[1:],
            duration=duration, loop=0, optimize=True,
        )


def save_gif(frames, name):
    gif_path = f"{OUT}/{name}.gif"
    frames_to_gif(frames, gif_path, fps=5)
    print(f"    -> {name}.gif ({len(frames)} frames)")
    webapp_path = f"{WEBAPP_IMG}/{name}.gif"
    if os.path.exists(os.path.dirname(webapp_path)):
        shutil.copy2(gif_path, webapp_path)
        print(f"    -> copied to webapp")


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            args=["--use-gl=angle", "--use-angle=d3d11"],
        )
        page = await browser.new_page(viewport={"width": 1920, "height": 1080})

        # --- Static screenshots ---
        print("=== MAP SCREENSHOTS (headed + GPU) ===\n")
        for name, path, wait in MAP_PAGES:
            url = f"{BASE}{path}"
            print(f"  {name} ...")
            await page.goto(url, wait_until="networkidle", timeout=30000)
            await page.wait_for_timeout(wait)
            await page.screenshot(path=f"{OUT}/{name}.png", full_page=False)
            print(f"    -> {name}.png")

        # --- GIF demos ---
        print("\n=== MAP GIF DEMOS ===\n")

        # Regional dashboard
        print("  regional_dashboard_demo ...")
        await page.goto(f"{BASE}/analysis/regional", wait_until="networkidle", timeout=30000)
        await page.wait_for_timeout(5000)
        frames = []
        for _ in range(15):
            frames.append(await page.screenshot())
            await page.wait_for_timeout(300)
        chip = page.locator("[data-region], .region-chip, .region-btn").first
        if await chip.count() > 0:
            await chip.click()
            await page.wait_for_timeout(3000)
            for _ in range(10):
                frames.append(await page.screenshot())
                await page.wait_for_timeout(300)
        else:
            for _ in range(10):
                await page.mouse.wheel(0, 120)
                await page.wait_for_timeout(400)
                frames.append(await page.screenshot())
        save_gif(frames, "regional_dashboard_demo")

        # Timeline map
        print("  timeline_map_demo ...")
        await page.goto(f"{BASE}/analysis/timeline", wait_until="networkidle", timeout=30000)
        await page.wait_for_timeout(5000)
        frames = []
        for _ in range(5):
            frames.append(await page.screenshot())
            await page.wait_for_timeout(200)
        play = page.locator("#play-btn, .play-btn, button:has-text('Play'), [aria-label='Play']").first
        if await play.count() > 0:
            await play.click()
            await page.wait_for_timeout(500)
            for _ in range(25):
                frames.append(await page.screenshot())
                await page.wait_for_timeout(400)
        save_gif(frames, "timeline_map_demo")

        # Map compare
        print("  map_compare_demo ...")
        await page.goto(f"{BASE}/analysis/map-compare", wait_until="networkidle", timeout=30000)
        await page.wait_for_timeout(6000)
        frames = []
        for _ in range(5):
            frames.append(await page.screenshot())
            await page.wait_for_timeout(200)
        buttons = page.locator(".indicator-pill")
        count = await buttons.count()
        for i in range(min(count, 4)):
            await buttons.nth(i).click()
            await page.wait_for_timeout(3000)
            for _ in range(6):
                frames.append(await page.screenshot())
                await page.wait_for_timeout(200)
        save_gif(frames, "map_compare_demo")

        # Trade networks
        print("  trade_networks_demo ...")
        await page.goto(f"{BASE}/analysis/networks/trade", wait_until="networkidle", timeout=30000)
        await page.wait_for_timeout(5000)
        frames = []
        for _ in range(5):
            frames.append(await page.screenshot())
            await page.wait_for_timeout(200)
        selector = page.locator("select, .commodity-select").first
        if await selector.count() > 0:
            options = await selector.locator("option").all()
            for opt in options[1:4]:
                val = await opt.get_attribute("value")
                if val:
                    await selector.select_option(val)
                    await page.wait_for_timeout(2000)
                    for _ in range(5):
                        frames.append(await page.screenshot())
                        await page.wait_for_timeout(200)
        else:
            for _ in range(20):
                frames.append(await page.screenshot())
                await page.wait_for_timeout(300)
        save_gif(frames, "trade_networks_demo")

        # Org networks
        print("  org_networks_demo ...")
        await page.goto(f"{BASE}/analysis/networks/organizations", wait_until="networkidle", timeout=30000)
        await page.wait_for_timeout(5000)
        frames = []
        for _ in range(5):
            frames.append(await page.screenshot())
            await page.wait_for_timeout(200)
        selector = page.locator("select").first
        if await selector.count() > 0:
            options = await selector.locator("option").all()
            for opt in options[1:4]:
                val = await opt.get_attribute("value")
                if val:
                    await selector.select_option(val)
                    await page.wait_for_timeout(2000)
                    for _ in range(5):
                        frames.append(await page.screenshot())
                        await page.wait_for_timeout(200)
        else:
            for _ in range(20):
                frames.append(await page.screenshot())
                await page.wait_for_timeout(300)
        save_gif(frames, "org_networks_demo")

        await browser.close()
    print("\nDone!")


if __name__ == "__main__":
    asyncio.run(main())
