from __future__ import annotations
import asyncio, hashlib
from dataclasses import dataclass
from urllib.parse import urlparse
import httpx
from .robots import CachedRobotsPolicy


@dataclass(frozen=True)
class Fetched:
    url: str
    status_code: int
    media_type: str
    content: bytes
    content_hash: str
    etag: str | None
    last_modified: str | None
    not_modified: bool = False


class PoliteFetcher:
    def __init__(self, *, delay_seconds: float = 1.0, timeout_seconds: float = 20.0, robots: CachedRobotsPolicy | None = None):
        self.delay = delay_seconds; self.timeout = timeout_seconds
        self.robots = robots or CachedRobotsPolicy()
        self._locks: dict[str, asyncio.Lock] = {}; self._last: dict[str, float] = {}

    async def fetch(self, url: str, *, etag: str | None = None, last_modified: str | None = None) -> Fetched:
        self.robots.require_allowed(url)
        domain = urlparse(url).netloc.casefold()
        lock = self._locks.setdefault(domain, asyncio.Lock())
        async with lock:
            loop = asyncio.get_running_loop(); wait = self.delay - (loop.time() - self._last.get(domain, 0))
            if wait > 0: await asyncio.sleep(wait)
            headers = {"User-Agent": "TUM-Project-Studies-Portal/1.0 (source verification crawler)"}
            if etag: headers["If-None-Match"] = etag
            if last_modified: headers["If-Modified-Since"] = last_modified
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                response = await client.get(url, headers=headers)
                self._last[domain] = loop.time()
                if response.status_code == 304:
                    return Fetched(str(response.url), 304, "", b"", "", etag, last_modified, True)
                response.raise_for_status()
                return Fetched(str(response.url), response.status_code, response.headers.get("content-type", "application/octet-stream"),
                               response.content, hashlib.sha256(response.content).hexdigest(), response.headers.get("etag"), response.headers.get("last-modified"))
