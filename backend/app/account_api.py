from uuid import UUID, uuid4
import base64, hashlib, hmac, json, time
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from .auth import User, admin_user, current_user
from .schemas import SavedSearchCreate
from .config import settings

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
def source_health(user: User = Depends(admin_user)): return {"sources": [], "summary": {"healthy": 0, "failing": 0}}

@router.get("/admin/crawl-history")
def crawl_history(user: User = Depends(admin_user)): return []

@router.get("/admin/reviews")
def reviews(user: User = Depends(admin_user)): return []

@router.post("/admin/sources/{source_id}/rescrape", status_code=202)
def rescrape(source_id: UUID, user: User = Depends(admin_user)): return {"source_id": source_id, "status": "queued"}

@router.post("/admin/projects/{listing_id}/archive")
def archive(listing_id: UUID, user: User = Depends(admin_user)): return {"listing_id": listing_id, "status": "archived"}

@router.post("/admin/projects/{listing_id}/restore")
def restore(listing_id: UUID, user: User = Depends(admin_user)): return {"listing_id": listing_id, "status": "active"}
