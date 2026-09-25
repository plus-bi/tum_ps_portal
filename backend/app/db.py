from datetime import date, datetime
from uuid import UUID, uuid4
from sqlalchemy import JSON, Boolean, Date, DateTime, Enum, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from .config import settings
from .schemas import Status


class Base(DeclarativeBase): pass


_engine = None

def engine():
    global _engine
    if _engine is None:
        _engine = create_engine(settings().database_url, pool_pre_ping=True)
    return _engine

def session_factory():
    return sessionmaker(bind=engine(), expire_on_commit=False)


class Department(Base):
    __tablename__ = "departments"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    slug: Mapped[str] = mapped_column(String(80), unique=True)
    name: Mapped[str] = mapped_column(String(160))


class Chair(Base):
    __tablename__ = "chairs"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    department_id: Mapped[UUID] = mapped_column(ForeignKey("departments.id"))
    slug: Mapped[str] = mapped_column(String(120), unique=True)
    name: Mapped[str] = mapped_column(String(200))


class Source(Base):
    __tablename__ = "sources"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    chair_id: Mapped[UUID] = mapped_column(ForeignKey("chairs.id"))
    url: Mapped[str] = mapped_column(Text)
    adapter: Mapped[str] = mapped_column(String(120))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0)
    etag: Mapped[str | None] = mapped_column(String(300))
    last_modified: Mapped[str | None] = mapped_column(String(300))


class Listing(Base):
    __tablename__ = "listings"
    __table_args__ = (UniqueConstraint("chair_id", "stable_source_key"),)
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    chair_id: Mapped[UUID] = mapped_column(ForeignKey("chairs.id"), index=True)
    stable_source_key: Mapped[str] = mapped_column(String(80))
    slug: Mapped[str] = mapped_column(String(320), unique=True)
    reference_code: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(300))
    summary: Mapped[str | None] = mapped_column(Text)
    normalized: Mapped[dict] = mapped_column(JSON, default=dict)
    content_hash: Mapped[str] = mapped_column(String(64))
    status: Mapped[Status] = mapped_column(Enum(Status), default=Status.pending_review, index=True)
    published_at: Mapped[date | None] = mapped_column(Date)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    consecutive_misses: Mapped[int] = mapped_column(Integer, default=0)


class ListingVersion(Base):
    __tablename__ = "listing_versions"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    listing_id: Mapped[UUID] = mapped_column(ForeignKey("listings.id"), index=True)
    content_hash: Mapped[str] = mapped_column(String(64))
    extracted: Mapped[dict] = mapped_column(JSON)
    evidence: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SourceArtifact(Base):
    __tablename__ = "source_artifacts"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    source_id: Mapped[UUID] = mapped_column(ForeignKey("sources.id"), index=True)
    content_hash: Mapped[str] = mapped_column(String(64))
    media_type: Mapped[str] = mapped_column(String(100))
    extracted_text: Mapped[str] = mapped_column(Text)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PDFArtifact(Base):
    __tablename__ = "pdf_artifacts"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    url: Mapped[str] = mapped_column(Text, unique=True)
    content_hash: Mapped[str | None] = mapped_column(String(64))
    storage_key: Mapped[str | None] = mapped_column(String(100))
    byte_size: Mapped[int | None] = mapped_column(Integer)
    media_type: Mapped[str | None] = mapped_column(String(100))
    fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error: Mapped[str | None] = mapped_column(Text)


class PDFAnalysis(Base):
    __tablename__ = "pdf_analysis"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    content_hash: Mapped[str] = mapped_column(String(64), unique=True)
    classification: Mapped[str] = mapped_column(String(30), default="unknown")
    classifier_version: Mapped[str] = mapped_column(String(80))
    classified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    extracted_markdown_pages: Mapped[list | None] = mapped_column(JSON)


class PDFProfileExtraction(Base):
    """One LLM project-profile extraction attempt per row; failures are added, never overwrite an ok row."""
    __tablename__ = "pdf_profile_extractions"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    schema_version: Mapped[str] = mapped_column(String(80))
    prompt_version: Mapped[str] = mapped_column(String(80))
    prompt_hash: Mapped[str] = mapped_column(String(64))
    model_deployment: Mapped[str] = mapped_column(String(120))
    reasoning_effort: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20))
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    errors: Mapped[list] = mapped_column(JSON, default=list)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    reasoning_tokens: Mapped[int] = mapped_column(Integer, default=0)
    coverage: Mapped[dict | None] = mapped_column(JSON)
    evidence_issues: Mapped[list] = mapped_column(JSON, default=list)
    document: Mapped[dict | None] = mapped_column(JSON)
    extracted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CrawlRun(Base):
    __tablename__ = "crawl_runs"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    source_id: Mapped[UUID | None] = mapped_column(ForeignKey("sources.id"), index=True)
    status: Mapped[str] = mapped_column(String(30))
    stats: Mapped[dict] = mapped_column(JSON, default=dict)
    error: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ExtractionReview(Base):
    __tablename__ = "extraction_reviews"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    listing_id: Mapped[UUID] = mapped_column(ForeignKey("listings.id"), index=True)
    decision: Mapped[str | None] = mapped_column(String(30))
    reviewer_id: Mapped[str | None] = mapped_column(String(160))
    notes: Mapped[str | None] = mapped_column(Text)


class ManualOverride(Base):
    __tablename__ = "manual_overrides"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    listing_id: Mapped[UUID] = mapped_column(ForeignKey("listings.id"), index=True)
    field: Mapped[str] = mapped_column(String(80))
    value: Mapped[dict] = mapped_column(JSON)
    actor_id: Mapped[str] = mapped_column(String(160))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ClerkUser(Base):
    __tablename__ = "clerk_users"
    clerk_id: Mapped[str] = mapped_column(String(160), primary_key=True)
    email: Mapped[str] = mapped_column(String(320))
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Bookmark(Base):
    __tablename__ = "bookmarks"
    __table_args__ = (UniqueConstraint("user_id", "listing_id"),)
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[str] = mapped_column(ForeignKey("clerk_users.clerk_id"))
    listing_id: Mapped[UUID] = mapped_column(ForeignKey("listings.id"))


class SavedSearch(Base):
    __tablename__ = "saved_searches"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[str] = mapped_column(ForeignKey("clerk_users.clerk_id"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    query: Mapped[dict] = mapped_column(JSON)
    frequency: Mapped[str] = mapped_column(String(20))
    paused: Mapped[bool] = mapped_column(Boolean, default=False)


class NotificationDelivery(Base):
    __tablename__ = "notification_deliveries"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[str | None] = mapped_column(String(160), index=True)
    saved_search_id: Mapped[UUID | None] = mapped_column(ForeignKey("saved_searches.id"))
    listing_id: Mapped[UUID] = mapped_column(ForeignKey("listings.id"))
    uniqueness_key: Mapped[str] = mapped_column(String(300), unique=True)
    provider_id: Mapped[str | None] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(30))
