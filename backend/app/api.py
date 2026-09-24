from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Query
from .ingestion.registry import ALL_REGISTRY, DEPARTMENTS
from .schemas import Freshness, Project, Status, Topic
from .db import Chair, Department, Listing, session_factory
from .ingestion.lifecycle import freshness
from sqlalchemy import select

router = APIRouter(prefix="/api/v1")

# Demo data keeps the UI useful before the first database-backed crawl.
PROJECTS = [Project(
    slug="example-project-study",
    title="Example Project Study",
    summary="Run the ingestion worker to replace this development record with source-grounded listings.",
    department="Operations and Technology", chair="Operations Management",
    topics=[Topic.operations_supply_chain], language="English", source_url="https://www.mgt.tum.de/",
    freshness=Freshness.undated,
)]

def persisted_projects() -> list[Project]:
    try:
        with session_factory()() as session:
            rows = session.execute(select(Listing, Chair, Department).join(Chair, Listing.chair_id == Chair.id).join(Department, Chair.department_id == Department.id)).all()
            return [Project(slug=listing.slug, title=listing.title, summary=listing.summary,
                            department=department.name, chair=chair.name,
                            opportunity_type=listing.normalized.get("opportunity_type", "project_study"),
                            company=listing.normalized.get("company"), language=listing.normalized.get("language"),
                            topics=listing.normalized.get("topics", []), location=listing.normalized.get("location"),
                            application_url=listing.normalized.get("application_url"), source_url=listing.normalized["source_url"],
                            artifact_url=listing.normalized.get("artifact_url"),
                            published_at=listing.published_at, first_seen_at=listing.first_seen_at,
                            last_seen_at=listing.last_seen_at, status=listing.status,
                            freshness=freshness(listing.published_at))
                    for listing, chair, department in rows]
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
        needle = q.casefold(); rows = [p for p in rows if needle in f"{p.title} {p.summary or ''} {p.chair}".casefold()]
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


@router.get("/departments")
def departments(): return [{"slug": key, "name": value} for key, value in DEPARTMENTS.items()]


@router.get("/chairs")
def chairs(): return [{"slug": a.slug, "name": a.name, "department": a.department, "source_state": a.state} for a in ALL_REGISTRY]


@router.get("/facets")
def facets():
    rows = persisted_projects() or PROJECTS
    return {"departments": {d: sum(p.department == d for p in rows) for d in DEPARTMENTS.values()},
            "topics": {t.value: sum(t in p.topics for p in rows) for t in Topic}}
