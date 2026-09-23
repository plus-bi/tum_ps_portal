"""Capture frozen source fixtures and a machine-readable audit manifest."""
from __future__ import annotations
import asyncio, json, sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.ingestion.adapters import parser_for
from app.ingestion.documents import extract
from app.ingestion.fetcher import PoliteFetcher
from app.ingestion.registry import ALL_REGISTRY

FIXTURES = ROOT / "backend/tests/fixtures/chairs"

async def audit():
    FIXTURES.mkdir(parents=True, exist_ok=True)
    fetcher = PoliteFetcher(delay_seconds=1.0, timeout_seconds=30); manifest = []
    for adapter in ALL_REGISTRY:
        url = adapter.source_urls[0]; row = {"slug": adapter.slug, "name": adapter.name, "url": url, "family": adapter.family}
        try:
            fetched = await asyncio.wait_for(fetcher.fetch(url), timeout=35); suffix = ".html" if "html" in fetched.media_type else ".bin"
            path = FIXTURES / f"{adapter.slug}{suffix}"; path.write_bytes(fetched.content); parser = parser_for(adapter)
            row.update(status=fetched.status_code, final_url=fetched.url, media_type=fetched.media_type,
                       sha256=fetched.content_hash, fixture=path.name,
                       candidates=len(parser.discover(adapter, fetched.url, fetched.content)) if suffix == ".html" else None,
                       child_links=len(parser.child_links(adapter, fetched.url, fetched.content)) if suffix == ".html" else None)
            # Inline-card sources already retain their application links. Recursively freeze only
            # chair-audited second-level/document URL families to avoid mirroring unrelated files.
            children = []; queue = ([(link, 1) for link in parser.child_links(adapter, fetched.url, fetched.content)]
                                    if suffix == ".html" and adapter.child_url_patterns else [])
            seen = {url, fetched.url}
            while queue:
                child_url, depth = queue.pop(0)
                if child_url in seen: continue
                seen.add(child_url); child = {"url": child_url, "depth": depth}
                try:
                    item = await asyncio.wait_for(fetcher.fetch(child_url), timeout=35)
                    media = item.media_type.split(";", 1)[0]; extension = ".html" if "html" in media else ".pdf" if media == "application/pdf" else ".docx" if "wordprocessingml" in media else ".bin"
                    child_dir = FIXTURES / adapter.slug; child_dir.mkdir(exist_ok=True)
                    child_path = child_dir / f"{item.content_hash[:16]}{extension}"; child_path.write_bytes(item.content)
                    child.update(status=item.status_code, final_url=item.url, media_type=item.media_type,
                                 sha256=item.content_hash, fixture=str(child_path.relative_to(FIXTURES)))
                    if extension == ".html":
                        found = parser.discover(adapter, item.url, item.content); child["candidates"] = len(found)
                        if depth < 2: queue.extend((link, depth + 1) for link in parser.child_links(adapter, item.url, item.content))
                    elif extension in {".pdf", ".docx"}:
                        try: child["text_chars"] = len(extract(item.content, item.media_type))
                        except Exception as parse_error: child["parse_error"] = f"{type(parse_error).__name__}: {parse_error}"
                except Exception as child_error: child.update(status="error", error=f"{type(child_error).__name__}: {child_error}")
                children.append(child)
            row["children"] = children
        except Exception as error: row.update(status="error", error=f"{type(error).__name__}: {error}")
        manifest.append(row); print(f"{adapter.slug}: {row['status']}", flush=True)
        output = {"captured_at": datetime.now(timezone.utc).isoformat(), "sources": manifest}
        (FIXTURES / "manifest.json").write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    return 1 if any(x["status"] == "error" for x in manifest) else 0

if __name__ == "__main__": raise SystemExit(asyncio.run(audit()))
