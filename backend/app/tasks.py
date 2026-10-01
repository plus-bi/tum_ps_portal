import asyncio
import json
import logging
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Callable

from celery import Celery
from celery.schedules import crontab
from sqlalchemy import select, text

from .config import settings
from .catalog_snapshot import pipeline_lock, publish_locked, current_version, read_data
import httpx
from pathlib import Path
from .db import Chair, Listing, PDFArtifact, engine, session_factory
from .ingestion.description_backfill import run_description_backfill
from .ingestion.live import run_live
from .ingestion.pdf_analysis import classify_stored_pdfs
from .ingestion.pdf_backfill import is_pdf_url
from .ingestion.profile_backfill import run_profile_backfill
from .ingestion.profile_sources import description_source_url, html_description_hash
from .ingestion.registry import ALL_BY_SLUG, ALL_REGISTRY, DEPARTMENTS
from .ingestion.run_summary import write_run_summary
from .schemas import Status

logger = logging.getLogger(__name__)
ENRICHMENT_LOCK_ID = 1414876498

app = Celery("portal", broker=settings().redis_url)
app.conf.timezone = "Europe/Berlin"
app.conf.enable_utc = True
app.conf.task_track_started = True
app.conf.worker_prefetch_multiplier = 1
app.conf.beat_schedule = {
    "catalog-reconciliation": {"task": "app.tasks.reconcile_catalog", "schedule": 300.0},
    "daily-ingestion": {"task": "app.tasks.ingest_all", "schedule": crontab(hour=3, minute=0)},
    "daily-alerts": {"task": "app.tasks.deliver_alerts", "schedule": crontab(hour=7, minute=0)},
    "weekly-alerts": {"task": "app.tasks.deliver_alerts", "schedule": crontab(hour=7, minute=0, day_of_week=1)},
}


@contextmanager
def project_enrichment_lock():
    """Prevent concurrent crawls from converting or profiling the same pending documents."""
    connection = engine().connect()
    acquired = True
    try:
        if connection.dialect.name == "postgresql":
            acquired = bool(connection.scalar(text("SELECT pg_try_advisory_lock(:key)"),
                                              {"key": ENRICHMENT_LOCK_ID}))
        yield acquired
    finally:
        if acquired and connection.dialect.name == "postgresql":
            connection.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": ENRICHMENT_LOCK_ID})
        connection.close()


def _active_profile_source_hashes(chair_slugs: set[str]) -> set[str]:
    """Hashes of Markdown and stored PDFs linked to active listings in the crawled chairs."""
    with session_factory()() as session:
        statement = (select(Listing.normalized)
                     .join(Chair, Listing.chair_id == Chair.id)
                     .where(Chair.slug.in_(chair_slugs), Listing.status == Status.active))
        description_hashes: set[str] = set()
        pdf_urls: set[str] = set()
        for (normalized,) in session.execute(statement):
            if not isinstance(normalized, dict):
                continue
            markdown = normalized.get("description_markdown")
            source_url = description_source_url(normalized)
            if (isinstance(markdown, str) and markdown.strip() and isinstance(source_url, str)
                    and normalized.get("description_hash") == html_description_hash(source_url, markdown)):
                description_hashes.add(normalized["description_hash"])
            for field in ("artifact_url", "pdf_url"):
                url = normalized.get(field)
                if isinstance(url, str) and is_pdf_url(url):
                    pdf_urls.add(url)
        hashes = set(description_hashes)
        if pdf_urls:
            hashes.update(value for value in session.scalars(select(PDFArtifact.content_hash).where(
                PDFArtifact.url.in_(pdf_urls), PDFArtifact.content_hash.is_not(None))) if value)
        return hashes


def _enrich_after_crawl(outcome: dict) -> dict:
    """Convert crawled source documents to Markdown, then extract pending LLM profiles."""
    completed_chairs = {row["chair"] for row in outcome.get("results", [])
                        if row.get("chair") and row.get("status") in {"success", "not_modified", "partial"}}
    if not completed_chairs:
        outcome["project_enrichment"] = {"status": "skipped", "reason": "no chair crawl completed"}
        return outcome
    with project_enrichment_lock() as acquired:
        if not acquired:
            outcome["project_enrichment"] = {"status": "skipped", "reason": "another enrichment is running"}
            return outcome
        return _run_project_enrichment(outcome, completed_chairs)


def _run_project_enrichment(outcome: dict, completed_chairs: set[str]) -> dict:
    stages: dict[str, object] = {}
    crawl_run_ids = [row["crawl_run_id"] for row in outcome.get("results", [])
                     if row.get("crawl_run_id")]

    def run_stage(name: str, callback: Callable[[], object]) -> None:
        try:
            stages[name] = callback()
        except Exception as error:
            stages[name] = {"status": "failed", "error_type": type(error).__name__}
            logger.error(json.dumps({"event": "project_enrichment_stage_failed", "stage": name,
                                     "crawl_run_ids": crawl_run_ids, "error_type": type(error).__name__}))

    # Keep these sequential so profile extraction sees Markdown persisted by both converters.
    run_stage("pdf_markdown", classify_stored_pdfs)
    run_stage("other_markdown", lambda: asyncio.run(
        run_description_backfill(chair_slugs=completed_chairs)))

    config = settings()
    if not config.azure_openai_api_key or not config.azure_openai_endpoint:
        stages["llm_profiles"] = {"status": "skipped", "reason": "Azure OpenAI not configured"}
    else:
        try:
            source_hashes = _active_profile_source_hashes(completed_chairs)
            stages["llm_profiles"] = run_profile_backfill(source_hashes=source_hashes, workers=2)
        except Exception as error:
            stages["llm_profiles"] = {"status": "failed", "error_type": type(error).__name__}
            logger.error(json.dumps({"event": "project_enrichment_stage_failed", "stage": "llm_profiles",
                                     "crawl_run_ids": crawl_run_ids, "error_type": type(error).__name__}))

    has_errors = any(
        isinstance(value, dict) and (
            value.get("status") == "failed"
            or value.get("failed", 0) > 0
            or value.get("api_errors", 0) > 0
            or value.get("unknown", 0) > 0
            or value.get("stopped_early", False)
        )
        for value in stages.values()
    )
    status = "completed_with_errors" if has_errors else "completed"
    outcome["project_enrichment"] = {"status": status, "chairs": sorted(completed_chairs), **stages}
    return outcome


def _run_ingestion_locked(adapters, *, trigger: str, force: bool = False) -> dict:
    """Run crawl and enrichment, then persist a metadata-only JSON run report."""
    selected = tuple(adapters)
    started_at = datetime.now(timezone.utc)
    try:
        outcome = run_live(selected, force=force)
    except Exception as error:
        outcome = {
            "status": "failed",
            "sources": len(selected),
            "failed": len(selected),
            "results": [],
            "run_error_type": type(error).__name__,
        }
        logger.error(json.dumps({"event": "ingestion_run_failed", "trigger": trigger,
                                 "error_type": type(error).__name__}))
    try:
        outcome = _enrich_after_crawl(outcome)
    except Exception as error:
        outcome["project_enrichment"] = {"status": "failed", "error_type": type(error).__name__}
        logger.error(json.dumps({"event": "project_enrichment_failed", "trigger": trigger,
                                 "error_type": type(error).__name__}))
    if any(row.get("status") in {"success", "not_modified", "partial"} for row in outcome.get("results", [])):
        try:
            bootstrap = publish_locked()
            outcome["catalog_publication"] = {"status": "published", "version": bootstrap["version"]}
        except Exception as error:
            outcome["catalog_publication"] = {"status": "failed", "error_type": type(error).__name__}
            logger.error(json.dumps({"event": "catalog_publication_failed", "error_type": type(error).__name__}))
    if outcome.get("catalog_publication", {}).get("status") == "published":
        try:
            refresh_catalog.delay(outcome["catalog_publication"]["version"])
        except Exception as error:
            logger.error(json.dumps({"event": "catalog_notification_failed", "error_type": type(error).__name__}))
    finished_at = datetime.now(timezone.utc)
    try:
        report_path = write_run_summary(
            outcome,
            report_dir=settings().artifact_storage_path / "reports",
            trigger=trigger,
            started_at=started_at,
            finished_at=finished_at,
        )
        outcome["report_path"] = str(report_path)
        logger.info(json.dumps({"event": "ingestion_run_summary_written", "trigger": trigger,
                               "report_file": report_path.name}))
    except Exception as error:
        # A report disk error must be visible without masking the crawl result.
        outcome["report_error_type"] = type(error).__name__
        logger.error(json.dumps({"event": "ingestion_run_summary_failed", "trigger": trigger,
                                 "error_type": type(error).__name__}))
    return outcome


def _run_ingestion(adapters, *, trigger: str, force: bool = False) -> dict:
    with pipeline_lock() as acquired:
        if not acquired:
            return {"status": "skipped", "reason": "another catalog pipeline is running", "results": []}
        return _run_ingestion_locked(adapters, trigger=trigger, force=force)


@app.task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_backoff_max=60,
          retry_jitter=True, max_retries=8)
def refresh_catalog(self, version: str):
    config = settings()
    if not config.catalog_revalidation_secret:
        raise RuntimeError("Catalog revalidation secret is not configured")
    # A superseded notification refreshes the latest publication instead.
    version = current_version()
    with httpx.Client(timeout=45) as client:
        response = client.post(f"{config.catalog_web_url}/api/internal/revalidate",
                               headers={"Authorization": f"Bearer {config.catalog_revalidation_secret}"},
                               json={"version": version})
        response.raise_for_status()
        for locale in ("en", "de"):
            response = client.get(f"{config.catalog_web_url}/{locale}")
            response.raise_for_status()
            if version not in response.text:
                raise RuntimeError("Catalog prewarm did not render the published version")
    from .catalog_snapshot import _write
    _write(config.catalog_storage_path / "acknowledged.json", {"version": version})
    logger.info(json.dumps({"event": "catalog_refresh_acknowledged", "version": version}))
    return {"version": version}


@app.task
def reconcile_catalog():
    config = settings()
    try:
        bootstrap = read_data(name="bootstrap")
    except Exception as error:
        logger.error(json.dumps({"event": "catalog_unavailable", "error_type": type(error).__name__}))
        return {"status": "unavailable"}
    age = (datetime.now(timezone.utc) - datetime.fromisoformat(bootstrap["published_at"])).total_seconds()
    if age > 36 * 3600:
        logger.error(json.dumps({"event": "catalog_publication_stale", "version": bootstrap["version"], "age_seconds": int(age)}))
    try:
        acknowledged = json.loads((config.catalog_storage_path / "acknowledged.json").read_text())["version"]
    except (OSError, ValueError, KeyError):
        acknowledged = None
    if acknowledged != bootstrap["version"]:
        if age > 300:
            logger.error(json.dumps({"event": "catalog_refresh_overdue", "version": bootstrap["version"]}))
        refresh_catalog.delay(bootstrap["version"])
    return {"version": bootstrap["version"], "acknowledged": acknowledged}


@app.task
def ingest_all():
    return _run_ingestion(ALL_REGISTRY, trigger="scheduled_full")


@app.task(name="app.tasks.ingest_department")
def ingest_department(department: str):
    if department not in DEPARTMENTS.values():
        raise ValueError(f"Unknown department: {department}")
    adapters = (adapter for adapter in ALL_REGISTRY if adapter.department == department)
    return _run_ingestion(adapters, trigger=f"department:{department}")


@app.task(name="app.tasks.ingest_source")
def ingest_source(chair_slug: str, force: bool = False):
    if chair_slug not in ALL_BY_SLUG:
        raise ValueError(f"Unknown chair: {chair_slug}")
    return _run_ingestion((ALL_BY_SLUG[chair_slug],), trigger=f"chair:{chair_slug}", force=force)


@app.task
def deliver_alerts():
    return {"status": "scheduled"}
