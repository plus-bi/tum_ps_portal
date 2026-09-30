import json
from datetime import datetime, timezone

from app.ingestion.live import _project_source_types
from app.ingestion.run_summary import build_run_summary, write_run_summary
from app.ingestion.adapters import Candidate


def test_run_summary_counts_new_projects_and_sanitizes_errors():
    started = datetime(2026, 9, 30, 1, tzinfo=timezone.utc)
    finished = datetime(2026, 9, 30, 1, 3, tzinfo=timezone.utc)
    outcome = {
        "status": "completed_with_failures",
        "sources": 2,
        "results": [
            {
                "chair": "chair-a", "status": "partial", "crawl_run_id": "run-a",
                "created": 2, "updated": 1, "unchanged": 3,
                "new_projects": [
                    {"reference_code": "idp-101", "slug": "chair-a-one", "title": "One",
                     "source_types": ["pdf", "html"]},
                    {"reference_code": "idp-102", "slug": "chair-a-two", "title": "Two",
                     "source_types": ["doc", "png"]},
                ],
                "failures": [{"error": "TimeoutError: secret response body"}],
            },
            {"chair": "chair-b", "status": "failed", "crawl_run_id": "run-b",
             "error": "RuntimeError: private provider response"},
        ],
        "project_enrichment": {
            "pdf_markdown": {"digital_native": 2, "scanned": 1, "unknown": 1, "already_current": 4},
            "other_markdown": {"selected": 3, "converted": 2, "fallback_inline": 1, "failed": 0,
                                "skipped": {"unapproved_child_url": 1}, "kinds": {"html": 3}},
            "llm_profiles": {"pending": 3, "scheduled": 3, "ok": 2, "api_errors": 1,
                              "input_tokens": 42, "output_tokens": 18,
                              "provider_payload": "must not be copied"},
        },
    }

    summary = build_run_summary(outcome, trigger="scheduled_full", started_at=started,
                                finished_at=finished, run_id="report-id")

    assert summary["status"] == "completed_with_errors"
    assert summary["projects"]["new"] == 2
    assert summary["projects"]["updated"] == 1
    assert summary["projects"]["source_type_counts"] == {"doc": 1, "html": 1, "pdf": 1, "png": 1}
    assert summary["markdown"]["pdf"]["scanned"] == 1
    assert summary["markdown"]["other"]["converted"] == 2
    assert summary["llm_profiles"]["ok"] == 2
    assert len(summary["errors"]) == 4
    serialized = json.dumps(summary)
    assert "secret response body" not in serialized
    assert "private provider response" not in serialized
    assert "must not be copied" not in serialized


def test_report_writer_creates_timestamped_atomic_json(tmp_path):
    started = datetime(2026, 9, 30, 1, 0, tzinfo=timezone.utc)
    path = write_run_summary({"status": "completed", "results": []}, report_dir=tmp_path,
                             trigger="scheduled_full", started_at=started,
                             finished_at=started)

    report = json.loads(path.read_text())
    assert path.name.startswith("ingestion-2026-09-30T010000Z-")
    assert report["report_file"] == path.name
    assert report["status"] == "completed"
    assert list(tmp_path.glob("*.tmp")) == []


def test_new_project_source_types_cover_common_artifact_extensions():
    candidate = Candidate(
        stable_source_key="key", title="Project", source_url="https://example.test/project.docx",
        application_url=None, source_text="short listing text", pdf_url="https://example.test/brief.pdf",
    )

    assert _project_source_types(candidate, "https://example.test/list") == ["doc", "pdf"]
