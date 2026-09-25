from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.ingestion import llm_client
from app.ingestion.project_profile import SCHEMA_VERSION, DocumentExtraction, Evidence, ListField, SourcedValue
from profile_builders import document, empty_offer


class Session:
    def __init__(self, analysis):
        self.analysis = analysis

    def __enter__(self):
        return self

    def __exit__(self, *_):
        pass

    def scalar(self, _):
        return self.analysis


def use_analysis(monkeypatch, classification, pages):
    analysis = SimpleNamespace(classification=classification, classifier_version="reader-v1",
                               extracted_markdown_pages=pages)
    monkeypatch.setattr(llm_client, "session_factory", lambda: lambda: Session(analysis))


def validation_error() -> ValidationError:
    try:
        DocumentExtraction.model_validate({"document_language": "en", "document_kind": "offer", "offers": []})
    except ValidationError as error:
        return error
    raise AssertionError("expected a validation error")


class FakeResponses:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.instructions = []

    def parse(self, **kwargs):
        self.instructions.append(kwargs["instructions"])
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        usage = SimpleNamespace(input_tokens=100, output_tokens=50,
                                output_tokens_details=SimpleNamespace(reasoning_tokens=10))
        return SimpleNamespace(output_parsed=outcome, usage=usage)


def use_responses(monkeypatch, *outcomes) -> FakeResponses:
    responses = FakeResponses(outcomes)
    monkeypatch.setattr(llm_client, "_client", lambda: SimpleNamespace(responses=responses))
    return responses


def test_scanned_pdf_requires_ocr_before_model_extraction(monkeypatch):
    use_analysis(monkeypatch, "scanned", [""])
    monkeypatch.setattr(llm_client, "extract_project_profile", lambda *_a, **_k: pytest.fail("model must not be called"))

    with pytest.raises(ValueError, match="requires OCR"):
        llm_client.extract_project_profile_for_pdf("sample-hash")


def test_pdf_result_attaches_coverage_and_flags_unsupported_item(monkeypatch):
    offer = empty_offer(subjects=ListField[str](stated=True, items=[
        SourcedValue[str](value="Robotics", evidence=[Evidence(page=1, excerpt="Robotics")]),
    ]))
    use_analysis(monkeypatch, "mixed", ["Project text", ""])
    use_responses(monkeypatch, document(offer))

    result = llm_client.extract_project_profile_result_for_pdf("sample-hash")
    assert result.status == "ok" and result.attempts == 1
    assert result.coverage.status == "partial_text"
    assert result.coverage.blank_markdown_pages == [2]
    assert result.schema_version == SCHEMA_VERSION
    assert len(result.prompt_hash) == 64
    assert [(issue.offer_index, issue.field, issue.item_index, issue.reason) for issue in result.evidence_issues] == [
        (0, "subjects", 0, "quote_not_found"),
    ]


def test_validation_failure_is_retried_once_with_the_errors(monkeypatch):
    use_analysis(monkeypatch, "digital_native", ["Project text " * 40])
    responses = use_responses(monkeypatch, validation_error(), document(empty_offer()))

    result = llm_client.extract_project_profile_result_for_pdf("sample-hash")
    assert result.status == "ok" and result.attempts == 2
    assert (result.input_tokens, result.output_tokens, result.reasoning_tokens) == (100, 50, 10)
    assert responses.instructions[0] == llm_client.SYSTEM_PROMPT
    assert "does not match 0 offers" in responses.instructions[1]


def test_repeated_failure_is_recorded_without_document_text(monkeypatch):
    use_analysis(monkeypatch, "digital_native", ["Secret project text " * 40])
    use_responses(monkeypatch, validation_error(), None)

    result = llm_client.extract_project_profile_result_for_pdf("sample-hash")
    assert result.status == "failed" and result.document is None and result.attempts == 2
    assert result.errors == ["Model returned no parsed output (refusal or incomplete response)"]
    assert "Secret" not in result.model_dump_json()

    use_responses(monkeypatch, None, None)
    with pytest.raises(llm_client.ProfileExtractionError):
        llm_client.extract_project_profile_for_pdf("sample-hash")


def test_validation_messages_exclude_input_values():
    messages = llm_client._validation_messages(validation_error())
    assert messages and all("input" not in message.lower() for message in messages)


def test_short_documents_are_extracted_and_flagged(monkeypatch):
    use_analysis(monkeypatch, "digital_native", ["IDP: robotics. Mail a@tum.de"])
    use_responses(monkeypatch, document(empty_offer()))

    result = llm_client.extract_project_profile_result_for_pdf("sample-hash")
    assert result.status == "ok"
    assert result.coverage.short_text
