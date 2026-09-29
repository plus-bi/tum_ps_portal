"""Build reviewable organization candidates from stored PDF markdown; no network calls.

    python -m app.ingestion.organization_backfill --limit 20 --output /tmp/organizations.jsonl
    python -m app.ingestion.organization_backfill --apply
    python -m app.ingestion.organization_backfill --approve-file reviewed.jsonl
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import json
import re
import sys
from pathlib import Path
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy import inspect, select

from ..db import (Base, Chair, Listing, OrganizationAttribution, PDFAnalysis, PDFArtifact,
                  PDFProfileExtraction, engine, session_factory)
from .organization_attribution import EXTRACTOR_VERSION, OrganizationCandidates, _key, extract_organization_candidates
from .project_profile import DocumentExtraction, SCHEMA_VERSION
from ..profile_filters import offer_for_listing


def candidate_rows(limit: int | None = None) -> list[dict]:
    """Return current PDF-backed offers with short, page-cited organization candidates."""
    rows: list[dict] = []
    serials: dict[str, int] = defaultdict(int)
    with session_factory()() as session:
        listings = session.execute(select(Listing, Chair).join(Chair, Listing.chair_id == Chair.id)
                                   .where(Listing.status == "active").order_by(Listing.slug)).all()
        for listing, source_chair in listings:
            url = listing.normalized.get("artifact_url")
            artifact = session.scalar(select(PDFArtifact).where(PDFArtifact.url == url)) if url else None
            if not artifact or not artifact.content_hash:
                continue
            analysis = session.scalar(select(PDFAnalysis).where(PDFAnalysis.content_hash == artifact.content_hash))
            if not analysis or not analysis.extracted_markdown_pages:
                continue
            extraction = session.scalar(select(PDFProfileExtraction).where(
                PDFProfileExtraction.content_hash == artifact.content_hash,
                PDFProfileExtraction.schema_version == SCHEMA_VERSION,
                PDFProfileExtraction.status == "ok",
            ).order_by(PDFProfileExtraction.extracted_at.desc(), PDFProfileExtraction.id.desc()))
            if not extraction or not extraction.document or extraction.review_flags:
                continue
            try:
                document = DocumentExtraction.model_validate(extraction.document)
            except ValidationError:
                continue
            offer = offer_for_listing(document, listing.title)
            if offer is None:
                continue
            candidates = extract_organization_candidates(analysis.extracted_markdown_pages, offer)
            opportunity_type = listing.normalized.get("opportunity_type", "project_study")
            prefix = "IDP" if opportunity_type == "idp" else "PS"
            serials[prefix] += 1
            rows.append({"review_id": f"{prefix}-{serials[prefix]:03d}",
                         "opportunity_type": opportunity_type,
                         "reference_code": listing.reference_code, "title": listing.title,
                         "artifact_url": url,
                         "slug": listing.slug, "listing_id": str(listing.id),
                         "content_hash": artifact.content_hash, "source_name": source_chair.name,
                         "extractor_version": EXTRACTOR_VERSION, **candidates.model_dump(mode="json")})
            if limit is not None and len(rows) >= limit:
                break
    return rows


def apply_candidates(rows: list[dict]) -> dict[str, int]:
    Base.metadata.create_all(engine(), tables=[OrganizationAttribution.__table__])
    created = existing = 0
    with session_factory()() as session:
        for row in rows:
            previous = session.scalar(select(OrganizationAttribution).where(
                OrganizationAttribution.listing_id == UUID(row["listing_id"]),
                OrganizationAttribution.content_hash == row["content_hash"],
                OrganizationAttribution.extractor_version == EXTRACTOR_VERSION))
            if previous:
                existing += 1
                continue
            session.add(OrganizationAttribution(
                listing_id=UUID(row["listing_id"]), content_hash=row["content_hash"],
                extractor_version=EXTRACTOR_VERSION, status="needs_review",
                academic_units=row["academic_units"], project_partners=row["project_partners"]))
            created += 1
        session.commit()
    return {"created": created, "existing": existing}


def approve_rows(path: Path) -> dict[str, int]:
    """Approve reviewed JSONL rows, including corrections with valid page evidence."""
    if not inspect(engine()).has_table(OrganizationAttribution.__tablename__):
        raise ValueError("Run --apply before approving rows")
    approved = 0
    with session_factory()() as session:
        lines = sys.stdin if str(path) == "-" else path.read_text(encoding="utf-8").splitlines()
        for line in lines:
            if not line.strip():
                continue
            row = json.loads(line)
            if row.get("approve") is not True:
                continue
            current = session.scalar(select(OrganizationAttribution).join(Listing,
                OrganizationAttribution.listing_id == Listing.id).where(
                Listing.slug == row.get("slug"),
                OrganizationAttribution.content_hash == row.get("content_hash"),
                OrganizationAttribution.extractor_version == EXTRACTOR_VERSION))
            if current is None:
                raise ValueError(f"No current attribution for {row.get('slug')}")
            expected = OrganizationCandidates.model_validate({
                "academic_units": row.get("academic_units", []),
                "project_partners": row.get("project_partners", []),
            })
            listing = session.get(Listing, current.listing_id)
            artifact = session.scalar(select(PDFArtifact).where(
                PDFArtifact.url == listing.normalized.get("artifact_url")))
            analysis = session.scalar(select(PDFAnalysis).where(PDFAnalysis.content_hash == current.content_hash))
            if not artifact or artifact.content_hash != current.content_hash or not analysis:
                raise ValueError(f"PDF changed since report for {row.get('slug')}")
            pages = analysis.extracted_markdown_pages or []
            for mention in [*expected.academic_units, *expected.project_partners]:
                index = mention.evidence.page - 1
                if index >= len(pages):
                    raise ValueError(f"Invalid evidence page for {row.get('slug')}")
                page_text = re.sub(r"<[^>]+>", " ", pages[index])
                if (_key(mention.evidence.excerpt) not in _key(page_text)
                        or _key(mention.name) not in _key(mention.evidence.excerpt)):
                    raise ValueError(f"Unverified organization quote for {row.get('slug')}")
            current.academic_units = [item.model_dump(mode="json") for item in expected.academic_units]
            current.project_partners = [item.model_dump(mode="json") for item in expected.project_partners]
            current.status = "approved"
            approved += 1
        session.commit()
    return {"approved": approved}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--output", type=Path, help="Write candidate JSONL for manual review; '-' means stdout")
    parser.add_argument("--apply", action="store_true", help="Store candidates as needs_review")
    parser.add_argument("--approve-file", type=Path, help="Approve reviewed, unchanged JSONL rows; '-' means stdin")
    args = parser.parse_args()
    if args.approve_file:
        print(json.dumps(approve_rows(args.approve_file), sort_keys=True))
        return
    rows = candidate_rows(args.limit)
    if args.output:
        rendered = "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows)
        if str(args.output) == "-":
            sys.stdout.write(rendered)
        else:
            args.output.write_text(rendered, encoding="utf-8")
    summary = {"offers": len(rows), "academic_unit_candidates": sum(bool(row["academic_units"]) for row in rows),
               "partner_candidates": sum(bool(row["project_partners"]) for row in rows)}
    if args.apply:
        summary.update(apply_candidates(rows))
    print(json.dumps(summary, sort_keys=True), file=sys.stderr if str(args.output) == "-" else sys.stdout)


if __name__ == "__main__":
    main()
