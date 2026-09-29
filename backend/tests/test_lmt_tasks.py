from types import SimpleNamespace

from sqlalchemy import create_engine

import app.db as db
import app.tasks as tasks
from app.db import Base, Chair, Department, Listing
from app.ingestion.profile_sources import html_description_hash
from app.schemas import Status


def test_scheduled_ingestion_extracts_only_current_lmt_html_descriptions(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'lmt-tasks.db'}")
    monkeypatch.setattr(db, "_engine", engine)
    Base.metadata.create_all(engine)
    url = "https://www.ce.cit.tum.de/en/lmt/student-thesis/"
    markdown = "# Robot learning\n\nStudents build a data collection tool."
    content_hash = html_description_hash(url, markdown)
    with db.session_factory()() as session:
        department = Department(slug="idp", name="Interdisciplinary Projects")
        session.add(department)
        session.flush()
        chair = Chair(department_id=department.id, slug=tasks.LMT_SLUG, name="Chair of Media Technology")
        session.add(chair)
        session.flush()
        session.add(Listing(chair_id=chair.id, stable_source_key="robot", slug="lmt-robot",
                            reference_code="idp-999", title="Robot learning", content_hash="a" * 64,
                            status=Status.active, normalized={"source_url": url, "artifact_url": None,
                                "description_markdown": markdown, "description_hash": content_hash}))
        session.commit()
    calls = []
    monkeypatch.setattr(tasks, "settings", lambda: SimpleNamespace(azure_openai_api_key="configured",
                                                       azure_openai_endpoint="https://example.invalid"))
    monkeypatch.setattr(tasks, "run_profile_backfill", lambda **kwargs: calls.append(kwargs) or {"ok": 1})
    monkeypatch.setattr(tasks, "run_live", lambda adapters: {
        "status": "completed", "results": [{"chair": tasks.LMT_SLUG, "status": "success"}]})
    assert tasks.ingest_all.run()["lmt_profiles"] == {"ok": 1}
    assert calls == [{"source_hashes": {content_hash}, "workers": 2}]

    monkeypatch.setattr(tasks, "run_live", lambda adapters, **kwargs: {
        "status": "completed_with_failures", "results": [{"chair": tasks.LMT_SLUG, "status": "failed"}]})
    assert "lmt_profiles" not in tasks.ingest_source.run(tasks.LMT_SLUG, force=True)
    assert len(calls) == 1
