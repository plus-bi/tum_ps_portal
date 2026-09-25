"""Resumable batch extraction of LLM project profiles from stored PDF markdown.

    python -m app.ingestion.profile_backfill --dry-run      # count what a run would extract, no model calls
    python -m app.ingestion.profile_backfill --limit 20
    python -m app.ingestion.profile_backfill --recheck --dry-run   # citation checks only, no model calls

Each document costs one or two Azure OpenAI calls. A document is skipped when it already has an ok
row for the current schema, prompt, deployment and reasoning effort, so an interrupted run resumes.
Every attempt adds a row: a failure never replaces an earlier ok result. Rows and logs carry
document facts only in the `document` column; errors store validation messages or an error type.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from contextlib import contextmanager
from typing import Callable

from sqlalchemy import select, text

from ..config import settings
from ..db import Base, PDFAnalysis, PDFProfileExtraction, engine, session_factory
from . import llm_client
from .pdf_reader import render_for_llm
from .profile_evidence import check_profile_evidence
from .project_profile import SCHEMA_VERSION, DocumentExtraction, PdfTextCoverage, ProfileExtraction

logger = logging.getLogger(__name__)

LOCK_ID = 1414876497  # PostgreSQL advisory-lock key; distinct from the live-ingestion lock.
MAX_MARKDOWN_CHARS = 120_000  # llm_client.extract_project_profile rejects longer input

Extract = Callable[..., ProfileExtraction]


def log_event(level: int, event: str, **fields) -> None:
    logger.log(level, json.dumps({"event": event, **fields}, default=str, sort_keys=True))


@contextmanager
def backfill_lock():
    connection = engine().connect(); acquired = True
    try:
        if connection.dialect.name == "postgresql":
            acquired = bool(connection.scalar(text("SELECT pg_try_advisory_lock(:key)"), {"key": LOCK_ID}))
        yield acquired
    finally:
        if acquired and connection.dialect.name == "postgresql":
            connection.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": LOCK_ID})
        connection.close()


def current_version(effort: str) -> dict[str, str]:
    """Columns that identify the extractor; an ok row matching all of them makes a document done."""
    return {
        "schema_version": SCHEMA_VERSION,
        "prompt_version": llm_client.PROMPT_VERSION,
        "prompt_hash": hashlib.sha256(llm_client.SYSTEM_PROMPT.encode()).hexdigest(),
        "model_deployment": settings().azure_openai_deployment,
        "reasoning_effort": effort,
    }


def _done_hashes(version: dict[str, str]) -> set[str]:
    with session_factory()() as session:
        query = select(PDFProfileExtraction.content_hash).where(PDFProfileExtraction.status == "ok")
        for column, value in version.items():
            query = query.where(getattr(PDFProfileExtraction, column) == value)
        return set(session.scalars(query))


def _analyses() -> list[PDFAnalysis]:
    with session_factory()() as session:
        return list(session.scalars(select(PDFAnalysis).where(PDFAnalysis.extracted_markdown_pages.is_not(None))
                                    .order_by(PDFAnalysis.content_hash)))


def _skip_reason(analysis: PDFAnalysis) -> str | None:
    pages = analysis.extracted_markdown_pages
    if not isinstance(pages, list) or not pages:
        return "no_pages"
    if PdfTextCoverage.from_pages(analysis.classification, analysis.classifier_version, pages).status == "no_text":
        return "requires_ocr"
    if len(render_for_llm(pages)) > MAX_MARKDOWN_CHARS:
        return "too_long"
    return None


def review_flags(coverage: PdfTextCoverage, evidence_issues: list) -> list[str]:
    """Reasons a stored extraction should not be trusted without review. requires_ocr: no page has
    a readable text layer, so nothing the model returned can be checked against the source.
    unverified_citations: at least one quote was not found on its cited page (see evidence_issues)."""
    flags = []
    if coverage.status == "no_text":
        flags.append("requires_ocr")
    if evidence_issues:
        flags.append("unverified_citations")
    return flags


def _store(result: ProfileExtraction) -> None:
    values = result.model_dump(mode="json")
    with session_factory()() as session:
        session.add(PDFProfileExtraction(**values, review_flags=review_flags(result.coverage, result.evidence_issues)))
        session.commit()


def _store_error(analysis: PDFAnalysis, version: dict[str, str], error: Exception) -> None:
    """API or transport failure: the error type only, since provider messages may echo request content."""
    coverage = PdfTextCoverage.from_pages(analysis.classification, analysis.classifier_version,
                                          analysis.extracted_markdown_pages)
    with session_factory()() as session:
        session.add(PDFProfileExtraction(content_hash=analysis.content_hash, **version, status="failed", attempts=0,
                                         errors=[type(error).__name__], coverage=coverage.model_dump(mode="json"),
                                         evidence_issues=[], review_flags=review_flags(coverage, []), document=None))
        session.commit()


def run_profile_backfill(*, effort: str = "low", limit: int | None = None, workers: int = 2,
                         max_consecutive_errors: int = 5, dry_run: bool = False,
                         extract: Extract = llm_client.extract_project_profile_result_for_pages) -> dict:
    """Extract pending documents with bounded concurrency. Validation failures are model results
    and are stored as failed rows; the next run retries them. Stops early after
    max_consecutive_errors API errors in a row (e.g. bad credentials or exhausted quota)."""
    Base.metadata.create_all(engine())
    summary = {"pending": 0, "scheduled": 0, "ok": 0, "failed": 0, "api_errors": 0, "already_done": 0,
               "skipped": {}, "input_tokens": 0, "output_tokens": 0, "reasoning_tokens": 0,
               "stopped_early": False, "dry_run": dry_run}
    with backfill_lock() as acquired:
        if not acquired:
            log_event(logging.WARNING, "profile_backfill_skipped", reason="another run holds the lock")
            return {**summary, "locked": True}
        version = current_version(effort)
        done = _done_hashes(version)
        pending = []
        for analysis in _analyses():
            if analysis.content_hash in done:
                summary["already_done"] += 1
            elif reason := _skip_reason(analysis):
                summary["skipped"][reason] = summary["skipped"].get(reason, 0) + 1
            else:
                pending.append(analysis)
        summary["pending"] = len(pending)
        batch = pending[:limit] if limit is not None else pending
        summary["scheduled"] = len(batch)
        if dry_run or not batch:
            return summary

        consecutive_errors = 0
        queue = iter(batch)
        in_flight: dict[Future, PDFAnalysis] = {}
        with ThreadPoolExecutor(max_workers=workers) as executor:
            while True:
                # At most `workers` calls in flight, so an early stop leaves no queued model calls.
                while not summary["stopped_early"] and len(in_flight) < workers and (analysis := next(queue, None)):
                    in_flight[executor.submit(extract, analysis.content_hash, analysis.extracted_markdown_pages,
                                              analysis.classification, analysis.classifier_version,
                                              reasoning_effort=effort)] = analysis
                if not in_flight:
                    break
                finished, _ = wait(in_flight, return_when=FIRST_COMPLETED)
                future = finished.pop()
                analysis = in_flight.pop(future)
                try:
                    result = future.result()
                except Exception as error:
                    _store_error(analysis, version, error)
                    summary["api_errors"] += 1
                    consecutive_errors += 1
                    log_event(logging.WARNING, "profile_extraction_error", content_hash=analysis.content_hash,
                              error_type=type(error).__name__)
                    if consecutive_errors >= max_consecutive_errors and not summary["stopped_early"]:
                        summary["stopped_early"] = True
                        log_event(logging.ERROR, "profile_backfill_stopped", consecutive_errors=consecutive_errors)
                    continue
                consecutive_errors = 0
                _store(result)
                summary[result.status] += 1
                for key in ("input_tokens", "output_tokens", "reasoning_tokens"):
                    summary[key] += getattr(result, key)
                log_event(logging.INFO if result.status == "ok" else logging.WARNING, "profile_extraction_stored",
                          content_hash=result.content_hash, status=result.status, attempts=result.attempts,
                          offers=len(result.document.offers) if result.document else 0,
                          evidence_issues=len(result.evidence_issues), output_tokens=result.output_tokens)
    return summary


def recheck_evidence(*, dry_run: bool = False) -> dict:
    """Post-processing: recompute coverage, the citation checks and review_flags for every stored
    document from its current stored pages, so checker and reader fixes apply to earlier
    extractions without model calls. Only these derived columns change; the model output is left
    as extracted."""
    Base.metadata.create_all(engine())
    summary = {"documents": 0, "changed": 0, "issues_before": 0, "issues_after": 0, "missing_pages": 0,
               "flags": {}, "dry_run": dry_run}
    with session_factory()() as session:
        analyses = {analysis.content_hash: analysis for analysis in session.scalars(
            select(PDFAnalysis).where(PDFAnalysis.extracted_markdown_pages.is_not(None)))}
        pages = {content_hash: analysis.extracted_markdown_pages for content_hash, analysis in analyses.items()}
        for row in session.scalars(select(PDFProfileExtraction).where(PDFProfileExtraction.document.is_not(None))):
            if row.document is None:  # JSON null passes the SQL filter
                continue
            if not isinstance(pages.get(row.content_hash), list):
                summary["missing_pages"] += 1
                continue
            analysis = analyses[row.content_hash]
            coverage = PdfTextCoverage.from_pages(analysis.classification, analysis.classifier_version,
                                                  pages[row.content_hash])
            checked = check_profile_evidence(DocumentExtraction.model_validate(row.document), pages[row.content_hash])
            issues = [issue.model_dump(mode="json") for issue in checked]
            flags = review_flags(coverage, issues)
            summary["documents"] += 1
            summary["issues_before"] += len(row.evidence_issues)
            summary["issues_after"] += len(issues)
            for flag in flags:
                summary["flags"][flag] = summary["flags"].get(flag, 0) + 1
            values = {"coverage": coverage.model_dump(mode="json"), "evidence_issues": issues, "review_flags": flags}
            if any(getattr(row, column) != value for column, value in values.items()):
                summary["changed"] += 1
                for column, value in values.items():
                    setattr(row, column, value)
        if dry_run:
            session.rollback()
        else:
            session.commit()
    log_event(logging.INFO, "profile_evidence_rechecked", **summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--effort", choices=["low", "medium", "high"], default="low")
    parser.add_argument("--limit", type=int, help="extract at most this many pending documents")
    parser.add_argument("--workers", type=int, default=2, help="concurrent model calls")
    parser.add_argument("--max-consecutive-errors", type=int, default=5)
    parser.add_argument("--dry-run", action="store_true", help="report pending documents without model calls")
    parser.add_argument("--recheck", action="store_true",
                        help="re-run citation checks on stored extractions instead of extracting")
    args = parser.parse_args()
    if args.workers < 1 or (args.limit is not None and args.limit < 0) or args.max_consecutive_errors < 1:
        parser.error("--workers and --max-consecutive-errors must be positive; --limit cannot be negative")
    config = settings()
    if not (args.dry_run or args.recheck) and not (config.azure_openai_api_key and config.azure_openai_endpoint):
        parser.error("Azure OpenAI is not configured (AZURE_OPENAI_API_KEY / AZURE_OPENAI_ENDPOINT)")
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    if args.recheck:
        print(json.dumps(recheck_evidence(dry_run=args.dry_run), sort_keys=True))
        return
    print(json.dumps(run_profile_backfill(effort=args.effort, limit=args.limit, workers=args.workers,
                                          max_consecutive_errors=args.max_consecutive_errors,
                                          dry_run=args.dry_run), sort_keys=True))


if __name__ == "__main__":
    main()
