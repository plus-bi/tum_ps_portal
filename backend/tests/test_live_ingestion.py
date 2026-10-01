import asyncio
from dataclasses import replace
from pathlib import Path

import httpx

from sqlalchemy import create_engine, select

import app.db as db
from app.db import Base, CrawlRun, Listing, ManualOverride, Source
from app.ingestion.fetcher import Fetched, PoliteFetcher
from app.ingestion.live import ingest_live
from app.ingestion.registry import ALL_BY_SLUG, REGISTRY
from app.schemas import Status


class FakeFetcher:
    def __init__(self, response=None, error=None): self.response = response; self.error = error
    async def fetch(self, url, **kwargs):
        if self.error: raise self.error
        return self.response


def test_management_accounting_live_crawl_retains_listings_after_partial_and_failed_runs(tmp_path, monkeypatch):
    test_engine = create_engine(f"sqlite:///{tmp_path / 'management-accounting.db'}")
    monkeypatch.setattr(db, "_engine", test_engine)
    Base.metadata.create_all(test_engine)
    adapter = replace(ALL_BY_SLUG["controlling"], source_urls=("https://www.fa.mgt.tum.de/en/controlling/teaching/projektstudien/",), child_url_patterns=("/detail/",))
    full_page = (Path(__file__).parent / "fixtures/chairs/management-accounting.html").read_bytes()
    partial_page = b'''<div class="frame"><p><strong>Recent Proposals:</strong></p>
        <ul><li><a href="/files/new.pdf">New proposal</a></li></ul></div>
        <a href="/detail/missing">Project study detail</a>'''
    state = {"page": full_page, "fail_top": False}

    def respond(request):
        if request.url.path == "/detail/missing":
            return httpx.Response(503)
        if state["fail_top"]:
            return httpx.Response(503)
        return httpx.Response(200, content=state["page"], headers={"content-type": "text/html"})

    class AllowRobots:
        def require_allowed(self, url):
            pass

    async def skip_pdf_storage(url, fetcher):
        return False

    monkeypatch.setattr("app.ingestion.live.store_pdf_url", skip_pdf_storage)
    fetcher = PoliteFetcher(delay_seconds=0, max_attempts=1, robots=AllowRobots(),
                            transport=httpx.MockTransport(respond))
    assert asyncio.run(ingest_live((adapter,), fetcher))["results"][0]["candidates"] == 52
    state["page"] = partial_page
    assert asyncio.run(ingest_live((adapter,), fetcher))["results"][0]["status"] == "partial"
    state["fail_top"] = True
    assert asyncio.run(ingest_live((adapter,), fetcher))["results"][0]["status"] == "failed"
    with db.session_factory()() as session:
        listings = session.scalars(select(Listing)).all()
        assert len(listings) == 53
        assert all(row.status == Status.active and row.consecutive_misses == 0 for row in listings)
        assert [row.status for row in session.scalars(select(CrawlRun).order_by(CrawlRun.started_at))] == [
            "success", "partial", "failed",
        ]


def test_failed_live_crawl_is_logged_without_changing_listing_lifecycle(tmp_path, monkeypatch):
    test_engine = create_engine(f"sqlite:///{tmp_path / 'live.db'}")
    monkeypatch.setattr(db, "_engine", test_engine)
    Base.metadata.create_all(test_engine)
    adapter = REGISTRY[0]
    body = f"<article><h2>{adapter.name}: Project Study - Data</h2><p>Applications open.</p></article>".encode()
    fetched = Fetched(adapter.source_urls[0], 200, "text/html", body, "hash-1", '"v1"', None)

    success = asyncio.run(ingest_live((adapter,), FakeFetcher(response=fetched)))
    assert success["successful"] == 1

    failure = asyncio.run(ingest_live((adapter,), FakeFetcher(error=RuntimeError("network unavailable"))))
    assert failure["failed"] == 1
    with db.session_factory()() as session:
        listing = session.scalar(select(Listing))
        source = session.scalar(select(Source))
        runs = session.scalars(select(CrawlRun).order_by(CrawlRun.started_at)).all()
        assert listing.status == Status.active
        assert listing.reference_code == "ps-001"
        assert listing.consecutive_misses == 0
        assert source.consecutive_failures == 1
        assert [run.status for run in runs] == ["success", "failed"]
        assert "network unavailable" in runs[-1].error


def test_manual_title_and_summary_overrides_survive_successful_recrawl(tmp_path, monkeypatch):
    test_engine = create_engine(f"sqlite:///{tmp_path / 'overrides.db'}")
    monkeypatch.setattr(db, "_engine", test_engine)
    Base.metadata.create_all(test_engine)
    adapter = REGISTRY[0]
    first_body = f"""<article><h2>{adapter.name}: Project Study - Data</h2>
    <p>First source description.</p></article>""".encode()
    first = Fetched(adapter.source_urls[0], 200, "text/html", first_body, "hash-1", None, None)
    asyncio.run(ingest_live((adapter,), FakeFetcher(response=first)))

    with db.session_factory()() as session:
        listing = session.scalar(select(Listing))
        session.add_all([
            ManualOverride(listing_id=listing.id, field="title", value={"value": "Curated project title"}, actor_id="test"),
            ManualOverride(listing_id=listing.id, field="summary", value={"value": "Curated project summary."}, actor_id="test"),
        ])
        session.commit()

    second_body = f"""<article><h2>{adapter.name}: Project Study - Data</h2>
    <p>Updated source description.</p></article>""".encode()
    second = Fetched(adapter.source_urls[0], 200, "text/html", second_body, "hash-2", None, None)
    asyncio.run(ingest_live((adapter,), FakeFetcher(response=second)))

    with db.session_factory()() as session:
        listing = session.scalar(select(Listing))
        assert listing.title == "Curated project title"
        assert listing.summary == "Curated project summary."
