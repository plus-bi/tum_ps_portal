import logging

import pytest
from sqlalchemy import create_engine, select

import app.db as db
from app.db import Base, PDFAnalysis, PDFProfileExtraction
from app.ingestion import profile_backfill
from app.ingestion.project_profile import PdfTextCoverage, ProfileExtraction
from profile_builders import document, empty_offer

SECRET_PAGE = "Secret project text about robotics. " * 20


@pytest.fixture
def database(tmp_path, monkeypatch):
    test_engine = create_engine(f"sqlite:///{tmp_path / 'profiles.db'}")
    monkeypatch.setattr(db, "_engine", test_engine)
    Base.metadata.create_all(test_engine)
    return test_engine


def add_analysis(content_hash, pages, classification="digital_native"):
    with db.session_factory()() as session:
        session.add(PDFAnalysis(content_hash=content_hash, classification=classification,
                                classifier_version="reader-v1", extracted_markdown_pages=pages))
        session.commit()


def rows(content_hash=None):
    with db.session_factory()() as session:
        query = select(PDFProfileExtraction).order_by(PDFProfileExtraction.extracted_at)
        if content_hash:
            query = query.where(PDFProfileExtraction.content_hash == content_hash)
        return list(session.scalars(query))


class FakeExtract:
    """Stands in for llm_client.extract_project_profile_result_for_pages; outcomes keyed by hash."""

    def __init__(self, **outcomes):
        self.outcomes = outcomes
        self.calls = []

    def __call__(self, content_hash, pages, classification, classifier_version, *, reasoning_effort):
        self.calls.append(content_hash)
        outcome = self.outcomes.get(content_hash, "ok")
        if isinstance(outcome, Exception):
            raise outcome
        version = profile_backfill.current_version(reasoning_effort)
        coverage = PdfTextCoverage.from_pages(classification, classifier_version, pages)
        if outcome == "failed":
            return ProfileExtraction(content_hash=content_hash, **version, coverage=coverage, status="failed",
                                     attempts=2, errors=["offers: bad"], input_tokens=5)
        return ProfileExtraction(content_hash=content_hash, **version, coverage=coverage, status="ok", attempts=1,
                                 document=document(empty_offer()), input_tokens=100, output_tokens=50)


def test_ok_result_is_stored_and_not_extracted_again(database):
    add_analysis("a" * 64, [SECRET_PAGE])
    extract = FakeExtract()

    summary = profile_backfill.run_profile_backfill(extract=extract)
    assert (summary["ok"], summary["input_tokens"], summary["output_tokens"]) == (1, 100, 50)
    [row] = rows()
    assert row.status == "ok" and row.document["document_kind"] == "offer"
    assert row.coverage["status"] == "text_on_all_pages"

    summary = profile_backfill.run_profile_backfill(extract=extract)
    assert (summary["scheduled"], summary["already_done"]) == (0, 1)
    assert extract.calls == ["a" * 64]


def test_other_effort_is_not_treated_as_done(database):
    add_analysis("a" * 64, [SECRET_PAGE])
    profile_backfill.run_profile_backfill(extract=FakeExtract())

    assert profile_backfill.run_profile_backfill(effort="medium", dry_run=True)["pending"] == 1


def test_failure_is_added_without_replacing_an_earlier_ok_result(database, monkeypatch):
    add_analysis("a" * 64, [SECRET_PAGE])
    profile_backfill.run_profile_backfill(extract=FakeExtract())
    first_version = profile_backfill.llm_client.PROMPT_VERSION
    monkeypatch.setattr(profile_backfill.llm_client, "PROMPT_VERSION", "next-prompt")  # forces a re-extraction

    summary = profile_backfill.run_profile_backfill(extract=FakeExtract(**{"a" * 64: "failed"}))
    assert summary["failed"] == 1
    assert [(row.status, row.prompt_version) for row in rows()] == [("ok", first_version), ("failed", "next-prompt")]
    assert rows()[0].document is not None


def test_validation_failure_is_retried_on_the_next_run(database):
    add_analysis("a" * 64, [SECRET_PAGE])
    profile_backfill.run_profile_backfill(extract=FakeExtract(**{"a" * 64: "failed"}))

    summary = profile_backfill.run_profile_backfill(extract=FakeExtract())
    assert summary["ok"] == 1
    assert [row.status for row in rows()] == ["failed", "ok"]


def test_api_error_is_recorded_by_type_without_stopping_the_batch(database, caplog):
    add_analysis("a" * 64, [SECRET_PAGE])
    add_analysis("b" * 64, [SECRET_PAGE])
    extract = FakeExtract(**{"a" * 64: TimeoutError(f"request echoed {SECRET_PAGE}")})

    with caplog.at_level(logging.INFO):
        summary = profile_backfill.run_profile_backfill(extract=extract, workers=1)
    assert (summary["api_errors"], summary["ok"], summary["stopped_early"]) == (1, 1, False)
    [failed] = rows("a" * 64)
    assert failed.status == "failed" and failed.errors == ["TimeoutError"] and failed.document is None
    assert "Secret" not in caplog.text


def test_consecutive_api_errors_stop_the_run(database):
    for letter in "abcd":
        add_analysis(letter * 64, [SECRET_PAGE])
    extract = FakeExtract(**{letter * 64: ConnectionError() for letter in "abcd"})

    summary = profile_backfill.run_profile_backfill(extract=extract, workers=1, max_consecutive_errors=2)
    assert summary["stopped_early"] and summary["api_errors"] == 2
    assert len(extract.calls) == 2


def test_scanned_and_oversized_documents_are_skipped_without_model_calls(database):
    add_analysis("a" * 64, ["", ""], classification="scanned")
    add_analysis("b" * 64, ["x" * 130_000])
    add_analysis("c" * 64, None)
    extract = FakeExtract()

    summary = profile_backfill.run_profile_backfill(extract=extract)
    assert summary["skipped"] == {"no_pages": 1, "requires_ocr": 1, "too_long": 1}
    assert extract.calls == [] and rows() == []


def test_limit_and_dry_run(database):
    for letter in "abc":
        add_analysis(letter * 64, [SECRET_PAGE])
    extract = FakeExtract()

    assert profile_backfill.run_profile_backfill(extract=extract, dry_run=True)["scheduled"] == 3
    assert extract.calls == []
    summary = profile_backfill.run_profile_backfill(extract=extract, limit=2)
    assert (summary["pending"], summary["scheduled"], summary["ok"]) == (3, 2, 2)
