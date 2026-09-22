from uuid import UUID, uuid4
import base64, hashlib, hmac, json, time
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from .auth import User, admin_user, current_user
from .schemas import SavedSearchCreate
from .config import settings
from .db import Chair, CrawlRun, Source, session_factory
from sqlalchemy import select

router = APIRouter(prefix="/api/v1")
_bookmarks: dict[str, set[str]] = {}
_searches: dict[str, dict[str, dict]] = {}

@router.get("/bookmarks")
def bookmarks(user: User = Depends(current_user)): return sorted(_bookmarks.get(user.id, set()))

@router.post("/bookmarks/{listing_id}", status_code=201)
def add_bookmark(listing_id: str, user: User = Depends(current_user)):
    _bookmarks.setdefault(user.id, set()).add(listing_id); return {"listing_id": listing_id}

@router.delete("/bookmarks/{listing_id}", status_code=204)
def delete_bookmark(listing_id: str, user: User = Depends(current_user)):
    _bookmarks.setdefault(user.id, set()).discard(listing_id); return Response(status_code=204)

@router.get("/saved-searches")
def saved_searches(user: User = Depends(current_user)): return list(_searches.get(user.id, {}).values())

@router.post("/saved-searches", status_code=201)
def create_saved_search(payload: SavedSearchCreate, user: User = Depends(current_user)):
    identifier = str(uuid4()); record = {"id": identifier, **payload.model_dump(mode="json"), "paused": False}
    _searches.setdefault(user.id, {})[identifier] = record; return record

@router.put("/saved-searches/{search_id}")
def update_saved_search(search_id: str, payload: SavedSearchCreate, user: User = Depends(current_user)):
    if search_id not in _searches.get(user.id, {}): raise HTTPException(404, "Saved search not found")
    record = {"id": search_id, **payload.model_dump(mode="json"), "paused": False}; _searches[user.id][search_id] = record; return record

@router.delete("/saved-searches/{search_id}", status_code=204)
def delete_saved_search(search_id: str, user: User = Depends(current_user)):
    _searches.get(user.id, {}).pop(search_id, None); return Response(status_code=204)

async def _verified_webhook(request: Request, secret: str | None) -> dict:
    if not secret: raise HTTPException(503, "Webhook secret is not configured")
    body = await request.body(); message_id = request.headers.get("svix-id", ""); timestamp = request.headers.get("svix-timestamp", "")
    if not message_id or not timestamp or abs(time.time() - int(timestamp)) > 300: raise HTTPException(400, "Invalid webhook timestamp")
    key = base64.b64decode(secret.removeprefix("whsec_")); signed = f"{message_id}.{timestamp}.".encode() + body
    expected = base64.b64encode(hmac.new(key, signed, hashlib.sha256).digest()).decode()
    signatures = [part.split(",", 1)[-1] for part in request.headers.get("svix-signature", "").split()]
    if not any(hmac.compare_digest(expected, candidate) for candidate in signatures): raise HTTPException(401, "Invalid webhook signature")
    return json.loads(body)

@router.post("/webhooks/clerk", status_code=202)
async def clerk_webhook(request: Request):
    event = await _verified_webhook(request, settings().clerk_webhook_secret)
    if event.get("type") == "user.deleted":
        user_id = event.get("data", {}).get("id", ""); _bookmarks.pop(user_id, None); _searches.pop(user_id, None)
    return {"accepted": True}

@router.post("/webhooks/resend", status_code=202)
async def resend_webhook(request: Request):
    await _verified_webhook(request, settings().resend_webhook_secret)
    return {"accepted": True}

@router.get("/admin/source-health")
def source_health(user: User = Depends(admin_user)):
    with session_factory()() as session:
        rows = session.execute(select(Source, Chair).join(Chair, Source.chair_id == Chair.id).order_by(Chair.name)).all()
        sources = []
        for source, chair in rows:
            latest = session.scalar(select(CrawlRun).where(CrawlRun.source_id == source.id)
                                    .order_by(CrawlRun.started_at.desc()).limit(1))
            sources.append({"id": source.id, "chair": chair.name, "chair_slug": chair.slug, "url": source.url,
                            "enabled": source.enabled, "consecutive_failures": source.consecutive_failures,
                            "last_status": latest.status if latest else None,
                            "last_started_at": latest.started_at if latest else None,
                            "last_error": latest.error if latest else None})
    failing = sum(row["consecutive_failures"] > 0 for row in sources)
    return {"sources": sources, "summary": {"healthy": len(sources) - failing, "failing": failing}}

@router.get("/admin/crawl-history")
def crawl_history(limit: int = 100, status: str | None = None, user: User = Depends(admin_user)):
    limit = min(max(limit, 1), 500)
    with session_factory()() as session:
        statement = select(CrawlRun, Source, Chair).join(Source, CrawlRun.source_id == Source.id).join(Chair, Source.chair_id == Chair.id)
        if status: statement = statement.where(CrawlRun.status == status)
        rows = session.execute(statement.order_by(CrawlRun.started_at.desc()).limit(limit)).all()
        return [{"id": run.id, "source_id": source.id, "chair": chair.name, "chair_slug": chair.slug,
                 "url": source.url, "status": run.status, "stats": run.stats, "error": run.error,
                 "started_at": run.started_at, "finished_at": run.finished_at}
                for run, source, chair in rows]

@router.get("/admin/reviews")
def reviews(user: User = Depends(admin_user)): return []

@router.post("/admin/sources/{source_id}/rescrape", status_code=202)
def rescrape(source_id: UUID, user: User = Depends(admin_user)):
    with session_factory()() as session:
        row = session.execute(select(Source, Chair).join(Chair, Source.chair_id == Chair.id)
                              .where(Source.id == source_id)).one_or_none()
        if row is None: raise HTTPException(404, "Source not found")
        _, chair = row
    from .tasks import app as celery_app
    task = celery_app.send_task("app.tasks.ingest_source", args=[chair.slug])
    return {"source_id": source_id, "chair_slug": chair.slug, "status": "queued", "task_id": task.id}

@router.post("/admin/projects/{listing_id}/archive")
def archive(listing_id: UUID, user: User = Depends(admin_user)): return {"listing_id": listing_id, "status": "archived"}

@router.post("/admin/projects/{listing_id}/restore")
def restore(listing_id: UUID, user: User = Depends(admin_user)): return {"listing_id": listing_id, "status": "active"}
