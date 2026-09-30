from contextlib import nullcontext
from types import SimpleNamespace

from sqlalchemy import create_engine

import app.db as db
import app.tasks as tasks
from app.db import Base, Chair, Department, Listing, PDFArtifact
from app.ingestion.profile_sources import html_description_hash
from app.schemas import Status


def test_active_profile_source_hashes_cover_markdown_and_pdf_artifacts_by_chair(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'profile-hashes.db'}")
    monkeypatch.setattr(db, "_engine", engine)
    Base.metadata.create_all(engine)
    markdown_url = "https://chair-a.example/projects/robotics"
    markdown = "# Robotics IDP\n\nBuild and test a robot controller."
    markdown_hash = html_description_hash(markdown_url, markdown)
    pdf_url = "https://chair-a.example/projects/robotics.pdf"

    with db.session_factory()() as session:
        department = Department(slug="idp", name="Interdisciplinary Projects")
        session.add(department)
        session.flush()
        chair_a = Chair(department_id=department.id, slug="chair-a", name="Chair A")
        chair_b = Chair(department_id=department.id, slug="chair-b", name="Chair B")
        session.add_all([chair_a, chair_b])
        session.flush()
        session.add_all([
            Listing(chair_id=chair_a.id, stable_source_key="markdown", slug="chair-a-markdown",
                    reference_code="idp-991", title="Robotics IDP", summary="A project description.",
                    content_hash="listing-a", status=Status.active,
                    normalized={"source_url": markdown_url, "description_markdown": markdown,
                                "description_hash": markdown_hash}),
            Listing(chair_id=chair_a.id, stable_source_key="pdf", slug="chair-a-pdf",
                    reference_code="idp-992", title="PDF project", summary="A project description.",
                    content_hash="listing-pdf", status=Status.active,
                    normalized={"source_url": markdown_url, "artifact_url": pdf_url}),
            Listing(chair_id=chair_b.id, stable_source_key="markdown", slug="chair-b-markdown",
                    reference_code="idp-993", title="Other project", summary="A project description.",
                    content_hash="listing-b", status=Status.active,
                    normalized={"source_url": markdown_url, "description_markdown": markdown,
                                "description_hash": markdown_hash}),
            Listing(chair_id=chair_a.id, stable_source_key="archived", slug="chair-a-archived",
                    reference_code="idp-994", title="Archived project", summary="A project description.",
                    content_hash="listing-archived", status=Status.archived,
                    normalized={"source_url": markdown_url, "description_markdown": markdown,
                                "description_hash": markdown_hash}),
            PDFArtifact(url=pdf_url, content_hash="pdf-content-hash"),
        ])
        session.commit()

    assert tasks._active_profile_source_hashes({"chair-a"}) == {markdown_hash, "pdf-content-hash"}


def test_nightly_task_converts_all_crawled_chairs_before_llm_profiles(tmp_path, monkeypatch):
    order = []
    chairs = {"chair-a", "chair-b"}
    outcome = {"status": "completed_with_failures", "results": [
        {"chair": "chair-a", "status": "success", "crawl_run_id": "run-a"},
        {"chair": "chair-b", "status": "partial", "crawl_run_id": "run-b"},
        {"chair": "chair-c", "status": "failed", "crawl_run_id": "run-c"},
    ]}

    def fake_live(adapters, *, force=False):
        order.append("crawl")
        assert adapters is tasks.ALL_REGISTRY
        assert force is False
        return outcome

    async def fake_markdown(*, chair_slugs):
        order.append("other_markdown")
        assert chair_slugs == chairs
        return {"converted": 2, "failed": 0}

    def fake_profiles(*, source_hashes, workers):
        order.append("llm_profiles")
        assert source_hashes == {"hash-a", "hash-b"}
        assert workers == 2
        return {"pending": 2, "ok": 2}

    def fake_source_hashes(slugs):
        assert slugs == chairs
        return {"hash-a", "hash-b"}

    monkeypatch.setattr(tasks, "run_live", fake_live)
    monkeypatch.setattr(tasks, "classify_stored_pdfs", lambda: order.append("pdf_markdown") or {"digital_native": 1})
    monkeypatch.setattr(tasks, "run_description_backfill", fake_markdown)
    monkeypatch.setattr(tasks, "_active_profile_source_hashes", fake_source_hashes)
    monkeypatch.setattr(tasks, "run_profile_backfill", fake_profiles)
    monkeypatch.setattr(tasks, "project_enrichment_lock", lambda: nullcontext(True))
    monkeypatch.setattr(tasks, "settings", lambda: SimpleNamespace(
        azure_openai_api_key="configured", azure_openai_endpoint="https://example.invalid",
        artifact_storage_path=tmp_path))

    result = tasks.ingest_all.run()

    assert order == ["crawl", "pdf_markdown", "other_markdown", "llm_profiles"]
    assert result["project_enrichment"]["chairs"] == ["chair-a", "chair-b"]
    assert result["project_enrichment"]["status"] == "completed"
    assert (tmp_path / "reports").is_dir()
    assert result["report_path"].endswith(".json")


def test_profile_extraction_waits_for_markdown_conversion_and_skips_without_credentials(monkeypatch):
    order = []

    def fail_if_called(**_kwargs):
        raise AssertionError("LLM backfill should not run without credentials")

    async def fake_markdown(*, chair_slugs):
        order.append(("other_markdown", chair_slugs))
        return {"converted": 0}

    monkeypatch.setattr(tasks, "classify_stored_pdfs", lambda: order.append(("pdf_markdown",)) or {})
    monkeypatch.setattr(tasks, "run_description_backfill", fake_markdown)
    monkeypatch.setattr(tasks, "run_profile_backfill", fail_if_called)
    monkeypatch.setattr(tasks, "project_enrichment_lock", lambda: nullcontext(True))
    monkeypatch.setattr(tasks, "settings", lambda: SimpleNamespace(
        azure_openai_api_key=None, azure_openai_endpoint=None))

    result = tasks._enrich_after_crawl({"results": [{"chair": "chair-a", "status": "success"}]})

    assert order == [("pdf_markdown",), ("other_markdown", {"chair-a"})]
    assert result["project_enrichment"]["llm_profiles"]["status"] == "skipped"


def test_failed_crawls_do_not_run_document_or_llm_enrichment(monkeypatch):
    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("enrichment should wait for a successful, not-modified, or partial crawl")

    monkeypatch.setattr(tasks, "classify_stored_pdfs", fail_if_called)
    monkeypatch.setattr(tasks, "run_description_backfill", fail_if_called)
    monkeypatch.setattr(tasks, "run_profile_backfill", fail_if_called)

    result = tasks._enrich_after_crawl({"results": [{"chair": "chair-a", "status": "failed"}]})

    assert result["project_enrichment"]["status"] == "skipped"


def test_overlapping_enrichment_run_is_skipped(monkeypatch):
    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("a concurrent enrichment owns the lock")

    monkeypatch.setattr(tasks, "project_enrichment_lock", lambda: nullcontext(False))
    monkeypatch.setattr(tasks, "classify_stored_pdfs", fail_if_called)
    monkeypatch.setattr(tasks, "run_description_backfill", fail_if_called)
    monkeypatch.setattr(tasks, "run_profile_backfill", fail_if_called)

    result = tasks._enrich_after_crawl({"results": [{"chair": "chair-a", "status": "success"}]})

    assert result["project_enrichment"]["status"] == "skipped"
    assert result["project_enrichment"]["reason"] == "another enrichment is running"
