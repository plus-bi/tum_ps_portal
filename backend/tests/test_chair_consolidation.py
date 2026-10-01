import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.exc import OperationalError

from app.consolidate_controlling import consolidate
from app.db import Base, Bookmark, Chair, ClerkUser, Department, Listing, ListingVersion, Source
from app.schemas import Status
import app.db as db
from app.api import canonical_project_slug, project_aliases, persisted_projects


def test_alias_lookup_preserves_slug_when_database_is_unavailable(monkeypatch):
    def unavailable_session():
        raise OperationalError("connection", {}, Exception("unavailable"))

    monkeypatch.setattr("app.api.session_factory", unavailable_session)
    assert canonical_project_slug("example-project-study") == "example-project-study"


def setup_records(session):
    department = Department(slug="finance", name="Finance and Accounting")
    session.add(department); session.flush()
    kept = Chair(slug="controlling", name="Controlling", department_id=department.id)
    retired = Chair(slug="management-accounting", name="Management Accounting", department_id=department.id)
    session.add_all([kept, retired]); session.flush()
    source = Source(chair_id=retired.id, url="https://example.org/en", adapter="typo3")
    rows = [Listing(chair_id=chair.id, stable_source_key="key", slug=slug, reference_code=code,
                    title="Offer", content_hash="hash", normalized={"artifact_url": "https://example.org/offer.pdf", "source_url": "https://example.org/projects"}, status=Status.active)
            for chair, slug, code in [(kept, "kept", "ps-1"), (retired, "old", "ps-2")]]
    session.add_all([source, *rows, ClerkUser(clerk_id="user", email="user@example.org")]); session.flush()
    session.add_all([Bookmark(user_id="user", listing_id=row.id) for row in rows])
    session.add(ListingVersion(listing_id=rows[1].id, content_hash="hash", extracted={}, evidence={}))
    session.flush()
    return source, rows


def test_merge_preserves_history_deduplicates_bookmarks_and_is_idempotent():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        source, (kept, old) = setup_records(session)
        assert consolidate(session)["duplicate_projects"] == 1
        assert old.status == Status.active
        report = consolidate(session, apply=True)
        assert report["aliases"] == {"old": "kept"}
        assert old.status == Status.archived
        assert old.normalized["merged_into_slug"] == kept.slug
        assert not source.enabled
        assert len(session.scalars(select(Listing)).all()) == 2
        assert len(session.scalars(select(ListingVersion)).all()) == 1
        bookmarks = session.scalars(select(Bookmark)).all()
        assert len(bookmarks) == 1 and bookmarks[0].listing_id == kept.id
        assert consolidate(session, apply=True)["duplicate_projects"] == 0


def test_unmatched_offer_aborts_before_modifying_listings():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        source, (_, old) = setup_records(session)
        old.normalized = {"artifact_url": "https://example.org/unique.pdf"}
        with pytest.raises(RuntimeError, match="Unmatched English project"):
            consolidate(session, apply=True)
        assert old.status == Status.active and source.enabled


def test_merged_projects_resolve_old_slugs_and_are_excluded_from_catalog(monkeypatch, tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'consolidation.db'}")
    monkeypatch.setattr(db, "_engine", engine)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        setup_records(session)
        consolidate(session, apply=True)
        session.commit()
    assert canonical_project_slug("old") == "kept"
    assert canonical_project_slug("kept") == "kept"
    assert project_aliases() == {"old": "kept"}
    assert [project.slug for project in persisted_projects()] == ["kept"]
