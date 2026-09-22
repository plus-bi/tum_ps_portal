from datetime import date, datetime, timezone
from enum import StrEnum
from pydantic import BaseModel, ConfigDict, EmailStr, Field, HttpUrl


class Status(StrEnum):
    pending_review = "pending_review"
    active = "active"
    archived = "archived"


class Freshness(StrEnum):
    current = "current"
    old = "old"
    undated = "undated"


class Topic(StrEnum):
    ai_data = "ai_data"
    marketing_sales = "marketing_sales"
    strategy_entrepreneurship = "strategy_entrepreneurship"
    finance_accounting = "finance_accounting"
    operations_supply_chain = "operations_supply_chain"
    sustainability_energy = "sustainability_energy"
    law_governance = "law_governance"
    health_sport = "health_sport"
    other = "other"


class Confidence(BaseModel):
    value: float = Field(ge=0, le=1)
    evidence: str = Field(max_length=500)


class ExtractedListing(BaseModel):
    """Strict schema passed to Responses API structured parsing."""
    model_config = ConfigDict(extra="forbid")
    is_project_study: bool
    title: str = Field(min_length=1, max_length=300)
    summary: str | None = Field(default=None, max_length=3000)
    company: str | None = None
    language: str | None = None
    topics: list[Topic] = []
    location: str | None = None
    remote_mode: str | None = None
    team_size_min: int | None = Field(default=None, ge=1)
    team_size_max: int | None = Field(default=None, ge=1)
    duration: str | None = None
    workload: str | None = None
    start_date: date | None = None
    deadline: date | None = None
    application_url: HttpUrl | None = None
    application_email: EmailStr | None = None
    published_at: date | None = None
    confidence: dict[str, Confidence]


class Project(BaseModel):
    slug: str
    title: str
    summary: str | None = None
    department: str
    chair: str
    company: str | None = None
    language: str | None = None
    topics: list[Topic] = []
    location: str | None = None
    remote_mode: str | None = None
    team_size_min: int | None = None
    team_size_max: int | None = None
    duration: str | None = None
    workload: str | None = None
    start_date: date | None = None
    deadline: date | None = None
    application_url: str | None = None
    application_email: str | None = None
    source_url: str
    artifact_url: str | None = None
    published_at: date | None = None
    first_seen_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_seen_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    status: Status = Status.active
    freshness: Freshness = Freshness.undated


class ProjectQuery(BaseModel):
    q: str | None = None
    departments: list[str] = []
    chairs: list[str] = []
    topics: list[Topic] = []
    languages: list[str] = []
    status: Status = Status.active
    sort: str = "relevance"
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


class SavedSearchCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    query: ProjectQuery
    frequency: str = Field(pattern="^(immediate|daily|weekly)$")
