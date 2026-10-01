"""Publish deterministic synthetic records in the isolated staging database only."""
from datetime import datetime, timedelta, timezone
import json
import os

from app.catalog_snapshot import pipeline_lock, publish_locked
from app.db import Base, Chair, Department, Listing, engine, session_factory
from app.ingestion.profile_sources import html_description_hash
from app.schemas import Status

if not os.environ.get("DATABASE_URL", "").endswith("/fixture.db"):
    raise RuntimeError("This fixture command requires the isolated fixture.db")
from app.config import settings
settings().catalog_storage_path.mkdir(parents=True, exist_ok=True)
settings().catalog_storage_path.chmod(0o777)
Base.metadata.create_all(engine())
with session_factory()() as session:
    if not session.query(Listing).count():
        department = Department(slug="operations", name="Operations and Technology")
        session.add(department)
        session.flush()
        chair = Chair(slug="operations", name="Management Accounting", department_id=department.id)
        session.add(chair)
        session.flush()
        now = datetime.now(timezone.utc)
        for index in range(420):
            url = f"https://example.org/projects/{index}"
            markdown = f"# Research project {index}\n\nSynthetic project description for testing."
            session.add(Listing(chair_id=chair.id, slug=f"fixture-project-{index}",
                stable_source_key=str(index), reference_code=f"ps-{index:03}",
                title=f"Research project {index}", summary="Analyze data and develop a research prototype with a project team.",
                normalized={"source_url": url, "opportunity_type": "idp" if index % 2 else "project_study",
                    "description_markdown": markdown, "description_hash": html_description_hash(url, markdown)},
                content_hash="0" * 64, status=Status.active, first_seen_at=now - timedelta(days=index), last_seen_at=now))
        session.commit()
with pipeline_lock() as acquired:
    if not acquired:
        raise RuntimeError("Pipeline already running")
    bootstrap = publish_locked()
print(json.dumps({"version": bootstrap["version"], "total": bootstrap["total"]}))
