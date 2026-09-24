from __future__ import annotations
import hashlib, json, re
from datetime import date, datetime, timezone
from pathlib import Path
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from ..db import Base, Chair, Department, Listing, Source, engine, session_factory
from ..listing_references import next_reference_code
from ..schemas import Status
from .adapters import parser_for
from .registry import DEPARTMENTS, REGISTRY

FIXTURES = Path(__file__).resolve().parents[2] / "tests/fixtures/chairs"

_PUBLISHED = re.compile(r"\s*\((?:published (?:at|on)|veröffentlicht am)\s+(\d{2}[/\.]\d{2}[/\.]\d{4})\)\s*$", re.IGNORECASE)
_LEADING_PUBLICATION = re.compile(r"^\s*\[(\d{2}[/\.]\d{2}[/\.]\d{4})\]\s*")

def publication_from_title(title: str) -> tuple[str, date | None]:
    match = _LEADING_PUBLICATION.search(title)
    if match:
        value = match.group(1).replace(".", "/")
        return title[match.end():].lstrip(), datetime.strptime(value, "%d/%m/%Y").date()
    match = _PUBLISHED.search(title)
    if not match: return title, None
    value = match.group(1).replace(".", "/")
    return title[:match.start()].rstrip(), datetime.strptime(value, "%d/%m/%Y").date()


def _fixture_rows() -> dict[str, dict]:
    return {row["slug"]: row for row in json.loads((FIXTURES / "manifest.json").read_text())["sources"]}


def ingest_department(department_name: str) -> dict:
    """Deterministically ingest one department from the latest frozen source audit."""
    adapters = [adapter for adapter in REGISTRY if adapter.department == department_name]
    if not adapters: raise ValueError(f"Unknown department: {department_name}")
    Base.metadata.create_all(engine())
    fixtures = _fixture_rows(); now = datetime.now(timezone.utc)
    stats = {"department": department_name, "sources": len(adapters), "discovered": 0, "created": 0, "updated": 0, "failed": []}
    with session_factory()() as session:
        department_slug = next(slug for slug, name in DEPARTMENTS.items() if name == department_name)
        department = session.scalar(select(Department).where(Department.slug == department_slug))
        if not department:
            department = Department(slug=department_slug, name=department_name); session.add(department); session.flush()
        for adapter in adapters:
            chair = session.scalar(select(Chair).where(Chair.slug == adapter.slug))
            if not chair:
                chair = Chair(department_id=department.id, slug=adapter.slug, name=adapter.name); session.add(chair); session.flush()
            source = session.scalar(select(Source).where(Source.chair_id == chair.id, Source.url == adapter.source_urls[0]))
            if not source:
                source = Source(chair_id=chair.id, url=adapter.source_urls[0], adapter=adapter.family); session.add(source)
            row = fixtures.get(adapter.slug, {})
            if row.get("status") != 200 or not row.get("fixture"):
                stats["failed"].append({"chair": adapter.name, "error": row.get("error", "fixture unavailable")}); continue
            content = (FIXTURES / row["fixture"]).read_bytes()
            candidates = parser_for(adapter).discover(adapter, row.get("final_url", adapter.source_urls[0]), content)
            stats["discovered"] += len(candidates)
            seen_keys = set()
            for candidate in candidates:
                seen_keys.add(candidate.stable_source_key)
                digest = hashlib.sha256(candidate.source_text.encode()).hexdigest()
                display_title, title_published_at = publication_from_title(candidate.title)
                display_summary, summary_published_at = publication_from_title(candidate.source_text[:3000])
                published_at = title_published_at or summary_published_at
                listing = session.scalar(select(Listing).where(Listing.chair_id == chair.id, Listing.stable_source_key == candidate.stable_source_key))
                listing_page_url = row.get("final_url", adapter.source_urls[0])
                artifact_url = candidate.source_url if candidate.source_url != listing_page_url else None
                normalized = {"department": department_name, "chair": adapter.name, "source_url": listing_page_url,
                              "artifact_url": artifact_url, "application_url": None, "topics": [], "language": None}
                if listing is None:
                    listing = Listing(chair_id=chair.id, stable_source_key=candidate.stable_source_key,
                                      slug=f"{adapter.slug}-{candidate.stable_source_key[:10]}",
                                      reference_code=next_reference_code(session, adapter.opportunity_type), title=display_title,
                                      summary=display_summary, normalized=normalized, content_hash=digest,
                                      status=Status.active, published_at=published_at, first_seen_at=now, last_seen_at=now)
                    session.add(listing); stats["created"] += 1
                else:
                    listing.title = display_title; listing.summary = display_summary
                    listing.normalized = normalized; listing.content_hash = digest; listing.status = Status.active
                    listing.published_at = published_at
                    listing.last_seen_at = now; listing.consecutive_misses = 0; stats["updated"] += 1
            existing = session.scalars(select(Listing).where(Listing.chair_id == chair.id, Listing.status == Status.active)).all()
            for listing in existing:
                if listing.stable_source_key not in seen_keys:
                    listing.consecutive_misses += 1
                    if listing.consecutive_misses >= 2: listing.status = Status.archived
        session.commit()
    return stats
