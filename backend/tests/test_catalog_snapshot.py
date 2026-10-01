from datetime import datetime, timezone
import json
import os
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from app import catalog_snapshot as snapshots, db, tasks
from app.db import Base, Chair, Department, Listing
from app.main import app
from app.schemas import Status


@pytest.fixture
def catalog(tmp_path, monkeypatch):
    database = create_engine(f"sqlite:///{tmp_path / 'catalog.db'}")
    monkeypatch.setattr(db, "_engine", database)
    Base.metadata.create_all(database)
    root = tmp_path / "snapshots"
    config = SimpleNamespace(catalog_storage_path=root, pinned_project_codes=("ps-003",),
                             organization_attribution_preview=False, public_url="http://localhost:3000")
    monkeypatch.setattr(snapshots, "settings", lambda: config)
    monkeypatch.setattr("app.api.settings", lambda: config)
    with db.session_factory()() as session:
        department = Department(slug="operations", name="Operations")
        session.add(department)
        session.flush()
        chair = Chair(slug="operations", name="Operations Management", department_id=department.id)
        session.add(chair)
        session.flush()
        for index in range(25):
            session.add(Listing(chair_id=chair.id, stable_source_key=str(index), slug=f"project-{index}",
                                reference_code=f"ps-{index:03}", title=f"Project {index}", content_hash="0" * 64,
                                normalized={"source_url": "https://example.org/", "opportunity_type": "project_study"},
                                first_seen_at=datetime(2026, 1, index + 1, tzinfo=timezone.utc),
                                status=Status.active))
        session.commit()
    return root


def test_snapshot_bootstrap_order_and_api_compatibility(catalog, monkeypatch):
    bootstrap = snapshots.publish_locked()
    assert bootstrap["total"] == 25 and len(bootstrap["items"]) == 20
    assert [p["slug"] for p in bootstrap["items"]][:3] == ["project-3", "project-24", "project-23"]
    monkeypatch.setattr("app.api.persisted_projects", lambda *args: pytest.fail("Visitor must not query the database"))
    client = TestClient(app)
    response = client.get("/api/v1/catalog")
    assert response.json() == bootstrap
    assert "s-maxage=300" in response.headers["cache-control"]
    index = client.get(f'/api/v1/catalog/{bootstrap["version"]}')
    assert len(index.json()["items"]) == 25
    assert "immutable" in index.headers["cache-control"]
    assert client.get(f'/api/v1/catalog/{bootstrap["version"]}', headers={"If-None-Match": index.headers["etag"]}).status_code == 304
    assert client.get("/api/v1/projects?page_size=20").json()["total"] == 25
    detail = client.get(f'/api/v1/projects/project-3/detail?version={bootstrap["version"]}')
    assert detail.json()["project"]["slug"] == "project-3"
    assert "immutable" in detail.headers["cache-control"]
    assert client.get("/api/v1/projects/project-3").json()["reference_code"] == "ps-003"
    assert client.get("/api/v1/projects/project-3/profile").status_code == 404


def test_publication_failure_preserves_previous_and_empty_catalog_is_valid(catalog, monkeypatch):
    first = snapshots.publish_locked()
    original = snapshots.construct
    monkeypatch.setattr(snapshots, "construct", lambda *args: (_ for _ in ()).throw(RuntimeError("Database failure")))
    with pytest.raises(RuntimeError):
        snapshots.publish_locked()
    assert snapshots.current_version() == first["version"]
    monkeypatch.setattr(snapshots, "construct", original)
    with db.session_factory()() as session:
        session.query(Listing).delete()
        session.commit()
    empty = snapshots.publish_locked()
    assert empty["total"] == 0 and empty["items"] == []
    assert json.loads((catalog / "current.json").read_text())["previous"] == first["version"]
    assert snapshots.read_data(first["version"], "catalog")["items"]


def test_atomic_pointer_is_not_replaced_when_write_fails(catalog, monkeypatch):
    first = snapshots.publish_locked()
    write = snapshots._write
    def fail_pointer(path, value):
        if path.name == ".current.tmp":
            raise OSError("disk full")
        write(path, value)
    monkeypatch.setattr(snapshots, "_write", fail_pointer)
    with pytest.raises(OSError):
        snapshots.publish_locked()
    assert snapshots.current_version() == first["version"]


def test_retention_preserves_current_and_previous(catalog):
    first = snapshots.publish_locked()
    os.utime(catalog / first["version"], (0, 0))
    second = snapshots.publish_locked()
    assert (catalog / first["version"]).exists()
    snapshots.publish_locked()
    assert not (catalog / first["version"]).exists()
    assert (catalog / second["version"]).exists()


def test_expired_missing_and_private_responses_are_uncached(catalog):
    client = TestClient(app)
    response = client.get("/api/v1/catalog")
    assert response.status_code == 503 and response.headers["cache-control"] == "no-store"
    snapshots.publish_locked()
    for path in ("/api/v1/catalog/expired", "/api/v1/projects/project-3/detail?version=expired"):
        response = client.get(path)
        assert response.status_code == 410 and response.headers["cache-control"] == "no-store"
    for path in ("/api/v1/bookmarks", "/api/v1/admin/source-health", "/api/v1/contact/config"):
        assert client.get(path).headers["cache-control"] == "private, no-store"


def test_pipeline_exclusion_skips_crawl_and_publication(monkeypatch):
    from contextlib import nullcontext
    monkeypatch.setattr(tasks, "pipeline_lock", lambda: nullcontext(False))
    monkeypatch.setattr(tasks, "run_live", lambda *args: pytest.fail("Must not crawl"))
    monkeypatch.setattr(tasks, "publish_locked", lambda *args: pytest.fail("Must not publish"))
    assert tasks.ingest_all.run()["status"] == "skipped"


def test_publication_reconciliation_retries_unacknowledged_generation(catalog, monkeypatch):
    bootstrap = snapshots.publish_locked()
    monkeypatch.setattr(tasks, "settings", snapshots.settings)
    queued = []
    monkeypatch.setattr(tasks.refresh_catalog, "delay", queued.append)
    result = tasks.reconcile_catalog.run()
    assert queued == [bootstrap["version"]] and result["acknowledged"] is None
    snapshots._write(catalog / "acknowledged.json", {"version": bootstrap["version"]})
    tasks.reconcile_catalog.run()
    assert len(queued) == 1


def test_refresh_prewarms_both_languages_before_acknowledging(catalog, monkeypatch):
    import httpx
    bootstrap = snapshots.publish_locked()
    config = snapshots.settings()
    config.catalog_web_url = "http://web:3000"
    config.catalog_revalidation_secret = "fixture-secret"
    monkeypatch.setattr(tasks, "settings", lambda: config)
    original_client = httpx.Client
    requests = []
    def handle(request):
        requests.append(request.url.path)
        return httpx.Response(200, text=bootstrap["version"])
    monkeypatch.setattr(tasks.httpx, "Client", lambda **kwargs: original_client(transport=httpx.MockTransport(handle), **kwargs))
    tasks.refresh_catalog.run(bootstrap["version"])
    assert requests == ["/api/internal/revalidate", "/en", "/de"]
    assert json.loads((catalog / "acknowledged.json").read_text())["version"] == bootstrap["version"]
    (catalog / "acknowledged.json").unlink()
    monkeypatch.setattr(tasks.httpx, "Client", lambda **kwargs: original_client(
        transport=httpx.MockTransport(lambda request: httpx.Response(503)), **kwargs))
    # Test the underlying task body; Celery's wrapper schedules retries in actual workers.
    with pytest.raises(Exception):
        tasks.refresh_catalog.__wrapped__(bootstrap["version"])
    assert not (catalog / "acknowledged.json").exists()


def test_failed_crawl_keeps_publication_but_partial_crawl_publishes(catalog, monkeypatch, tmp_path):
    from contextlib import nullcontext
    first = snapshots.publish_locked()
    config = snapshots.settings()
    config.artifact_storage_path = tmp_path / "artifacts"
    monkeypatch.setattr(tasks, "settings", lambda: config)
    monkeypatch.setattr(tasks, "pipeline_lock", lambda: nullcontext(True))
    monkeypatch.setattr(tasks, "_enrich_after_crawl", lambda outcome: outcome)
    monkeypatch.setattr(tasks.refresh_catalog, "delay", lambda version: None)
    monkeypatch.setattr(tasks, "run_live", lambda *args, **kwargs: {"results": [{"status": "failed"}]})
    tasks.ingest_all.run()
    assert snapshots.current_version() == first["version"]
    monkeypatch.setattr(tasks, "run_live", lambda *args, **kwargs: {"results": [{"status": "partial"}]})
    outcome = tasks.ingest_all.run()
    assert outcome["catalog_publication"]["status"] == "published"
    assert snapshots.current_version() != first["version"]
