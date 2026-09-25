"""Builders for schema-valid profile objects with every field unstated."""
from app.ingestion.project_profile import DateField, DocumentExtraction, ListField, ProjectProfile, TextField


def empty_offer(**overrides) -> ProjectProfile:
    values = {"source_pages": [1], "search_summary_en": "Summary.",
              "programming_performed": {"level": "unknown"}, "programming_required": {"level": "not_stated"},
              "work_location_mode": {"level": "unknown"}}
    for name, field in ProjectProfile.model_fields.items():
        if name in values:
            continue
        if issubclass(field.annotation, ListField):
            values[name] = {"stated": False, "items": []}
        elif issubclass(field.annotation, (TextField, DateField)):
            values[name] = {"stated": False, "value": None, "evidence": []}
    return ProjectProfile.model_validate(values).model_copy(update=overrides)


def document(*offers: ProjectProfile) -> DocumentExtraction:
    kind = "not_an_offer" if not offers else "offer" if len(offers) == 1 else "multi_offer"
    return DocumentExtraction(document_language="en", document_kind=kind, offers=list(offers))
