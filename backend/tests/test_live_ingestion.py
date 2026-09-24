import asyncio

from sqlalchemy import create_engine, select

import app.db as db
from app.db import Base, CrawlRun, Listing, ManualOverride, Source
from app.ingestion.fetcher import Fetched
from app.ingestion.live import ingest_live
from app.ingestion.registry import REGISTRY
from app.schemas import Status


class FakeFetcher:
    def __init__(self, response=None, error=None): self.response = response; self.error = error
    async def fetch(self, url, **kwargs):
        if self.error: raise self.error
        return self.response


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
