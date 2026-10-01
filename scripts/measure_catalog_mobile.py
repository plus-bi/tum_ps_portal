"""Five cold mobile navigations using fixed CDP network and CPU throttling."""
import argparse
import asyncio
import json
import statistics
from pathlib import Path
from playwright.async_api import async_playwright


async def main(base, output):
    samples = []
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch()
        for _ in range(5):
            context = await browser.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=3, is_mobile=True, has_touch=True)
            page = await context.new_page()
            session = await context.new_cdp_session(page)
            await session.send("Network.enable")
            await session.send("Network.emulateNetworkConditions", {"offline": False, "latency": 150,
                                "downloadThroughput": 200000, "uploadThroughput": 93750})
            await session.send("Emulation.setCPUThrottlingRate", {"rate": 4})
            await page.add_init_script("window.catalogLCP = 0; new PerformanceObserver(list => {window.catalogLCP = list.getEntries().at(-1).startTime;}).observe({type:'largest-contentful-paint', buffered:true});")
            await page.goto(base + "/en", wait_until="networkidle")
            await page.wait_for_timeout(1000)
            samples.append(await page.evaluate("window.catalogLCP"))
            await context.close()
        await browser.close()
    result = {"lcp_ms": samples, "median_lcp_ms": statistics.median(samples), "network_latency_ms": 150,
              "download_bytes_per_second": 200000, "cpu_slowdown": 4}
    Path(output).write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://127.0.0.1:8187")
    parser.add_argument("--output", default="/tmp/catalog-mobile-results.json")
    args = parser.parse_args()
    asyncio.run(main(args.base, args.output))
