import asyncio
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import httpx
from bs4 import BeautifulSoup
from sqlalchemy import create_engine, select

import app.db as db
from app.api import persisted_projects, project_description, project_profile
from app.db import Base, Listing, PDFArtifact, PDFProfileExtraction
from app.ingestion import profile_backfill
from app.ingestion.adapters import parser_for
from app.ingestion.fetcher import PoliteFetcher
from app.ingestion.live import ingest_live
from app.ingestion.project_profile import PdfTextCoverage
from app.ingestion.profile_sources import HTML_MARKDOWN_VERSION
from app.ingestion.registry import ALL_BY_SLUG
from app.schemas import Status
from profile_builders import document, empty_offer


ADAPTER = ALL_BY_SLUG["idp-chair-of-media-technology"]
FIXTURE = Path(__file__).parent / "fixtures/chairs/idp-chair-of-media-technology.html"


class AllowRobots:
    def require_allowed(self, url):
        pass


def test_lmt_fixture_yields_only_idp_offers_with_separate_markdown_and_pdf_links():
    candidates = parser_for(ADAPTER).discover(ADAPTER, ADAPTER.source_urls[0], FIXTURE.read_bytes())
    assert len(candidates) == 5
    assert len({item.stable_source_key for item in candidates}) == 5
    assert all(item.source_url == ADAPTER.source_urls[0] for item in candidates)
    assert all(item.pdf_url and "mode=pdfdownload" in item.pdf_url for item in candidates)
    assert all(item.description_markdown.startswith(f"# {item.title}\n") for item in candidates)
    assert "Robot Learning from Demonstration" in candidates[0].title
    assert candidates[0].stable_source_key.startswith("787a0ecbfc")
    assert candidates[1].stable_source_key.startswith("debfea2172")
    assert "Python and/or Matlab" in candidates[1].description_markdown
    assert "KalmanNet" not in candidates[1].description_markdown
    for candidate in candidates:
        assert all(other.title not in candidate.description_markdown for other in candidates if other is not candidate)
    assert "3D Hand-Object Reconstruction" not in [item.title for item in candidates]


def test_lmt_live_crawl_stores_html_markdown_without_fetching_timing_out_pdfs(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'lmt.db'}")
    monkeypatch.setattr(db, "_engine", engine)
    Base.metadata.create_all(engine)
    html = FIXTURE.read_bytes()
    fail_top = False
    pdf_requests = 0

    def respond(request):
        if request.url.path == "/en/lmt/student-thesis/":
            if fail_top:
                return httpx.Response(503)
            if request.headers.get("if-none-match") == '"lmt-v1"':
                return httpx.Response(304)
            return httpx.Response(200, content=html, headers={"ETag": '"lmt-v1"'})
        if request.url.host == "tumanager.ei.tum.de" and request.url.path == "/service.php":
            nonlocal pdf_requests
            pdf_requests += 1
            raise httpx.ConnectTimeout("PDF host timed out")
        return httpx.Response(404)

    fetcher = PoliteFetcher(delay_seconds=0, max_attempts=1, robots=AllowRobots(),
                            transport=httpx.MockTransport(respond))
    first = asyncio.run(ingest_live((ADAPTER,), fetcher))
    assert first["successful"] == 1
    assert asyncio.run(ingest_live((ADAPTER,), fetcher))["results"][0]["status"] == "not_modified"
    forced = asyncio.run(ingest_live((ADAPTER,), fetcher, force=True))
    assert forced["results"][0]["status"] == "success"
    assert forced["results"][0]["candidates"] == 5
    with db.session_factory()() as session:
        listings = session.scalars(select(Listing).order_by(Listing.title)).all()
        artifacts = session.scalars(select(PDFArtifact)).all()
        assert len(listings) == 5
        assert artifacts == []
        assert all(row.status == Status.active and row.normalized["description_markdown"].startswith("# ")
                   for row in listings)
        assert all(row.normalized["artifact_url"] is None and row.normalized["pdf_url"]
                   for row in listings)
        one = listings[0]
        html_hash = one.normalized["description_hash"]
        markdown = one.normalized["description_markdown"]
        slug = one.slug

    analyses = [row for row in profile_backfill._analyses() if row.content_hash == html_hash]
    assert len(analyses) == 1
    assert analyses[0].extracted_markdown_pages == [markdown]
    assert analyses[0].classifier_version == HTML_MARKDOWN_VERSION
    assert project_description(slug).markdown == markdown
    coverage = PdfTextCoverage.from_pages("digital_native", HTML_MARKDOWN_VERSION, [markdown])
    with db.session_factory()() as session:
        session.add(PDFProfileExtraction(content_hash=html_hash, **profile_backfill.current_version("low"),
                                         status="ok", attempts=1, errors=[], review_flags=[], evidence_issues=[],
                                         coverage=coverage.model_dump(mode="json"),
                                         document=document(empty_offer()).model_dump(mode="json")))
        session.commit()
    monkeypatch.setattr("app.api.settings", lambda: SimpleNamespace(
        organization_attribution_preview=False, public_url="http://localhost:8080"))
    assert next(row for row in persisted_projects() if row.slug == slug).has_profile
    assert next(row for row in persisted_projects() if row.slug == slug).has_description
    assert project_profile(slug).source_kind == "html"
    assert pdf_requests == 0

    fail_top = True
    failed = asyncio.run(ingest_live((ADAPTER,), fetcher))
    assert failed["failed"] == 1
    with db.session_factory()() as session:
        assert all(row.status == Status.active for row in session.scalars(select(Listing)))


def test_lmt_partial_child_failure_does_not_archive_unseen_offer(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'lmt-partial.db'}")
    monkeypatch.setattr(db, "_engine", engine)
    Base.metadata.create_all(engine)
    original = FIXTURE.read_bytes()
    reduced = BeautifulSoup(original, "html.parser")
    reduced.select(".tx-curlcontent-main > .accordion")[-1].decompose()
    reduced.body.append(BeautifulSoup('<a href="/en/lmt/student-thesis/details/">Details</a>', "html.parser"))
    partial_body = str(reduced).encode()
    child_adapter = replace(ADAPTER, child_url_patterns=("/en/lmt/student-thesis/details/",))
    body = original

    def respond(request):
        if request.url.path == "/en/lmt/student-thesis/":
            return httpx.Response(200, content=body)
        if request.url.path == "/en/lmt/student-thesis/details/":
            return httpx.Response(503)
        if request.url.host == "tumanager.ei.tum.de":
            raise httpx.ConnectTimeout("PDF host timed out")
        return httpx.Response(404)

    fetcher = PoliteFetcher(delay_seconds=0, max_attempts=1, robots=AllowRobots(),
                            transport=httpx.MockTransport(respond))
    assert asyncio.run(ingest_live((ADAPTER,), fetcher))["successful"] == 1
    body = partial_body
    assert asyncio.run(ingest_live((child_adapter,), fetcher))["partial"] == 1
    with db.session_factory()() as session:
        listings = session.scalars(select(Listing)).all()
        assert len(listings) == 5
        assert all(row.status == Status.active and row.consecutive_misses == 0 for row in listings)
