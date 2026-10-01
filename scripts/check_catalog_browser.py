"""Production-mode browser checks; writes only timings and cache metadata."""
import argparse
import asyncio
import json
import statistics
import time
from pathlib import Path
from playwright.async_api import async_playwright, expect


async def main(base, output):
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1365, "height": 768})
        page = await context.new_page()
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        downloads = []
        page.on("request", lambda request: downloads.append(request.url) if "/api/v1/catalog/" in request.url else None)
        # Hold dataset requests to prove the HTML bootstrap works before the download.
        release = asyncio.Event()
        async def hold(route):
            await release.wait()
            await route.continue_()
        await page.route("**/api/v1/catalog/*", hold)
        response = await page.goto(f"{base}/en")
        assert response.status == 200
        await page.wait_for_selector("article.card")
        assert await page.locator("article.card").count() == 20
        assert await page.locator("input.search").is_disabled()
        bootstrap_total = int(await page.locator(".results-count strong").inner_text())
        assert bootstrap_total >= 20
        release.set()
        await page.wait_for_selector('[data-catalog-ready="true"]')
        await page.unroute("**/api/v1/catalog/*", hold)
        assert not await page.locator("input.search").is_disabled()
        assert len(downloads) == 1
        # Search, display and pagination remain in the root provider across languages.
        await page.locator("input.search").fill("project")
        await page.locator(".controls select").select_option("50")
        await page.locator(".pagination button").filter(has_text="Next").click()
        await page.wait_for_timeout(300)
        first_reference = await page.locator("article.card").first.inner_text()
        await page.locator(".lang a[lang=de]").click()
        await page.wait_for_url("**/de")
        await page.wait_for_selector('[data-catalog-ready="true"]')
        assert await page.locator("input.search").input_value() == "project"
        assert await page.locator(".controls select").input_value() == "50"
        assert await page.locator('.pagination button[aria-current="page"]').inner_text() == "2"
        assert len(downloads) == 1
        # All selected types may be unchecked and must produce no results.
        types = page.locator(".filters fieldset").first.locator('input[type="checkbox"]')
        for checkbox in await types.all():
            await checkbox.uncheck()
        assert await page.locator("article.card").count() == 0
        for checkbox in await types.all():
            await checkbox.check()
        await page.locator(".controls select").select_option("20")
        first_card = page.locator("article.card").first
        details = first_card.locator("details")
        if await details.count() and not await details.first.get_attribute("open"):
            await details.first.locator("summary").click()
        await first_card.locator("button[aria-pressed]").click()
        await page.locator(".saved-pill").click()
        await page.wait_for_url("**saved=1")
        await page.wait_for_selector('[data-catalog-ready="true"]')
        await expect(page.locator("article.card")).to_have_count(1)
        await page.locator(".lang a[lang=en]").click()
        await page.wait_for_url("**/en?saved=1")
        await expect(page.locator("article.card")).to_have_count(1)
        # A separate browser context shares cached HTML, never bookmark state.
        other = await browser.new_context()
        other_page = await other.new_page()
        await other_page.goto(f"{base}/en?saved=1")
        await other_page.wait_for_selector('[data-catalog-ready="true"]')
        await expect(other_page.locator("article.card")).to_have_count(0)
        await other.close()
        # Detail uses one response and translates controls while keeping the original title.
        first_card = page.locator("article.card").first
        title = await first_card.locator("h2, summary").first.inner_text()
        details = first_card.locator("details")
        if await details.count() and not await details.first.get_attribute("open"):
            await details.first.locator("summary").click()
        await page.locator("article.card a.source-primary").first.click()
        await page.wait_for_url("**/projects/**")
        assert await page.locator("h1").inner_text() == title
        await page.locator(".lang a[lang=de]").hover()
        await page.wait_for_timeout(300)
        await page.locator(".lang a[lang=de]").click()
        await page.wait_for_url("**/de/projects/**")
        assert await page.locator("h1").inner_text() == title
        # Failure leaves bootstrap cards visible; explicit retry restores filtering.
        failure = await browser.new_context()
        failure_page = await failure.new_page()
        await failure_page.route("**/api/v1/catalog/*", lambda route: route.fulfill(status=503, body="unavailable"))
        await failure_page.goto(f"{base}/en")
        await failure_page.get_by_role("button", name="Retry", exact=True).wait_for()
        assert await failure_page.locator("article.card").count() == 20
        await failure_page.unroute("**/api/v1/catalog/*")
        await failure_page.get_by_role("button", name="Retry", exact=True).click()
        await failure_page.wait_for_selector('[data-catalog-ready="true"]')
        await failure.close()
        # Repeated warm language switches and filtering measured from input to next paint.
        await page.goto(f"{base}/en")
        await page.wait_for_selector('[data-catalog-ready="true"]')
        await page.locator("input.search").fill("")
        switches = []
        for index in range(10):
            lang = "de" if index % 2 == 0 else "en"
            await page.locator(f'.lang a[lang="{lang}"]').hover()
            await page.wait_for_timeout(100)
            started = time.perf_counter()
            await page.locator(f'.lang a[lang="{lang}"]').click()
            await page.wait_for_url(f"**/{lang}")
            await page.wait_for_selector('[data-catalog-ready="true"]')
            switches.append((time.perf_counter() - started) * 1000)
        interactions = []
        for size in (20, 100, "all"):
            await page.locator(".controls select").select_option(str(size))
            started = time.perf_counter()
            await page.locator("input.search").fill("project 1")
            await page.wait_for_timeout(30)
            await page.evaluate("() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))")
            interactions.append({"display": size, "milliseconds": round((time.perf_counter() - started) * 1000, 2)})
            await page.locator("input.search").fill("")
        assert not errors, errors
        report = {"total": bootstrap_total, "browser_checks": "passed", "language_switch_p95_ms": sorted(switches)[-1], "interactions": interactions}
        Path(output).write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report))
        await browser.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://127.0.0.1:8187")
    parser.add_argument("--output", default="/tmp/catalog-browser-results.json")
    args = parser.parse_args()
    asyncio.run(main(args.base, args.output))
