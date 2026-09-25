from datetime import date
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import ValidationError
from .ingestion.registry import ALL_REGISTRY, DEPARTMENTS
from .ingestion.project_profile import DocumentExtraction, EvidenceIssue, PdfTextCoverage, SCHEMA_VERSION
from .schemas import Freshness, Project, ProjectProfileDetail, Status, Topic
from .db import Chair, Department, Listing, PDFArtifact, PDFProfileExtraction, session_factory
from .ingestion.lifecycle import freshness
from sqlalchemy import select

router = APIRouter(prefix="/api/v1")

# Demo data keeps the UI useful before the first database-backed crawl.
PROJECTS = [Project(
    slug="example-project-study",
    reference_code="ps-001",
    title="Example Project Study",
    summary="Run the ingestion worker to replace this development record with source-grounded listings.",
    department="Operations and Technology", chair="Operations Management",
    topics=[Topic.operations_supply_chain], language="English", source_url="https://www.mgt.tum.de/",
    freshness=Freshness.undated,
)]

def _project_from_listing(listing: Listing, chair: Chair, department: Department,
                          *, has_profile: bool = False) -> Project:
    return Project(slug=listing.slug, reference_code=listing.reference_code,
                   title=listing.title, summary=listing.summary,
                   department=department.name, chair=chair.name,
                   opportunity_type=listing.normalized.get("opportunity_type", "project_study"),
                   company=listing.normalized.get("company"), language=listing.normalized.get("language"),
                   topics=listing.normalized.get("topics", []), location=listing.normalized.get("location"),
                   application_url=listing.normalized.get("application_url"),
                   source_url=listing.normalized["source_url"],
                   artifact_url=listing.normalized.get("artifact_url"), has_profile=has_profile,
                   published_at=listing.published_at, first_seen_at=listing.first_seen_at,
                   last_seen_at=listing.last_seen_at, status=listing.status,
                   freshness=freshness(listing.published_at))


# Extractions from a document without a readable text layer cannot be checked against the PDF,
# so they are not shown; unverified citations are shown with a warning.
HIDDEN_PROFILE_FLAGS = {"requires_ocr"}


def _displayable_profiles(session, content_hashes: set[str] | None = None) -> dict[str, UUID]:
    """Id of the latest ok extraction of the current schema per content hash, for hashes whose
    latest extraction has offers and no hiding flag. Loads no documents."""
    query = select(PDFProfileExtraction.content_hash, PDFProfileExtraction.id, PDFProfileExtraction.review_flags).where(
        PDFProfileExtraction.status == "ok",
        PDFProfileExtraction.schema_version == SCHEMA_VERSION,
        PDFProfileExtraction.document["document_kind"].as_string().in_(("offer", "multi_offer")),
    ).order_by(PDFProfileExtraction.extracted_at, PDFProfileExtraction.id)
    if content_hashes is not None:
        query = query.where(PDFProfileExtraction.content_hash.in_(content_hashes))
    latest = {content_hash: (row_id, flags) for content_hash, row_id, flags in session.execute(query)}
    return {content_hash: row_id for content_hash, (row_id, flags) in latest.items()
            if not HIDDEN_PROFILE_FLAGS.intersection(flags or [])}


def persisted_projects() -> list[Project]:
    try:
        with session_factory()() as session:
            rows = session.execute(select(Listing, Chair, Department)
                                   .join(Chair, Listing.chair_id == Chair.id)
                                   .join(Department, Chair.department_id == Department.id)).all()
            artifact_hashes = dict(session.execute(select(PDFArtifact.url, PDFArtifact.content_hash)).all())
            profile_hashes = set(_displayable_profiles(session))
            return [_project_from_listing(
                listing, chair, department,
                has_profile=artifact_hashes.get(listing.normalized.get("artifact_url")) in profile_hashes,
            ) for listing, chair, department in rows]
    except Exception:
        return []


@router.get("/projects")
def projects(q: str | None = None, status: Status = Status.active, department: list[str] = Query(default=[]),
             chair: list[str] = Query(default=[]), topic: list[Topic] = Query(default=[]),
             sort: str = "relevance", page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100)):
    stored = persisted_projects()
    last_updated_at = max((project.last_seen_at for project in stored), default=None)
    rows = [p for p in (stored or PROJECTS) if p.status == status]
    if q:
        needle = q.casefold(); rows = [p for p in rows if needle in f"{p.reference_code} {p.title} {p.summary or ''} {p.chair}".casefold()]
    if department: rows = [p for p in rows if p.department in department]
    if chair: rows = [p for p in rows if p.chair in chair]
    if topic: rows = [p for p in rows if set(topic) & set(p.topics)]
    if sort == "title": rows.sort(key=lambda p: p.title.casefold())
    elif sort == "chair": rows.sort(key=lambda p: p.chair.casefold())
    elif sort == "deadline": rows.sort(key=lambda p: p.deadline or date.max)
    elif sort == "newest": rows.sort(key=lambda p: p.first_seen_at, reverse=True)
    start = (page - 1) * page_size
    return {"items": rows[start:start + page_size], "total": len(rows), "page": page, "page_size": page_size,
            "last_updated_at": last_updated_at}


@router.get("/projects/{slug}", response_model=Project)
def project(slug: str):
    found = next((p for p in (persisted_projects() or PROJECTS) if p.slug == slug), None)
    if not found: raise HTTPException(404, "Project not found")
    return found


@router.get("/projects/{slug}/profile", response_model=ProjectProfileDetail)
def project_profile(slug: str) -> ProjectProfileDetail:
    with session_factory()() as session:
        row = session.execute(select(Listing, Chair, Department)
                              .join(Chair, Listing.chair_id == Chair.id)
                              .join(Department, Chair.department_id == Department.id)
                              .where(Listing.slug == slug)).one_or_none()
        if row is None:
            raise HTTPException(404, "Project not found")
        listing, chair, department = row
        artifact_url = listing.normalized.get("artifact_url")
        artifact = session.scalar(select(PDFArtifact).where(PDFArtifact.url == artifact_url)) if artifact_url else None
        if artifact is None or not artifact.content_hash:
            raise HTTPException(404, "No extracted profile for this project")
        extraction_id = _displayable_profiles(session, {artifact.content_hash}).get(artifact.content_hash)
        extraction = session.get(PDFProfileExtraction, extraction_id) if extraction_id else None
        if extraction is None or not extraction.document or not extraction.coverage:
            raise HTTPException(404, "No extracted profile for this project")
        try:
            document = DocumentExtraction.model_validate(extraction.document)
            coverage = PdfTextCoverage.model_validate(extraction.coverage)
            evidence_issues = [EvidenceIssue.model_validate(issue) for issue in extraction.evidence_issues]
        except ValidationError:
            raise HTTPException(404, "No valid extracted profile for this project") from None
        return ProjectProfileDetail(
            project=_project_from_listing(listing, chair, department, has_profile=True),
            document=document, coverage=coverage, evidence_issues=evidence_issues,
            review_flags=extraction.review_flags or [], extracted_at=extraction.extracted_at,
        )


@router.get("/departments")
def departments(): return [{"slug": key, "name": value} for key, value in DEPARTMENTS.items()]


@router.get("/chairs")
def chairs(): return [{"slug": a.slug, "name": a.name, "department": a.department, "source_state": a.state} for a in ALL_REGISTRY]


@router.get("/facets")
def facets():
    rows = persisted_projects() or PROJECTS
    return {"departments": {d: sum(p.department == d for p in rows) for d in DEPARTMENTS.values()},
            "topics": {t.value: sum(t in p.topics for p in rows) for t in Topic}}
