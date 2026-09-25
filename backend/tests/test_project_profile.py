import pytest
from pydantic import ValidationError

from app.ingestion.project_profile import (Contact, DateField, DocumentExtraction, Evidence, ListField, PdfTextCoverage,
                                           ProgrammingSkill, ProgrammingWork, SourcedValue, TextField,
                                           WorkLocationMode)
from profile_builders import empty_offer

EVIDENCE = [Evidence(page=1, excerpt="Data analysis")]


def test_stated_fields_require_values_and_evidence():
    with pytest.raises(ValidationError):
        TextField(stated=True)
    with pytest.raises(ValidationError):
        ListField[str](stated=True)
    with pytest.raises(ValidationError):
        SourcedValue[str](value="Data analysis", evidence=[])

    assert TextField(stated=True, value="Data analysis", evidence=EVIDENCE).value == "Data analysis"
    item = SourcedValue[str](value="Data analysis", evidence=EVIDENCE)
    assert ListField[str](stated=True, items=[item]).items[0].value == "Data analysis"


def test_unstated_fields_reject_claims_and_invalid_evidence():
    with pytest.raises(ValidationError):
        TextField(stated=False, value="Data analysis")
    with pytest.raises(ValidationError):
        ListField[str](stated=False, items=[SourcedValue[str](value="Data analysis", evidence=EVIDENCE)])
    with pytest.raises(ValidationError):
        Evidence(page=0, excerpt="Data analysis")
    with pytest.raises(ValidationError):
        Evidence(page=1, excerpt="")


@pytest.mark.parametrize("model, unknown, known", [
    (ProgrammingWork, "unknown", "none"),
    (ProgrammingSkill, "not_stated", "required"),
    (WorkLocationMode, "unknown", "remote"),
])
def test_assessments_need_evidence_except_when_unknown(model, unknown, known):
    assert model(level=unknown).evidence == []
    assert model(level=known, evidence=EVIDENCE).level == known
    with pytest.raises(ValidationError):
        model(level=known)
    with pytest.raises(ValidationError):
        model(level=unknown, evidence=EVIDENCE)


def test_date_normalization_is_optional_but_restricted_to_supported_forms():
    stated = dict(stated=True, value="1st of October 2024", evidence=[Evidence(page=1, excerpt="1st of October 2024")])
    for normalized in ("2024-10-01", "2024-10", "WiSe2026/27", "SoSe2027", "asap", "flexible", None):
        assert DateField(**stated, normalized=normalized).normalized == normalized
    with pytest.raises(ValidationError):
        DateField(**stated, normalized="October 2024")
    with pytest.raises(ValidationError):
        DateField(stated=False, normalized="asap")


def test_document_kind_must_match_offer_count():
    offer = empty_offer()
    assert len(DocumentExtraction(document_language="en", document_kind="multi_offer", offers=[offer, offer]).offers) == 2
    for kind, offers in [("offer", []), ("offer", [offer, offer]), ("multi_offer", [offer]),
                         ("not_an_offer", [offer]), ("unknown", [offer])]:
        with pytest.raises(ValidationError):
            DocumentExtraction(document_language="en", document_kind=kind, offers=offers)


def test_offer_needs_source_pages_and_summary():
    values = empty_offer().model_dump()
    with pytest.raises(ValidationError):
        type(empty_offer()).model_validate({**values, "source_pages": []})
    with pytest.raises(ValidationError):
        type(empty_offer()).model_validate({**values, "search_summary_en": ""})


def test_pdf_text_coverage_tracks_blank_pages_without_claiming_content_absent():
    coverage = PdfTextCoverage.from_pages("mixed", "reader-v1", ["Project brief", ""])
    assert coverage.status == "partial_text"
    assert coverage.blank_markdown_pages == [2]
    assert coverage.page_count == 2
    assert coverage.short_text


def test_pdf_text_coverage_does_not_flag_ordinary_offers_as_short():
    coverage = PdfTextCoverage.from_pages("digital_native", "reader-v1", ["x" * 400])
    assert coverage.text_chars == 400
    assert not coverage.short_text


def test_contact_needs_a_name_or_an_email():
    assert Contact(name=None, email="a@b.de").email == "a@b.de"
    with pytest.raises(ValidationError):
        Contact(name=" ", email=None)
