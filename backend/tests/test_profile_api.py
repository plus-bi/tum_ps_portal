from fastapi.testclient import TestClient
from sqlalchemy import create_engine

import app.db as db
from app.db import Base, Chair, Department, Listing, PDFArtifact, PDFProfileExtraction
from app.ingestion import profile_backfill
from app.ingestion.project_profile import PdfTextCoverage
from app.main import app
from app.schemas import Status
from profile_builders import document, empty_offer

client = TestClient(app)


def add_project(slug, content_hash, review_flags, evidence_issues=()):
    artifact_url = f"https://example.org/{slug}.pdf"
    coverage = PdfTextCoverage.from_pages("digital_native", "reader-v1", ["Project text " * 10])
    with db.session_factory()() as session:
        department = Department(slug=f"dept-{slug}", name="Informatics")
        session.add(department)
        session.flush()
        chair = Chair(department_id=department.id, slug=f"chair-{slug}", name="Chair")
        session.add(chair)
        session.flush()
        session.add(Listing(chair_id=chair.id, stable_source_key=slug, slug=slug, reference_code=slug[:8].upper(),
                            title="Project", content_hash="0" * 64, status=Status.active,
                            normalized={"source_url": "https://example.org/", "artifact_url": artifact_url}))
        session.add(PDFArtifact(url=artifact_url, content_hash=content_hash))
        session.add(PDFProfileExtraction(content_hash=content_hash, **profile_backfill.current_version("low"),
                                         status="ok", attempts=1, errors=[], coverage=coverage.model_dump(mode="json"),
                                         evidence_issues=list(evidence_issues), review_flags=review_flags,
                                         document=document(empty_offer()).model_dump(mode="json")))
        session.commit()


def test_profiles_needing_ocr_are_hidden_and_unverified_ones_are_flagged(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'api.db'}")
    monkeypatch.setattr(db, "_engine", engine)
    Base.metadata.create_all(engine)
    issue = {"offer_index": 0, "field": "title", "item_index": None, "page": 1, "reason": "quote_not_found"}
    add_project("clean", "a" * 64, [])
    add_project("unverified", "b" * 64, ["unverified_citations"], [issue])
    add_project("ocr", "c" * 64, ["requires_ocr", "unverified_citations"])

    projects = {project["slug"]: project["has_profile"] for project in client.get("/api/v1/projects?page_size=50").json()["items"]}
    assert projects == {"clean": True, "unverified": True, "ocr": False}

    assert client.get("/api/v1/projects/clean/profile").json()["review_flags"] == []
    detail = client.get("/api/v1/projects/unverified/profile").json()
    assert detail["review_flags"] == ["unverified_citations"] and detail["evidence_issues"] == [issue]
    assert client.get("/api/v1/projects/ocr/profile").status_code == 404
