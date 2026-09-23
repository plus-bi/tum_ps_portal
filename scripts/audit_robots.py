"""Fetch and evaluate robots.txt for every configured crawl origin."""
from __future__ import annotations

import asyncio
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.ingestion.adapters import parser_for
from app.ingestion.registry import ALL_REGISTRY

OUTPUT = ROOT / "compliance/robots"
FIXTURES = ROOT / "backend/tests/fixtures/chairs"
USER_AGENT = "TUM-Project-Studies-Portal"


def crawl_urls() -> set[str]:
    urls = {adapter.source_urls[0] for adapter in ALL_REGISTRY}
    manifest_path = FIXTURES / "manifest.json"
    if not manifest_path.exists(): return urls
    rows = {row["slug"]: row for row in json.loads(manifest_path.read_text())["sources"]}
    for adapter in ALL_REGISTRY:
        row = rows.get(adapter.slug, {})
        fixture = row.get("fixture")
        if not fixture or not fixture.endswith(".html") or not adapter.child_url_patterns: continue
        content = (FIXTURES / fixture).read_bytes()
        urls.update(parser_for(adapter).child_links(adapter, row.get("final_url", adapter.source_urls[0]), content))
    return urls


def policy_result(text: str, url: str) -> tuple[bool, float | None]:
    parser = RobotFileParser()
    parser.set_url(f"{urlparse(url).scheme}://{urlparse(url).netloc}/robots.txt")
    parser.parse(text.splitlines())
    return parser.can_fetch(USER_AGENT, url), parser.crawl_delay(USER_AGENT) or parser.crawl_delay("*")


async def main() -> int:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    urls = crawl_urls()
    origins = sorted({f"{urlparse(url).scheme}://{urlparse(url).netloc}" for url in urls} | {"https://www.tum.de"})
    records = []
    async with httpx.AsyncClient(follow_redirects=True, timeout=20, headers={"User-Agent": f"{USER_AGENT}/1.0"}) as client:
        for origin in origins:
            robots_url = f"{origin}/robots.txt"; host = urlparse(origin).netloc
            relevant = [url for url in sorted(urls) if urlparse(url).netloc == host]
            record = {"origin": origin, "robots_url": robots_url}
            try:
                response = await asyncio.wait_for(client.get(robots_url), timeout=25)
                body = response.content
                (OUTPUT / f"{host}.txt").write_bytes(body)
                record.update(status=response.status_code, final_url=str(response.url), sha256=hashlib.sha256(body).hexdigest())
                if response.status_code == 200:
                    decisions = [{"url": url, "allowed": policy_result(response.text, url)[0]} for url in relevant]
                    _, delay = policy_result(response.text, origin + "/")
                    record.update(policy="rules_applied", crawl_delay=delay, urls=decisions,
                                  compliant=all(item["allowed"] for item in decisions))
                elif response.status_code in {401, 403}:
                    record.update(policy="disallow_all", compliant=False, urls=[{"url": url, "allowed": False} for url in relevant])
                elif 400 <= response.status_code < 500:
                    record.update(policy="allow_all_no_policy", compliant=True, urls=[{"url": url, "allowed": True} for url in relevant])
                else:
                    record.update(policy="temporarily_unavailable_defer_crawl", compliant=False, urls=[{"url": url, "allowed": False} for url in relevant])
            except Exception as error:
                (OUTPUT / f"{host}.txt").write_text("", encoding="utf-8")
                record.update(status="error", policy="temporarily_unavailable_defer_crawl", compliant=False,
                              error=f"{type(error).__name__}: {error}", urls=[{"url": url, "allowed": False} for url in relevant])
            records.append(record)
            print(f"{host}: {record['status']} ({record['policy']})", flush=True)

    generated = datetime.now(timezone.utc).isoformat()
    report = {"generated_at": generated, "user_agent": USER_AGENT, "origins": records}
    (OUTPUT / "manifest.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    lines = ["# Robots.txt compliance audit", "", f"Generated: `{generated}`", "",
             f"Crawler token: `{USER_AGENT}`", "", "Robots rules are origin-specific. HTTP 4xx responses other than 401/403 are treated as no published policy; 401/403 disallow crawling; network and 5xx failures defer crawling.", "",
             "| Origin | HTTP | Policy | Registered/traversed URLs | Allowed |", "|---|---:|---|---:|---:|"]
    for item in records:
        checked = len(item["urls"]); allowed = sum(entry["allowed"] for entry in item["urls"])
        lines.append(f"| {item['origin']} | {item['status']} | {item['policy']} | {checked} | {allowed}/{checked} |")
    blocked = [entry["url"] for item in records for entry in item["urls"] if not entry["allowed"]]
    lines += ["", "## Result", "", ("All configured crawl targets are allowed by the successfully retrieved policies." if not blocked and all(r["compliant"] for r in records) else "The crawler must not run against every configured target until the exceptions below are resolved."), ""]
    if blocked:
        lines += ["### Disallowed targets", ""] + [f"- `{url}`" for url in blocked] + [""]
    unavailable = [r for r in records if r["policy"] == "temporarily_unavailable_defer_crawl"]
    if unavailable:
        lines += ["### Deferred origins", ""] + [f"- `{r['origin']}` — {r['status']}" for r in unavailable] + [""]
    lines += ["## Cached files", "", "Each origin's raw response body is stored beside this summary. `manifest.json` contains hashes and per-URL decisions.", ""]
    (OUTPUT / "SUMMARY.md").write_text("\n".join(lines), encoding="utf-8")
    return 0 if all(r["compliant"] for r in records) else 1


if __name__ == "__main__": raise SystemExit(asyncio.run(main()))
