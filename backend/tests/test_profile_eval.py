import re

import pytest

from app.ingestion import profile_eval
from app.ingestion.project_profile import (Contact, DegreeLevel, DocumentExtraction, Evidence, ListField, PdfTextCoverage,
                                           ProfileExtraction, ProjectType, SourcedValue, TextField, WorkMode)
from profile_builders import document, empty_offer

EVIDENCE = [Evidence(page=1, excerpt="quote")]


def contacts(*emails: str) -> ListField:
    return ListField[Contact](stated=True, items=[
        SourcedValue[Contact](value=Contact(name=None, email=email), evidence=EVIDENCE) for email in emails])


def text(value: str) -> TextField:
    return TextField(stated=True, value=value, evidence=EVIDENCE)


def items(*values) -> ListField:
    return ListField(stated=True, items=[SourcedValue(value=value, evidence=EVIDENCE) for value in values])


def result(doc: DocumentExtraction | None, **extra) -> ProfileExtraction:
    coverage = PdfTextCoverage.from_pages("digital_native", "reader-v1", ["x" * 400])
    return ProfileExtraction(content_hash="h", schema_version="v", prompt_version="p", prompt_hash="x",
                             model_deployment="m", reasoning_effort="low", coverage=coverage,
                             status="ok" if doc else "failed", attempts=1, document=doc, **extra)


def test_label_file_uses_schema_values():
    allowed = {
        "project_types": {member.value for member in ProjectType},
        "degree_level": {member.value for member in DegreeLevel},
        "work_modes_required": {member.value for member in WorkMode},
        "work_modes_forbidden": {member.value for member in WorkMode},
        "programming_performed": {"none", "some", "central", "unknown"},
        "programming_required": {"required", "recommended", "not_stated"},
        "work_location_mode": {"on_site", "hybrid", "remote", "unknown"},
    }
    for label in profile_eval.load_labels().values():
        assert set(label["document_kind"]) <= {"offer", "multi_offer", "not_an_offer", "unknown"}
        for offer in label["offers"]:
            offer = {**label.get("offer_defaults", {}), **offer}
            assert offer["source_pages"]
            for key, values in allowed.items():
                for value in offer.get(key, []):
                    assert set(value if isinstance(value, list) else [value]) <= values, (key, value)
            for prerequisite in offer.get("prerequisites", []):
                assert prerequisite["strength"] in {"required", "recommended"}
            for date in offer.get("start_date_normalized", []):
                assert date is None or re.fullmatch(r"\d{4}(-\d{2}(-\d{2})?)?|asap|flexible", date)


def test_synthetic_label_keys_appear_in_their_pages():
    for label in profile_eval.load_labels().values():
        if "pages" not in label:
            continue
        page_text = " ".join(label["pages"]).lower()
        for offer in label["offers"]:
            keys = offer["contact_emails"] + [p["key"] for p in offer.get("prerequisites", [])]
            keys += offer.get("forbidden_keys", [])
            assert all(key in page_text for key in keys)
            assert any(key in page_text for key in offer["title_keys"])


def test_offers_on_one_page_are_matched_by_title_and_contact():
    labels = [{"source_pages": [1], "title_keys": ["heat"], "contact_emails": ["anna"]},
              {"source_pages": [1], "title_keys": ["interview"], "contact_emails": ["ben"]}]
    offers = [empty_offer(title=text("Interview study")), empty_offer(title=text("Heat flow"))]
    assert profile_eval.match_offers(labels, offers) == [(0, 1), (1, 0)]


def test_offer_with_no_overlap_or_match_stays_unmatched():
    labels = [{"source_pages": [1], "title_keys": ["heat"]}]
    assert profile_eval.match_offers(labels, [empty_offer(source_pages=[2])]) == []


def test_offer_checks_cover_only_labeled_fields():
    offer = empty_offer(
        source_pages=[1, 2],
        contacts=contacts("Anna.Beispiel@tum.de"),
        project_types=items(ProjectType.idp),
        prerequisites_required=items("Python"),
        prerequisites_recommended=items("Numerical methods", "SQL"),
        deliverables=items("Report", "App"),
        work_modes=items(WorkMode.modeling_simulation, WorkMode.software_development),
    )
    label = {"source_pages": [1, 2], "contact_emails": ["anna.beispiel@tum.de"], "project_types": [["idp"]],
             "programming_performed": ["unknown"],
             "prerequisites": [{"key": "python", "strength": "required"}, {"key": "sql", "strength": "required"},
                               {"key": "git", "strength": "required"}],
             "deliverables_required": [["report"], ["prototype"]], "work_modes_required": ["modeling_simulation"],
             "work_modes_forbidden": ["software_development"], "forbidden_keys": ["numerical"]}
    assert profile_eval.score_offer(label, offer) == {
        "boundary_exact": True, "contact": True, "programming_performed": True, "project_types": True,
        "work_modes_recall": 1.0, "work_modes_no_forbidden": False,
        "prerequisite_recall": pytest.approx(2 / 3), "prerequisite_strength": pytest.approx(1 / 3),
        "deliverables_supported": False, "deliverable_recall": 0.5, "no_leakage": False,
    }


def test_empty_contact_label_expects_no_contact():
    assert profile_eval.score_offer({"source_pages": [1], "contact_emails": []}, empty_offer())["contact"]


def test_optional_keys_are_allowed_but_not_required_deliverables():
    offer = empty_offer(deliverables=items("Presentation of results", "Optional publication"))
    label = {"source_pages": [1], "deliverables_required": [["presentation"]], "deliverable_keys": ["visuali"]}
    assert profile_eval.score_offer(label, offer) == {
        "boundary_exact": True, "deliverables_supported": False, "deliverable_recall": 1.0}
    label = {"source_pages": [1], "deliverables_required": []}
    assert profile_eval.score_offer(label, empty_offer()) == {"boundary_exact": True, "deliverables_supported": True}


def test_empty_working_language_label_expects_no_invented_language():
    label = {"source_pages": [1], "working_language": []}
    assert profile_eval.score_offer(label, empty_offer())["working_language"]
    assert not profile_eval.score_offer(label, empty_offer(working_language=items("English")))["working_language"]


def test_several_labeled_contacts_must_all_be_extracted():
    label = {"source_pages": [1], "contact_emails": ["a@x.de", "b@y.de"]}
    one = profile_eval.score_offer(label, empty_offer(contacts=contacts("a@x.de")))
    both = profile_eval.score_offer(label, empty_offer(contacts=contacts("a@x.de", "b@y.de")))
    assert (one["contact"], one["contacts_complete"]) == (True, False)
    assert both["contacts_complete"]


def test_document_score_uses_defaults_and_counts_unmatched_offers():
    label = {"document_kind": ["multi_offer"], "offer_defaults": {"programming_required": ["not_stated"]},
             "offers": [{"source_pages": [1]}, {"source_pages": [2]}]}
    doc = document(empty_offer(source_pages=[1]), empty_offer(source_pages=[3]))
    scored = profile_eval.score_document(label, result(doc, input_tokens=10))
    assert scored["checks"] == {"document_kind": True, "offer_count": True, "offer_recall": 0.5}
    assert scored["offers"] == [{"label_index": 0, "offer_index": 0, "boundary_exact": True,
                                 "programming_required": True}]
    assert scored["unmatched_offers"] == 1 and scored["input_tokens"] == 10


def test_failed_extraction_is_scored_without_checks():
    scored = profile_eval.score_document({"document_kind": ["offer"], "offers": []}, result(None))
    assert scored["status"] == "failed" and scored["checks"] == {}
    summary = profile_eval.summarize({"h": scored})
    assert summary["failed"] == 1 and summary["checks"] == {}


def test_not_an_offer_scores_full_recall_when_no_offers_returned():
    scored = profile_eval.score_document({"document_kind": ["not_an_offer"], "offers": []}, result(document()))
    assert scored["checks"] == {"document_kind": True, "offer_count": True, "offer_recall": 1.0}
