from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable

from sqlalchemy import select, text

from ..config import settings
from ..db import (
    Base, Chair, CrawlRun, Department, Listing, ListingVersion, Source, SourceArtifact,
    engine, session_factory,
)
from ..schemas import Status
from .adapters import Candidate, parser_for
from .documents import extract
from .fetcher import Fetched, PoliteFetcher
from .pdf_backfill import is_pdf_url, store_pdf_url
from .registry import ALL_REGISTRY, ChairAdapter, DEPARTMENTS
from .service import publication_from_title

logger = logging.getLogger(__name__)
LOCK_ID = 1414876496  # Stable PostgreSQL advisory-lock key for the whole ingestion run.


def log_event(level: int, event: str, **fields) -> None:
    logger.log(level, json.dumps({"event": event, **fields}, default=str, sort_keys=True))


@dataclass(frozen=True)
class LiveArtifact:
    fetched: Fetched
    extracted_text: str


@dataclass(frozen=True)
class DiscoveryResult:
    top: Fetched
    candidates: tuple[Candidate, ...] = ()
    artifacts: tuple[LiveArtifact, ...] = ()
    failures: tuple[dict, ...] = ()


def _media_type(item: Fetched) -> str:
    media = item.media_type.split(";", 1)[0].casefold().strip()
    path = item.url.casefold().split("?", 1)[0]
    if media in {"", "application/octet-stream"}:
        if path.endswith(".pdf"): return "application/pdf"
        if path.endswith(".docx"): return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        if path.endswith((".html", ".htm", "/")): return "text/html"
    return media


def _deduplicate(candidates: Iterable[Candidate]) -> tuple[Candidate, ...]:
    chosen: dict[tuple[str, str], Candidate] = {}
    for candidate in candidates:
        identity = (candidate.source_url.rstrip("/").casefold(), " ".join(candidate.title.casefold().split()))
        previous = chosen.get(identity)
        if previous is None or len(candidate.source_text) < len(previous.source_text):
            chosen[identity] = candidate
    return tuple(chosen.values())


async def discover_adapter(adapter: ChairAdapter, fetcher: PoliteFetcher, *, etag: str | None = None,
                           last_modified: str | None = None, max_depth: int = 2) -> DiscoveryResult:
    """Fetch one chair and its explicitly scoped children without touching persistence."""
    top = await fetcher.fetch(adapter.source_urls[0], etag=etag, last_modified=last_modified)
    if top.not_modified:
        return DiscoveryResult(top=top)
    if "html" not in _media_type(top):
        raise ValueError(f"Chair source is not HTML ({top.media_type}): {top.url}")

    parser = parser_for(adapter)
    candidates = list(parser.discover(adapter, top.url, top.content))
    artifacts: list[LiveArtifact] = [LiveArtifact(top, extract(top.content, _media_type(top)))]
    failures: list[dict] = []
    queue = ([(url, 1) for url in parser.child_links(adapter, top.url, top.content)]
             if adapter.child_url_patterns else [])
    seen = {adapter.source_urls[0], top.url}

    while queue:
        child_url, depth = queue.pop(0)
        if child_url in seen: continue
        seen.add(child_url)
        try:
            child = await fetcher.fetch(child_url)
            media = _media_type(child)
            child_text = extract(child.content, media)
            artifacts.append(LiveArtifact(child, child_text))
            if "html" in media:
                candidates.extend(parser.discover(adapter, child.url, child.content))
                if depth < max_depth:
                    queue.extend((url, depth + 1) for url in parser.child_links(adapter, child.url, child.content))
        except Exception as error:
            failure = {"url": child_url, "depth": depth, "error": f"{type(error).__name__}: {error}"[:1500]}
            failures.append(failure)
            log_event(logging.ERROR, "child_fetch_failed", chair=adapter.slug, **failure)

    return DiscoveryResult(top=top, candidates=_deduplicate(candidates), artifacts=tuple(artifacts),
                           failures=tuple(failures))


def _ensure_source(adapter: ChairAdapter) -> tuple[object, object]:
    """Create registry rows and return IDs without retaining a database session."""
    with session_factory()() as session:
        department_slug = next(slug for slug, name in DEPARTMENTS.items() if name == adapter.department)
        department = session.scalar(select(Department).where(Department.slug == department_slug))
        if department is None:
            department = Department(slug=department_slug, name=adapter.department)
            session.add(department); session.flush()
        chair = session.scalar(select(Chair).where(Chair.slug == adapter.slug))
        if chair is None:
            chair = Chair(department_id=department.id, slug=adapter.slug, name=adapter.name)
            session.add(chair); session.flush()
        source = session.scalar(select(Source).where(Source.chair_id == chair.id, Source.url == adapter.source_urls[0]))
        if source is None:
            source = Source(chair_id=chair.id, url=adapter.source_urls[0], adapter=adapter.family)
            session.add(source); session.flush()
        result = (source.id, chair.id)
        session.commit()
        return result


def _version(session, listing: Listing, digest: str, normalized: dict, source_text: str) -> None:
    session.add(ListingVersion(
        listing_id=listing.id, content_hash=digest,
        extracted={"title": listing.title, "summary": listing.summary, **normalized},
        evidence={"source_url": normalized["artifact_url"] or normalized["source_url"],
                  "excerpt": source_text[:1000]},
    ))


def _start_run(adapter: ChairAdapter, source_id, started_at: datetime):
    with session_factory()() as session:
        run = CrawlRun(source_id=source_id, status="running",
                       stats={"chair": adapter.slug, "requested_url": adapter.source_urls[0]},
                       started_at=started_at)
        session.add(run); session.flush(); run_id = run.id
        session.commit()
        return run_id


def _persist_success(adapter: ChairAdapter, source_id, chair_id, run_id, result: DiscoveryResult,
                     started_at: datetime) -> dict:
    now = datetime.now(timezone.utc)
    with session_factory()() as session:
        source = session.get(Source, source_id)
        source.etag = result.top.etag
        source.last_modified = result.top.last_modified
        source.consecutive_failures = source.consecutive_failures + 1 if result.failures else 0

        for artifact in result.artifacts:
            exists = session.scalar(select(SourceArtifact.id).where(
                SourceArtifact.source_id == source_id,
                SourceArtifact.content_hash == artifact.fetched.content_hash,
            ))
            if exists is None:
                session.add(SourceArtifact(source_id=source_id, content_hash=artifact.fetched.content_hash,
                                           media_type=_media_type(artifact.fetched),
                                           extracted_text=artifact.extracted_text))

        seen_keys: set[str] = set()
        created = updated = unchanged = 0
        for candidate in result.candidates:
            seen_keys.add(candidate.stable_source_key)
            digest = hashlib.sha256(candidate.source_text.encode()).hexdigest()
            display_title, title_date = publication_from_title(candidate.title)
            display_summary, summary_date = publication_from_title(candidate.source_text[:3000])
            listing_page_url = result.top.url
            artifact_url = candidate.source_url if candidate.source_url != listing_page_url else None
            normalized = {"department": adapter.department, "chair": adapter.name,
                          "source_url": listing_page_url, "artifact_url": artifact_url,
                          "application_url": None, "topics": [], "language": None,
                          "opportunity_type": adapter.opportunity_type}
            listing = session.scalar(select(Listing).where(
                Listing.chair_id == chair_id, Listing.stable_source_key == candidate.stable_source_key,
            ))
            if listing is None:
                listing = Listing(
                    chair_id=chair_id, stable_source_key=candidate.stable_source_key,
                    slug=f"{adapter.slug}-{candidate.stable_source_key[:10]}", title=display_title,
                    summary=display_summary, normalized=normalized, content_hash=digest,
                    status=Status.active, published_at=title_date or summary_date,
                    first_seen_at=now, last_seen_at=now,
                )
                session.add(listing); session.flush(); _version(session, listing, digest, normalized, candidate.source_text)
                created += 1
            else:
                changed = listing.content_hash != digest
                listing.title = display_title; listing.summary = display_summary
                listing.normalized = normalized; listing.content_hash = digest
                listing.published_at = title_date or summary_date
                listing.status = Status.active; listing.last_seen_at = now; listing.consecutive_misses = 0
                if changed: _version(session, listing, digest, normalized, candidate.source_text); updated += 1
                else: unchanged += 1

        # A partial crawl can safely add/update observed listings, but must never mark unseen ones missing.
        if not result.failures:
            existing = session.scalars(select(Listing).where(
                Listing.chair_id == chair_id, Listing.status == Status.active,
            )).all()
            for listing in existing:
                if listing.stable_source_key not in seen_keys:
                    listing.consecutive_misses += 1
                    if listing.consecutive_misses >= 2: listing.status = Status.archived

        status = "partial" if result.failures else "success"
        stats = {
            "chair": adapter.slug, "requested_url": adapter.source_urls[0], "final_url": result.top.url,
            "http_status": result.top.status_code, "content_hash": result.top.content_hash,
            "candidates": len(result.candidates), "created": created, "updated": updated,
            "unchanged": unchanged, "artifacts": len(result.artifacts), "failures": list(result.failures),
        }
        run = session.get(CrawlRun, run_id)
        run.status = status; run.stats = stats
        run.error = json.dumps(result.failures)[:5000] if result.failures else None
        run.finished_at = now
        session.commit()
    return {"crawl_run_id": str(run_id), "status": status, **stats}


def _persist_not_modified(adapter: ChairAdapter, source_id, chair_id, run_id, result: DiscoveryResult,
                          started_at: datetime) -> dict:
    now = datetime.now(timezone.utc)
    stats = {"chair": adapter.slug, "requested_url": adapter.source_urls[0], "final_url": result.top.url,
             "http_status": 304, "not_modified": True}
    with session_factory()() as session:
        source = session.get(Source, source_id); source.consecutive_failures = 0
        for listing in session.scalars(select(Listing).where(
            Listing.chair_id == chair_id, Listing.status == Status.active,
        )).all():
            listing.last_seen_at = now
            listing.consecutive_misses = 0
        run = session.get(CrawlRun, run_id)
        run.status = "not_modified"; run.stats = stats; run.finished_at = now
        session.commit()
    return {"crawl_run_id": str(run_id), "status": "not_modified", **stats}


def _persist_failure(adapter: ChairAdapter, source_id, run_id, started_at: datetime, error: Exception) -> dict:
    now = datetime.now(timezone.utc); message = f"{type(error).__name__}: {error}"[:5000]
    stats = {"chair": adapter.slug, "requested_url": adapter.source_urls[0]}
    with session_factory()() as session:
        source = session.get(Source, source_id); source.consecutive_failures += 1
        run = session.get(CrawlRun, run_id)
        run.status = "failed"; run.stats = stats; run.error = message; run.finished_at = now
        session.commit()
    log_event(logging.ERROR, "source_crawl_failed", crawl_run_id=run_id, chair=adapter.slug,
              url=adapter.source_urls[0], error=message)
    return {"crawl_run_id": str(run_id), "status": "failed", **stats, "error": message}


async def ingest_adapter_live(adapter: ChairAdapter, fetcher: PoliteFetcher) -> dict:
    started_at = datetime.now(timezone.utc)
    source_id, chair_id = _ensure_source(adapter)
    with session_factory()() as session:
        source = session.get(Source, source_id)
        if not source.enabled:
            outcome = {"status": "skipped", "chair": adapter.slug, "requested_url": adapter.source_urls[0],
                       "reason": "source disabled"}
            log_event(logging.INFO, "source_crawl_skipped", **outcome)
            return outcome
        # A partial run must re-fetch the top page so failed children are attempted again.
        etag = source.etag if source.consecutive_failures == 0 else None
        last_modified = source.last_modified if source.consecutive_failures == 0 else None
    run_id = _start_run(adapter, source_id, started_at)
    log_event(logging.INFO, "source_crawl_started", crawl_run_id=run_id, chair=adapter.slug,
              url=adapter.source_urls[0])
    try:
        result = await discover_adapter(adapter, fetcher, etag=etag, last_modified=last_modified)
        outcome = (_persist_not_modified(adapter, source_id, chair_id, run_id, result, started_at)
                   if result.top.not_modified else
                   _persist_success(adapter, source_id, chair_id, run_id, result, started_at))
        if not result.top.not_modified:
            pdf_urls = {candidate.source_url for candidate in result.candidates if is_pdf_url(candidate.source_url)}
            stored_pdfs = 0
            for url in pdf_urls:
                stored_pdfs += int(await store_pdf_url(url, fetcher))
            outcome["pdf_artifacts_stored"] = stored_pdfs
        level = logging.WARNING if outcome["status"] == "partial" else logging.INFO
        log_event(level, "source_crawl_finished", **outcome)
        return outcome
    except Exception as error:
        return _persist_failure(adapter, source_id, run_id, started_at, error)


@contextmanager
def ingestion_lock():
    connection = engine().connect(); acquired = True
    try:
        if connection.dialect.name == "postgresql":
            acquired = bool(connection.scalar(text("SELECT pg_try_advisory_lock(:key)"), {"key": LOCK_ID}))
        yield acquired
    finally:
        if acquired and connection.dialect.name == "postgresql":
            connection.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": LOCK_ID})
        connection.close()


async def ingest_live(adapters: Iterable[ChairAdapter] = ALL_REGISTRY, fetcher: PoliteFetcher | None = None) -> dict:
    Base.metadata.create_all(engine())
    selected = tuple(adapters)
    if fetcher is None:
        config = settings()
        fetcher = PoliteFetcher(delay_seconds=config.crawler_delay_seconds,
                                timeout_seconds=config.crawler_timeout_seconds,
                                max_attempts=config.crawler_max_attempts,
                                max_content_bytes=config.crawler_max_content_bytes)
    with ingestion_lock() as acquired:
        if not acquired:
            result = {"status": "skipped", "reason": "another ingestion run holds the database lock"}
            log_event(logging.WARNING, "ingestion_skipped", **result)
            return result
        started_at = datetime.now(timezone.utc)
        log_event(logging.INFO, "ingestion_started", sources=len(selected), started_at=started_at)
        results = [await ingest_adapter_live(adapter, fetcher) for adapter in selected]
        failures = sum(row["status"] == "failed" for row in results)
        partial = sum(row["status"] == "partial" for row in results)
        summary = {
            "status": "completed_with_failures" if failures or partial else "completed", "sources": len(results),
            "successful": sum(row["status"] in {"success", "not_modified"} for row in results),
            "partial": partial,
            "failed": failures,
            "skipped": sum(row["status"] == "skipped" for row in results),
            "results": results,
        }
        level = logging.ERROR if failures else logging.WARNING if partial else logging.INFO
        log_event(level, "ingestion_finished", **{key: value for key, value in summary.items() if key != "results"})
        return summary


def run_live(adapters: Iterable[ChairAdapter] = ALL_REGISTRY) -> dict:
    return asyncio.run(ingest_live(adapters))
