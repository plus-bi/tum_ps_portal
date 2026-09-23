from celery import Celery
from celery.schedules import crontab
from .config import settings
from .ingestion.live import run_live
from .ingestion.registry import ALL_BY_SLUG, ALL_REGISTRY, DEPARTMENTS

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


@app.task
def ingest_all():
    return run_live(ALL_REGISTRY)


@app.task(name="app.tasks.ingest_department")
def ingest_department(department: str):
    if department not in DEPARTMENTS.values(): raise ValueError(f"Unknown department: {department}")
    return run_live(adapter for adapter in ALL_REGISTRY if adapter.department == department)


@app.task(name="app.tasks.ingest_source")
def ingest_source(chair_slug: str):
    if chair_slug not in ALL_BY_SLUG: raise ValueError(f"Unknown chair: {chair_slug}")
    return run_live((ALL_BY_SLUG[chair_slug],))


@app.task
def deliver_alerts():
    return {"status": "scheduled"}
