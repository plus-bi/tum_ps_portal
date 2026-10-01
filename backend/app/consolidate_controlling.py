"""Consolidate the approved German/English chair duplication without deleting history.

Run `python -m app.consolidate_controlling` to inspect; add `--apply` to commit.
"""
import argparse
import json

from sqlalchemy import select

from .db import Bookmark, Chair, Listing, ManualOverride, NotificationDelivery, OrganizationAttribution, SavedSearch, Source, session_factory
from .ingestion.live import ingestion_lock
from .listing_overrides import manual_text_overrides
from .schemas import Status


def document_url(listing: Listing) -> str | None:
    data = listing.normalized or {}
    return data.get("artifact_url") or data.get("source_url")


def consolidate(session, apply: bool = False) -> dict:
    chairs = {row.slug: row for row in session.scalars(select(Chair).where(
        Chair.slug.in_(("controlling", "management-accounting"))).with_for_update())}
    if set(chairs) != {"controlling", "management-accounting"}:
        raise RuntimeError("Both chair records must exist")
    kept = list(session.scalars(select(Listing).where(Listing.chair_id == chairs["controlling"].id).with_for_update()))
    retired = list(session.scalars(select(Listing).where(Listing.chair_id == chairs["management-accounting"].id).with_for_update()))
    by_url = {}
    for row in kept:
        url = document_url(row)
        if not url or url in by_url:
            raise RuntimeError("Canonical chair has missing or duplicate document URLs")
        by_url[url] = row
    pairs = []
    for row in retired:
        if (row.normalized or {}).get("merged_into_slug"):
            continue
        target = by_url.get(document_url(row))
        if target is None:
            raise RuntimeError(f"Unmatched English project {row.reference_code}; no changes committed")
        pairs.append((row, target))
    report = {"duplicate_projects": len(pairs), "canonical_active_projects": sum(row.status == Status.active for row in kept),
              "aliases": {old.slug: target.slug for old, target in pairs}, "applied": apply}
    if not apply:
        return report
    for old, target in pairs:
        old.normalized = {**old.normalized, "merged_into_slug": target.slug, "merged_into_reference_code": target.reference_code}
        old.status = Status.archived
        target.first_seen_at = min(target.first_seen_at, old.first_seen_at)
        target.last_seen_at = max(target.last_seen_at, old.last_seen_at)
        # PDF profiles are already shared by document hash. Preserve any missing HTML extraction too.
        for field in ("description_markdown", "description_hash", "description_source_url", "description_content_hash"):
            if field not in target.normalized and field in old.normalized:
                target.normalized = {**target.normalized, field: old.normalized[field]}
        for bookmark in session.scalars(select(Bookmark).where(Bookmark.listing_id == old.id)):
            existing = session.scalar(select(Bookmark).where(Bookmark.listing_id == target.id, Bookmark.user_id == bookmark.user_id))
            if existing:
                session.delete(bookmark)
            else:
                bookmark.listing_id = target.id
        for delivery in session.scalars(select(NotificationDelivery).where(NotificationDelivery.listing_id == old.id)):
            delivery.listing_id = target.id
        overrides = manual_text_overrides(session, target.id)
        for field, value in manual_text_overrides(session, old.id).items():
            if field not in overrides:
                session.add(ManualOverride(listing_id=target.id, field=field, value={"value": value}, actor_id="chair-consolidation"))
                setattr(target, field, value)
        for attribution in session.scalars(select(OrganizationAttribution).where(OrganizationAttribution.listing_id == old.id)):
            existing = session.scalar(select(OrganizationAttribution).where(
                OrganizationAttribution.listing_id == target.id,
                OrganizationAttribution.content_hash == attribution.content_hash,
                OrganizationAttribution.extractor_version == attribution.extractor_version))
            if existing is None:
                session.add(OrganizationAttribution(listing_id=target.id, content_hash=attribution.content_hash,
                    extractor_version=attribution.extractor_version, status=attribution.status,
                    academic_units=attribution.academic_units, project_partners=attribution.project_partners,
                    extracted_at=attribution.extracted_at))
    for source in session.scalars(select(Source).where(Source.chair_id == chairs["management-accounting"].id)):
        source.enabled = False
    def canonical_query(value):
        if isinstance(value, dict):
            return {key: canonical_query(item) for key, item in value.items()}
        if isinstance(value, list):
            return [canonical_query(item) for item in value]
        return "Controlling" if value == "Management Accounting" else "controlling" if value == "management-accounting" else value
    for search in session.scalars(select(SavedSearch)):
        search.query = canonical_query(search.query)
    session.flush()
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    with ingestion_lock() as acquired:
        if not acquired:
            raise RuntimeError("Ingestion is running; retry consolidation after it finishes")
        with session_factory()() as session, session.begin():
            report = consolidate(session, args.apply)
            print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
