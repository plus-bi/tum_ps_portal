from app.ingestion.project_profile import (DegreeLevel, Evidence, ListField, ProgrammingSkill,
                                           ProgrammingWork, SourcedValue, TextField, WorkLocationMode, WorkMode)
from app.profile_filters import (FILTER_FIELDS, available_fields, normalize_working_languages, offer_for_listing,
                                 values_from_offer)
from profile_builders import document, empty_offer


def test_filter_values_keep_unstated_fields_unknown():
    values = values_from_offer(empty_offer())
    assert values.degree_level is None
    assert values.work_modes is None
    assert values.programming_performed == "unknown"
    assert values.programming_required == "not_stated"
    assert values.work_location_mode == "unknown"
    assert values.working_language is None


def test_filter_values_use_stated_evidenced_fields():
    evidence = [Evidence(page=1, excerpt="Students will develop software in English and German.")]
    offer = empty_offer(
        degree_level=ListField[DegreeLevel](stated=True, items=[SourcedValue(value=DegreeLevel.any, evidence=evidence)]),
        work_modes=ListField[WorkMode](stated=True, items=[SourcedValue(value=WorkMode.software_development, evidence=evidence)]),
        programming_performed=ProgrammingWork(level="central", evidence=evidence),
        programming_required=ProgrammingSkill(level="recommended", evidence=evidence),
        work_location_mode=WorkLocationMode(level="hybrid", evidence=evidence),
        working_language=ListField[str](stated=True, items=[SourcedValue(value="English and German", evidence=evidence)]),
    )
    values = values_from_offer(offer)
    assert values.degree_level == ["any"]
    assert values.work_modes == ["software_development"]
    assert values.programming_performed == "central"
    assert values.programming_required == "recommended"
    assert values.work_location_mode == "hybrid"
    assert values.working_language == ["en", "de"]


def test_working_language_normalization_keeps_other_stated_languages():
    assert normalize_working_languages(["Englisch", "Français"]) == ["en", "other"]
    assert normalize_working_languages(["English or French"]) == ["en", "other"]
    assert normalize_working_languages(None) is None


def test_multi_offer_filtering_requires_unique_exact_title():
    evidence = [Evidence(page=1, excerpt="Forecasting project")]
    first = empty_offer(title=TextField(stated=True, value="Forecasting project", evidence=evidence))
    second = empty_offer(title=TextField(stated=True, value="Market research", evidence=evidence))
    extracted = document(first, second)
    assert offer_for_listing(extracted, "Forecasting project") is first
    assert offer_for_listing(extracted, "Project opportunities") is None


def test_all_structured_profile_fields_are_available():
    assert available_fields() == sorted(FILTER_FIELDS)
    assert len(available_fields()) == 6
