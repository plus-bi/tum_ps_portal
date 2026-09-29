from celery import Celery
from celery.schedules import crontab
from sqlalchemy import select
from .config import settings
from .db import Chair, Listing, session_factory
from .ingestion.live import run_live
from .ingestion.profile_backfill import run_profile_backfill
from .ingestion.profile_sources import html_description_hash
from .ingestion.registry import ALL_BY_SLUG, ALL_REGISTRY, DEPARTMENTS
from .schemas import Status

app = Celery("portal", broker=settings().redis_url)
app.conf.timezone = "Europe/Berlin"
app.conf.enable_utc = True
app.conf.task_track_started = True
app.conf.worker_prefetch_multiplier = 1
app.conf.beat_schedule = {
    "daily-ingestion": {"task": "app.tasks.ingest_all", "schedule": crontab(hour=3, minute=0)},
    "daily-alerts": {"task": "app.tasks.deliver_alerts", "schedule": crontab(hour=7, minute=0)},
    "weekly-alerts": {"task": "app.tasks.deliver_alerts", "schedule": crontab(hour=7, minute=0, day_of_week=1)},
}

LMT_SLUG = "idp-chair-of-media-technology"


def _extract_lmt_after_crawl(outcome: dict) -> dict:
    lmt_crawled = any(row.get("chair") == LMT_SLUG and row.get("status") in
                      {"success", "not_modified", "partial"} for row in outcome.get("results", []))
    if not lmt_crawled:
        return outcome
    config = settings()
    if not config.azure_openai_api_key or not config.azure_openai_endpoint:
        outcome["lmt_profiles"] = {"status": "skipped", "reason": "Azure OpenAI not configured"}
        return outcome
    with session_factory()() as session:
        normalized_rows = session.execute(select(Listing.normalized).join(Chair, Listing.chair_id == Chair.id)
                                          .where(Chair.slug == LMT_SLUG, Listing.status == Status.active))
        hashes = set()
        for (normalized,) in normalized_rows:
            markdown = normalized.get("description_markdown")
            source_url = normalized.get("source_url")
            if (isinstance(markdown, str) and markdown.strip() and isinstance(source_url, str)
                    and normalized.get("description_hash") == html_description_hash(source_url, markdown)):
                hashes.add(normalized["description_hash"])
    if not hashes:
        outcome["lmt_profiles"] = {"status": "skipped", "reason": "no stored LMT descriptions"}
        return outcome
    try:
        outcome["lmt_profiles"] = run_profile_backfill(source_hashes=hashes, workers=2)
    except Exception as error:
        outcome["lmt_profiles"] = {"status": "failed", "error_type": type(error).__name__}
    return outcome


@app.task
def ingest_all():
    return _extract_lmt_after_crawl(run_live(ALL_REGISTRY))


@app.task(name="app.tasks.ingest_department")
def ingest_department(department: str):
    if department not in DEPARTMENTS.values(): raise ValueError(f"Unknown department: {department}")
    return _extract_lmt_after_crawl(run_live(adapter for adapter in ALL_REGISTRY if adapter.department == department))


@app.task(name="app.tasks.ingest_source")
def ingest_source(chair_slug: str, force: bool = False):
    if chair_slug not in ALL_BY_SLUG: raise ValueError(f"Unknown chair: {chair_slug}")
    return _extract_lmt_after_crawl(run_live((ALL_BY_SLUG[chair_slug],), force=force))


@app.task
def deliver_alerts():
    return {"status": "scheduled"}
