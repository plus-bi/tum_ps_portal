"""Build and persist compact JSON summaries for live ingestion runs."""
from __future__ import annotations

import json
import os
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _error_type(value: Any) -> str:
    """Extract an exception class without retaining potentially sensitive messages."""
    if not isinstance(value, str) or not value:
        return "UnknownError"
    return value.split(":", 1)[0].strip() or "UnknownError"


def _stage_errors(stage: str, result: Any, chair: str | None = None) -> list[dict[str, Any]]:
    if not isinstance(result, dict):
        return []
    failures = result.get("failed", 0)
    api_errors = result.get("api_errors", 0)
    unknown = result.get("unknown", 0) if stage == "pdf_markdown" else 0
    events: list[dict[str, Any]] = []
    if result.get("status") == "failed":
        events.append({"stage": stage, "chair": chair, "error_type": result.get("error_type", "StageError"),
                       "count": 1})
    for label, count, error_type in (
        ("failed", failures, "ProcessingError"),
        ("api_errors", api_errors, "ProviderError"),
        ("unknown", unknown, "DocumentReadError"),
    ):
        if isinstance(count, int) and count > 0:
            events.append({"stage": stage, "chair": chair, "error_type": error_type, "count": count})
    if result.get("stopped_early"):
        events.append({"stage": stage, "chair": chair, "error_type": "StoppedEarly", "count": 1})
    return events


def build_run_summary(outcome: dict[str, Any], *, trigger: str, started_at: datetime,
                      finished_at: datetime, run_id: str | None = None) -> dict[str, Any]:
    """Select operational counts and project metadata; never serialize raw crawl payloads."""
    results = outcome.get("results", [])
    if not isinstance(results, list):
        results = []

    chairs: list[dict[str, Any]] = []
    projects: list[dict[str, Any]] = []
    source_type_counts: dict[str, int] = {}
    errors: list[dict[str, Any]] = []
    crawl_counts = {status: 0 for status in ("success", "not_modified", "partial", "failed", "skipped")}
    project_counts = {key: 0 for key in ("new", "updated", "unchanged")}

    for row in results:
        if not isinstance(row, dict):
            continue
        chair = row.get("chair")
        status = row.get("status", "unknown")
        if status in crawl_counts:
            crawl_counts[status] += 1
        new_projects = row.get("new_projects", [])
        if not isinstance(new_projects, list):
            new_projects = []
        safe_projects = []
        for project in new_projects:
            if not isinstance(project, dict):
                continue
            source_types = project.get("source_types", [])
            if not isinstance(source_types, list):
                source_types = []
            source_types = sorted({value for value in source_types if isinstance(value, str)})
            for source_type in source_types:
                source_type_counts[source_type] = source_type_counts.get(source_type, 0) + 1
            safe_project = {
                "chair": chair,
                "reference_code": project.get("reference_code"),
                "slug": project.get("slug"),
                "title": project.get("title"),
                "source_types": source_types,
            }
            projects.append(safe_project)
            safe_projects.append(safe_project)

        created = row.get("created", len(safe_projects))
        updated = row.get("updated", 0)
        unchanged = row.get("unchanged", 0)
        for key, value in (("new", created), ("updated", updated), ("unchanged", unchanged)):
            if isinstance(value, int):
                project_counts[key] += value
        child_failures = row.get("failures", [])
        if not isinstance(child_failures, list):
            child_failures = []
        for failure in child_failures:
            error = failure.get("error") if isinstance(failure, dict) else None
            errors.append({"stage": "crawl_child", "chair": chair,
                           "crawl_run_id": row.get("crawl_run_id"),
                           "error_type": _error_type(error), "count": 1})
        if status == "failed":
            errors.append({"stage": "crawl", "chair": chair, "crawl_run_id": row.get("crawl_run_id"),
                           "error_type": _error_type(row.get("error")), "count": 1})
        chairs.append({
            "chair": chair,
            "status": status,
            "crawl_run_id": row.get("crawl_run_id"),
            "created": created if isinstance(created, int) else 0,
            "updated": updated if isinstance(updated, int) else 0,
            "unchanged": unchanged if isinstance(unchanged, int) else 0,
            "new_projects": safe_projects,
            "child_failures": len(child_failures),
        })

    enrichment = outcome.get("project_enrichment", {})
    if not isinstance(enrichment, dict):
        enrichment = {}
    pdf_markdown = enrichment.get("pdf_markdown", {})
    other_markdown = enrichment.get("other_markdown", {})
    llm_profiles = enrichment.get("llm_profiles", {})
    for stage, value in (("pdf_markdown", pdf_markdown), ("other_markdown", other_markdown),
                         ("llm_profiles", llm_profiles)):
        errors.extend(_stage_errors(stage, value))
    if enrichment.get("status") == "failed":
        errors.append({"stage": "project_enrichment", "error_type": enrichment.get("error_type", "StageError"),
                       "count": 1})

    if outcome.get("run_error_type"):
        errors.append({"stage": "crawl", "error_type": outcome["run_error_type"], "count": 1})
    if not errors and outcome.get("status") in {"completed_with_failures", "failed"}:
        # Covers failures reported by a future crawler version without leaking its message.
        errors.append({"stage": "crawl", "error_type": "ReportedFailure", "count": 1})

    status = "completed_with_errors" if errors else outcome.get("status", "completed")
    duration = max(0.0, (finished_at - started_at).total_seconds())
    return {
        "schema_version": 1,
        "run_id": run_id or str(uuid.uuid4()),
        "trigger": trigger,
        "started_at": started_at.astimezone(timezone.utc).isoformat(),
        "finished_at": finished_at.astimezone(timezone.utc).isoformat(),
        "duration_seconds": round(duration, 3),
        "status": status,
        "crawl": {
            "sources": outcome.get("sources", len(results)),
            "counts_by_status": crawl_counts,
        },
        "projects": {**project_counts, "source_type_counts": source_type_counts, "items": projects},
        "chairs": chairs,
        "markdown": {
            "pdf": {key: value for key, value in pdf_markdown.items()
                    if key in {"digital_native", "scanned", "mixed", "unknown", "already_current"}}
            if isinstance(pdf_markdown, dict) else {},
            "other": {key: value for key, value in other_markdown.items()
                      if key in {"selected", "converted", "fallback_inline", "failed", "skipped", "kinds"}}
            if isinstance(other_markdown, dict) else {},
        },
        "llm_profiles": {key: value for key, value in llm_profiles.items()
                         if key in {"pending", "scheduled", "ok", "failed", "api_errors", "already_done",
                                    "skipped", "input_tokens", "output_tokens", "reasoning_tokens",
                                    "stopped_early", "status", "locked"}}
        if isinstance(llm_profiles, dict) else {},
        "errors": errors,
    }


def write_run_summary(outcome: dict[str, Any], *, report_dir: Path, trigger: str,
                      started_at: datetime, finished_at: datetime) -> Path:
    """Atomically persist one private, timestamped JSON report for a task invocation."""
    report_dir.mkdir(parents=True, exist_ok=True)
    run_id = str(uuid.uuid4())
    summary = build_run_summary(outcome, trigger=trigger, started_at=started_at,
                                finished_at=finished_at, run_id=run_id)
    timestamp = started_at.astimezone(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")
    destination = report_dir / f"ingestion-{timestamp}-{run_id[:8]}.json"
    summary["report_file"] = destination.name
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=report_dir,
                                         prefix=".ingestion-", suffix=".tmp", delete=False) as handle:
            temporary_path = Path(handle.name)
            os.chmod(temporary_path, 0o600)
            json.dump(summary, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, destination)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()
    return destination
