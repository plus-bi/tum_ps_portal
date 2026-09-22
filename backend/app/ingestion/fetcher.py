from __future__ import annotations
import asyncio, hashlib, json, logging
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse
import httpx
from .robots import CachedRobotsPolicy

logger = logging.getLogger(__name__)


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
    def __init__(self, *, delay_seconds: float = 1.0, timeout_seconds: float = 20.0,
                 max_attempts: int = 3, max_content_bytes: int = 25_000_000,
                 robots: CachedRobotsPolicy | None = None,
                 transport: httpx.AsyncBaseTransport | None = None):
        self.delay = delay_seconds; self.timeout = timeout_seconds
        self.max_attempts = max_attempts; self.max_content_bytes = max_content_bytes
        self.robots = robots or CachedRobotsPolicy()
        self.transport = transport
        self._locks: dict[str, asyncio.Lock] = {}; self._last: dict[str, float] = {}

    async def _request(self, client: httpx.AsyncClient, url: str, headers: dict[str, str]) -> httpx.Response:
        self.robots.require_allowed(url)
        domain = urlparse(url).netloc.casefold()
        lock = self._locks.setdefault(domain, asyncio.Lock())
        async with lock:
            loop = asyncio.get_running_loop(); wait = self.delay - (loop.time() - self._last.get(domain, 0))
            if wait > 0: await asyncio.sleep(wait)
            try:
                response = await client.get(url, headers=headers, follow_redirects=False)
            finally:
                self._last[domain] = loop.time()
            return response

    async def fetch(self, url: str, *, etag: str | None = None, last_modified: str | None = None) -> Fetched:
        base_headers = {"User-Agent": "TUM-Project-Studies-Portal/1.0 (source verification crawler)"}
        if etag: base_headers["If-None-Match"] = etag
        if last_modified: base_headers["If-Modified-Since"] = last_modified
        retry_statuses = {429, 500, 502, 503, 504}
        last_error: Exception | None = None
        async with httpx.AsyncClient(timeout=self.timeout, transport=self.transport) as client:
            for attempt in range(1, self.max_attempts + 1):
                current = url
                try:
                    for redirect_count in range(6):
                        response = await self._request(client, current, base_headers)
                        if response.status_code in {301, 302, 303, 307, 308}:
                            location = response.headers.get("location")
                            if not location: response.raise_for_status()
                            current = urljoin(current, location)
                            continue
                        if response.status_code == 304:
                            return Fetched(current, 304, "", b"", "", etag, last_modified, True)
                        if response.status_code in retry_statuses:
                            raise httpx.HTTPStatusError(
                                f"retryable HTTP status {response.status_code}", request=response.request, response=response
                            )
                        response.raise_for_status()
                        content = response.content
                        if len(content) > self.max_content_bytes:
                            raise ValueError(f"Source exceeds {self.max_content_bytes} byte limit: {current}")
                        return Fetched(
                            current, response.status_code,
                            response.headers.get("content-type", "application/octet-stream"),
                            content, hashlib.sha256(content).hexdigest(), response.headers.get("etag"),
                            response.headers.get("last-modified"),
                        )
                    raise httpx.TooManyRedirects(f"More than 5 redirects for {url}")
                except (httpx.RequestError, httpx.HTTPStatusError) as error:
                    last_error = error
                    if isinstance(error, httpx.HTTPStatusError) and error.response.status_code not in retry_statuses:
                        raise
                    if attempt == self.max_attempts: raise
                    retry_after = getattr(error, "response", None)
                    raw_wait = retry_after.headers.get("retry-after") if retry_after is not None else None
                    delay = min(float(raw_wait), 30.0) if raw_wait and raw_wait.isdigit() else float(2 ** (attempt - 1))
                    logger.warning(json.dumps({"event": "fetch_retry", "url": url, "attempt": attempt,
                                               "wait_seconds": delay, "error": f"{type(error).__name__}: {error}"}))
                    await asyncio.sleep(delay)
        assert last_error is not None
        raise last_error
