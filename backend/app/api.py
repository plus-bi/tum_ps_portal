from datetime import date
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import ValidationError
from .ingestion.registry import ALL_REGISTRY, DEPARTMENTS
from .ingestion.project_profile import DocumentExtraction, EvidenceIssue, PdfTextCoverage, SCHEMA_VERSION
from .profile_filters import ProfileFilterValues, available_fields, local_preview_enabled, offer_for_listing, values_from_offer
from .ingestion.organization_attribution import EXTRACTOR_VERSION, OrganizationMention
from .ingestion.profile_sources import description_source_url, html_description_hash
from .config import settings
from .schemas import Freshness, Project, ProjectDescriptionDetail, ProjectProfileDetail, Status, Topic
from .db import Chair, Department, Listing, OrganizationAttribution, PDFArtifact, PDFProfileExtraction, session_factory
from .ingestion.lifecycle import freshness
from sqlalchemy import inspect, select

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
                          *, has_profile: bool = False,
                          filter_values: ProfileFilterValues | None = None,
                          academic_units: list[OrganizationMention] | None = None,
                          project_partners: list[OrganizationMention] | None = None) -> Project:
    units = academic_units or []
    markdown = listing.normalized.get("description_markdown")
    source_url = description_source_url(listing.normalized)
    has_description = (isinstance(markdown, str) and bool(markdown.strip())
                       and isinstance(source_url, str) and listing.normalized.get("description_hash")
                       == html_description_hash(source_url, markdown))
    return Project(slug=listing.slug, reference_code=listing.reference_code,
                   title=listing.title, summary=listing.summary,
                   department=department.name,
                   chair=((units[0].canonical_name or units[0].name) if units else None)
                   if chair.slug == "informatics-idp-hub" else chair.name,
                   source_name=chair.name,
                   academic_units=units, project_partners=project_partners or [],
                   opportunity_type=listing.normalized.get("opportunity_type", "project_study"),
                   company=listing.normalized.get("company"), language=listing.normalized.get("language"),
                   topics=listing.normalized.get("topics", []), location=listing.normalized.get("location"),
                   application_url=listing.normalized.get("application_url"),
                   source_url=listing.normalized["source_url"],
                   artifact_url=listing.normalized.get("artifact_url"), has_profile=has_profile,
                   has_description=has_description,
                   filter_values=filter_values,
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


def _organization_rows(session, preview: bool) -> dict[tuple[UUID, str], OrganizationAttribution]:
    if not inspect(session.bind).has_table(OrganizationAttribution.__tablename__):
        return {}
    query = select(OrganizationAttribution).where(
        OrganizationAttribution.extractor_version == EXTRACTOR_VERSION,
        OrganizationAttribution.status.in_(("approved", "needs_review") if preview else ("approved",)),
    )
    return {(row.listing_id, row.content_hash): row for row in session.scalars(query)}


def _mentions(row: OrganizationAttribution | None, field: str) -> list[OrganizationMention]:
    if row is None:
        return []
    try:
        return [OrganizationMention.model_validate(value) for value in getattr(row, field)]
    except ValidationError:
        return []


def persisted_projects() -> list[Project]:
    try:
        with session_factory()() as session:
            rows = session.execute(select(Listing, Chair, Department)
                                   .join(Chair, Listing.chair_id == Chair.id)
                                   .join(Department, Chair.department_id == Department.id)).all()
            artifact_hashes = dict(session.execute(select(PDFArtifact.url, PDFArtifact.content_hash)).all())
            config = settings()
            organizations = _organization_rows(session, local_preview_enabled(config.organization_attribution_preview,
                                                                                config.public_url))
            profile_ids = _displayable_profiles(session)
            extractions = {row.id: row for row in session.scalars(select(PDFProfileExtraction).where(
                PDFProfileExtraction.id.in_(profile_ids.values())))} if profile_ids else {}
            documents = {}
            for content_hash, extraction_id in profile_ids.items():
                extraction = extractions.get(extraction_id)
                if extraction is None or not extraction.document or extraction.review_flags:
                    continue
                try:
                    documents[content_hash] = DocumentExtraction.model_validate(extraction.document)
                except ValidationError:
                    continue
            projects = []
            for listing, chair, department in rows:
                pdf_hash = artifact_hashes.get(listing.normalized.get("artifact_url"))
                html_hash = listing.normalized.get("description_hash")
                content_hash = html_hash if html_hash in profile_ids else pdf_hash
                document = documents.get(content_hash)
                offer = offer_for_listing(document, listing.title) if document else None
                projects.append(_project_from_listing(
                    listing, chair, department,
                    has_profile=content_hash in profile_ids,
                    filter_values=values_from_offer(offer) if offer else None,
                    academic_units=_mentions(organizations.get((listing.id, pdf_hash)), "academic_units"),
                    project_partners=_mentions(organizations.get((listing.id, pdf_hash)), "project_partners"),
                ))
            return projects
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
        needle = q.casefold(); rows = [p for p in rows if needle in f"{p.reference_code} {p.title} {p.summary or ''} {p.chair or ''} {p.source_name or ''}".casefold()]
    if department: rows = [p for p in rows if p.department in department]
    if chair: rows = [p for p in rows if p.chair in chair]
    if topic: rows = [p for p in rows if set(topic) & set(p.topics)]
    if sort == "title": rows.sort(key=lambda p: p.title.casefold())
    elif sort == "chair": rows.sort(key=lambda p: (p.chair is None, (p.chair or "").casefold()))
    elif sort == "deadline": rows.sort(key=lambda p: p.deadline or date.max)
    elif sort == "newest": rows.sort(key=lambda p: p.first_seen_at, reverse=True)
    start = (page - 1) * page_size
    return {"items": rows[start:start + page_size], "total": len(rows), "page": page, "page_size": page_size,
            "last_updated_at": last_updated_at,
            "published_profile_filters": available_fields()}


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
        html_hash = listing.normalized.get("description_hash")
        pdf_hash = artifact.content_hash if artifact else None
        available = _displayable_profiles(session, {value for value in (html_hash, pdf_hash) if value})
        content_hash = html_hash if html_hash in available else pdf_hash
        if not content_hash:
            raise HTTPException(404, "No extracted profile for this project")
        extraction_id = available.get(content_hash)
        extraction = session.get(PDFProfileExtraction, extraction_id) if extraction_id else None
        if extraction is None or not extraction.document or not extraction.coverage:
            raise HTTPException(404, "No extracted profile for this project")
        try:
            document = DocumentExtraction.model_validate(extraction.document)
            coverage = PdfTextCoverage.model_validate(extraction.coverage)
            evidence_issues = [EvidenceIssue.model_validate(issue) for issue in extraction.evidence_issues]
        except ValidationError:
            raise HTTPException(404, "No valid extracted profile for this project") from None
        config = settings()
        org_row = _organization_rows(session, local_preview_enabled(config.organization_attribution_preview,
                                                                      config.public_url)).get((listing.id, pdf_hash))
        return ProjectProfileDetail(
            project=_project_from_listing(listing, chair, department, has_profile=True,
                                          academic_units=_mentions(org_row, "academic_units"),
                                          project_partners=_mentions(org_row, "project_partners")),
            source_kind="html" if content_hash == html_hash else "pdf",
            document=document, coverage=coverage, evidence_issues=evidence_issues,
            review_flags=extraction.review_flags or [], extracted_at=extraction.extracted_at,
        )


@router.get("/projects/{slug}/description", response_model=ProjectDescriptionDetail)
def project_description(slug: str) -> ProjectDescriptionDetail:
    with session_factory()() as session:
        row = session.execute(select(Listing, Chair, Department)
                              .join(Chair, Listing.chair_id == Chair.id)
                              .join(Department, Chair.department_id == Department.id)
                              .where(Listing.slug == slug)).one_or_none()
        if row is None:
            raise HTTPException(404, "Project not found")
        listing, chair, department = row
        project = _project_from_listing(listing, chair, department)
        if not project.has_description:
            raise HTTPException(404, "No chair-page description for this project")
        return ProjectDescriptionDetail(project=project, markdown=listing.normalized["description_markdown"])


@router.get("/departments")
def departments(): return [{"slug": key, "name": value} for key, value in DEPARTMENTS.items()]


@router.get("/chairs")
def chairs(): return [{"slug": a.slug, "name": a.name, "department": a.department, "source_state": a.state} for a in ALL_REGISTRY]


@router.get("/facets")
def facets():
    rows = persisted_projects() or PROJECTS
    return {"departments": {d: sum(p.department == d for p in rows) for d in DEPARTMENTS.values()},
            "topics": {t.value: sum(t in p.topics for p in rows) for t in Topic}}
