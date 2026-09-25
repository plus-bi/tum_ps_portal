"""Pydantic schema for LLM-extracted structured project profiles.

See ../../../docs/pdf-project-profile-v3-plan.md for the current design rationale.
"""
from __future__ import annotations

import re
from enum import Enum
from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, Field, field_validator, model_validator

SCHEMA_VERSION = "project-profile-v3.1"
SHORT_TEXT_CHARS = 300

T = TypeVar("T")


class Evidence(BaseModel):
    page: int = Field(ge=1, description="1-indexed source PDF page")
    excerpt: str = Field(min_length=1)

    @field_validator("excerpt")
    @classmethod
    def excerpt_has_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Evidence excerpt cannot be blank")
        return value


class TextField(BaseModel):
    stated: bool
    value: str | None = None
    evidence: list[Evidence] = Field(default_factory=list)

    @model_validator(mode="after")
    def check_stated_value(self):
        if self.stated and (not self.value or not self.value.strip() or not self.evidence):
            raise ValueError("A stated text field needs a value and evidence")
        if not self.stated and (self.value is not None or self.evidence):
            raise ValueError("An unstated text field cannot have a value or evidence")
        return self


NORMALIZED_DATE = re.compile(r"\d{4}(-\d{2}(-\d{2})?)?|(WiSe\d{4}/\d{2}|SoSe\d{4})|asap|flexible")


class DateField(TextField):
    normalized: str | None = Field(
        default=None,
        description='Derived from value: "YYYY-MM-DD", "YYYY-MM", "YYYY", "WiSe2026/27", "SoSe2027", '
                    '"asap", "flexible", or null when the wording cannot be mapped')

    @model_validator(mode="after")
    def check_normalized(self):
        if self.normalized is not None and (not self.stated or not NORMALIZED_DATE.fullmatch(self.normalized)):
            raise ValueError("normalized must be null or a supported date/semester form of a stated value")
        return self


class SourcedValue(BaseModel, Generic[T]):
    value: T
    evidence: list[Evidence] = Field(min_length=1, description="Short quotes supporting this value")

    @model_validator(mode="after")
    def check_value(self):
        if isinstance(self.value, str) and not self.value.strip():
            raise ValueError("A sourced value cannot be blank")
        return self


class ListField(BaseModel, Generic[T]):
    stated: bool
    items: list[SourcedValue[T]] = Field(default_factory=list)

    @model_validator(mode="after")
    def check_stated_items(self):
        if self.stated and not self.items:
            raise ValueError("A stated list field needs sourced items")
        if not self.stated and self.items:
            raise ValueError("An unstated list field cannot have items")
        return self


def _check_assessment(level: str, unknown: str, evidence: list[Evidence]) -> None:
    if level == unknown and evidence:
        raise ValueError(f"'{unknown}' cannot have evidence")
    if level != unknown and not evidence:
        raise ValueError(f"'{level}' needs evidence")


class ProgrammingWork(BaseModel):
    level: Literal["none", "some", "central", "unknown"] = Field(
        description="Programming the students perform in the project. 'none' only when the offer "
                    "explicitly says so; silence or 'qualitative' work alone is 'unknown'")
    evidence: list[Evidence] = Field(default_factory=list)

    @model_validator(mode="after")
    def check_evidence(self):
        _check_assessment(self.level, "unknown", self.evidence)
        return self


class ProgrammingSkill(BaseModel):
    level: Literal["required", "recommended", "not_stated"] = Field(
        description="Programming asked of applicants as a prerequisite, independent of the project work")
    evidence: list[Evidence] = Field(default_factory=list)

    @model_validator(mode="after")
    def check_evidence(self):
        _check_assessment(self.level, "not_stated", self.evidence)
        return self


class WorkLocationMode(BaseModel):
    level: Literal["on_site", "hybrid", "remote", "unknown"] = Field(
        description="Only from explicit statements about where the students work, not company locations")
    evidence: list[Evidence] = Field(default_factory=list)

    @model_validator(mode="after")
    def check_evidence(self):
        _check_assessment(self.level, "unknown", self.evidence)
        return self


class Contact(BaseModel):
    name: str | None = Field(description="Person or office as written, or null when only an address is given")
    email: str | None = Field(description="Email address as written, or null when none is given for this contact")

    @model_validator(mode="after")
    def check_named(self):
        if not (self.name or "").strip() and not (self.email or "").strip():
            raise ValueError("A contact needs a name or an email")
        return self


class ProjectType(str, Enum):
    project_study = "project_study"
    idp = "idp"
    bachelor_thesis = "bachelor_thesis"
    master_thesis = "master_thesis"
    semester_thesis = "semester_thesis"


class DegreeLevel(str, Enum):
    bachelor = "bachelor"
    master = "master"
    any = "any"


class WorkMode(str, Enum):
    software_development = "software_development"
    data_analysis_ml = "data_analysis_ml"
    modeling_simulation = "modeling_simulation"
    hardware_lab = "hardware_lab"
    literature_research = "literature_research"
    empirical_user_research = "empirical_user_research"
    business_strategy = "business_strategy"
    process_optimization = "process_optimization"
    marketing_content = "marketing_content"
    design_ux = "design_ux"


class ProjectProfile(BaseModel):
    """One project offer. Pipeline metadata (content_hash, page_count, extractor_version,
    schema_version) is attached by the caller when a record is stored — the model has no
    reliable way to state its own page count or which extractor version produced it."""

    source_pages: list[int] = Field(
        min_length=1, description="Every page this offer draws facts from, including shared pages; may overlap other offers")
    title: TextField = Field(description="Project offer title, not a generic section heading")
    provider_name: TextField = Field(description="hosting company/lab, distinct from the TUM chair")
    project_types: ListField[ProjectType] = Field(description="Only project formats explicitly named in this offer")
    degree_level: ListField[DegreeLevel] = Field(
        description="Only explicitly stated eligibility; 'Bachelor or Master' yields both values; "
                    "'any' only for an explicit all-levels statement")

    project_goal: TextField = Field(description="What the student project aims to achieve; may be stated without a formal deliverable")
    subjects: ListField[str] = Field(description="Knowledge domains central to the proposed work, excluding prerequisites, figure captions and company background")
    application_areas: ListField[str] = Field(description="Industries, business processes or concrete use cases served by the proposed work")
    methods_tools: ListField[str] = Field(description="Named methods, software, technologies or data used in the proposed student work, not skills named only as prerequisites")
    activities: ListField[str] = Field(description="Actions students will perform, excluding background about the company or existing system")
    work_modes: ListField[WorkMode] = Field(description="Kinds of work the students perform, each supported by a stated activity")
    programming_performed: ProgrammingWork
    programming_required: ProgrammingSkill
    deliverables: ListField[str] = Field(description="Named outputs students must create, implement, write, present or submit; excludes optional outputs")
    prerequisites_required: ListField[str] = Field(description="Mandatory skills, experience or ways of working; scope qualifiers to individual items")
    prerequisites_recommended: ListField[str] = Field(description="Skills or experience specifically called desirable, preferred, a plus or optional")
    eligible_study_fields: ListField[str] = Field(description="Explicitly named eligible degree programs or disciplines, distinct from skills")
    learning_opportunities: ListField[str] = Field(description="Explicit learning or experience gains, excluding workplace culture and ordinary tasks")
    support_offered: ListField[str] = Field(description="Explicit mentoring, supervision, coaching, training or feedback offered to students")

    team_size: TextField = Field(description='free text, e.g. "2 Studierende", "15 people" — not parsed to an integer here')
    duration: TextField
    start_date: DateField = Field(description='explicit date or stated text such as "asap"/"flexible"')
    application_deadline: DateField
    location: TextField = Field(description='Where the students work, e.g. "Munich (at least 2 days/week on-site)"; not the company headquarters')
    work_location_mode: WorkLocationMode
    working_language: ListField[str] = Field(description="Explicit project working languages; language skill requirements belong under prerequisites")

    contacts: ListField[Contact] = Field(description="Every contact named for this offer, each with its own evidence")
    application_instructions: TextField
    external_url: TextField

    search_summary_en: str = Field(
        min_length=1, description="2-4 neutral English sentences restating only facts extracted above for this offer: "
                                  "what students do, on which topic, with which methods, for whom")


class DocumentExtraction(BaseModel):
    """LLM output for one PDF: zero, one or several independent project offers."""

    document_language: Literal["de", "en", "mixed", "other", "unknown"] = Field(
        description="Language of the document body, independent of working language or language skills")
    document_kind: Literal["offer", "multi_offer", "not_an_offer", "unknown"] = Field(
        description="multi_offer when the document contains several independent offers; the same offer "
                    "repeated in another language is one offer")
    offers: list[ProjectProfile]

    @model_validator(mode="after")
    def check_offer_count(self):
        count = len(self.offers)
        if (self.document_kind == "offer" and count != 1 or self.document_kind == "multi_offer" and count < 2
                or self.document_kind in ("not_an_offer", "unknown") and count):
            raise ValueError(f"document_kind={self.document_kind} does not match {count} offers")
        return self


class PdfTextCoverage(BaseModel):
    """Deterministic extraction metadata, attached outside the LLM output."""

    classification: Literal["digital_native", "mixed", "scanned", "unknown"]
    classifier_version: str
    page_count: int = Field(ge=0)
    blank_markdown_pages: list[int] = Field(default_factory=list)
    status: Literal["text_on_all_pages", "partial_text", "no_text"]
    text_chars: int = Field(ge=0)
    short_text: bool = Field(description="Below SHORT_TEXT_CHARS: still extracted, but flagged for review or OCR assessment")

    @classmethod
    def from_pages(cls, classification: str, classifier_version: str, pages: list[str]) -> "PdfTextCoverage":
        blank_pages = [number for number, page in enumerate(pages, start=1) if not page.strip()]
        status = ("no_text" if len(blank_pages) == len(pages)
                  else "text_on_all_pages" if classification == "digital_native" and not blank_pages
                  else "partial_text")
        text_chars = sum(len(page.strip()) for page in pages)
        return cls(classification=classification, classifier_version=classifier_version,
                   page_count=len(pages), blank_markdown_pages=blank_pages, status=status,
                   text_chars=text_chars, short_text=text_chars < SHORT_TEXT_CHARS)


class EvidenceIssue(BaseModel):
    offer_index: int | None = None
    field: str
    item_index: int | None = None
    page: int
    reason: Literal["page_out_of_range", "quote_not_found", "outside_offer_pages"]


class ProfileExtraction(BaseModel):
    """LLM result and deterministic source metadata for later review and indexing.

    A failed extraction carries no document. Whoever persists these records must keep the
    previous ok result for the same content hash rather than overwrite it with a failure."""

    content_hash: str
    schema_version: str
    prompt_version: str
    prompt_hash: str
    model_deployment: str
    reasoning_effort: str
    coverage: PdfTextCoverage
    status: Literal["ok", "failed"]
    attempts: int = Field(ge=1)
    errors: list[str] = Field(default_factory=list, description="Validation messages without document text")
    input_tokens: int = 0
    output_tokens: int = 0
    reasoning_tokens: int = 0
    evidence_issues: list[EvidenceIssue] = Field(default_factory=list)
    document: DocumentExtraction | None = None

    @model_validator(mode="after")
    def check_status(self):
        if (self.status == "ok") != (self.document is not None):
            raise ValueError("Only an ok extraction carries a document")
        return self
