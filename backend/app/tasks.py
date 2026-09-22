from celery import Celery
from celery.schedules import crontab
from .config import settings
from .ingestion.service import ingest_department as run_department_ingestion

app = Celery("portal", broker=settings().redis_url)
app.conf.timezone = "Europe/Berlin"
app.conf.beat_schedule = {
    "daily-ingestion": {"task": "app.tasks.ingest_all", "schedule": crontab(hour=3, minute=0)},
    "daily-alerts": {"task": "app.tasks.deliver_alerts", "schedule": crontab(hour=7, minute=0)},
    "weekly-alerts": {"task": "app.tasks.deliver_alerts", "schedule": crontab(hour=7, minute=0, day_of_week=1)},
}


@app.task
def ingest_all():
    from .ingestion.registry import DEPARTMENTS
    return [run_department_ingestion(name) for name in DEPARTMENTS.values()]


@app.task(name="app.tasks.ingest_department")
def ingest_department(department: str):
    return run_department_ingestion(department)


@app.task
def deliver_alerts():
    return {"status": "scheduled"}
