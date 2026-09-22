import asyncio

import httpx

from app.ingestion.fetcher import PoliteFetcher


class RecordingRobots:
    def __init__(self): self.checked = []
    def require_allowed(self, url): self.checked.append(url)


def test_redirect_destination_is_checked_against_robots():
    robots = RecordingRobots()

    def handler(request: httpx.Request):
        if request.url.host == "one.test":
            return httpx.Response(302, headers={"location": "https://two.test/project"})
        return httpx.Response(200, headers={"content-type": "text/html", "etag": '"v1"'}, content=b"<h1>Project Study</h1>")

    fetcher = PoliteFetcher(delay_seconds=0, robots=robots, transport=httpx.MockTransport(handler))
    result = asyncio.run(fetcher.fetch("https://one.test/start"))
    assert result.url == "https://two.test/project"
    assert result.etag == '"v1"'
    assert robots.checked == ["https://one.test/start", "https://two.test/project"]


def test_conditional_not_modified_response():
    robots = RecordingRobots()

    def handler(request: httpx.Request):
        assert request.headers["if-none-match"] == '"v1"'
        return httpx.Response(304)

    fetcher = PoliteFetcher(delay_seconds=0, robots=robots, transport=httpx.MockTransport(handler))
    result = asyncio.run(fetcher.fetch("https://one.test/start", etag='"v1"'))
    assert result.not_modified
    assert result.content == b""


def test_retryable_status_is_retried(monkeypatch):
    attempts = 0
    robots = RecordingRobots()

    def handler(request: httpx.Request):
        nonlocal attempts
        attempts += 1
        return (httpx.Response(503, request=request) if attempts == 1 else
                httpx.Response(200, headers={"content-type": "text/html"}, content=b"ok", request=request))

    async def no_sleep(_delay): pass
    monkeypatch.setattr("app.ingestion.fetcher.asyncio.sleep", no_sleep)
    fetcher = PoliteFetcher(delay_seconds=0, max_attempts=2, robots=robots,
                            transport=httpx.MockTransport(handler))
    result = asyncio.run(fetcher.fetch("https://one.test/start"))
    assert result.content == b"ok"
    assert attempts == 2
