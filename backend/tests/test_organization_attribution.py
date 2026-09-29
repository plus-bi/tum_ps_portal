import json
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine

import app.db as db
from app.db import (Base, Chair, Department, Listing, OrganizationAttribution, PDFAnalysis,
                    PDFArtifact, PDFProfileExtraction)
from app.api import persisted_projects
from app.ingestion import organization_backfill, profile_backfill
from app.ingestion.organization_attribution import extract_organization_candidates
from app.ingestion.project_profile import Evidence, TextField
from app.schemas import Status
from profile_builders import document, empty_offer


def test_header_academic_unit_and_external_partner_keep_separate_evidence():
    page = "Chair of Spacecraft Systems TUM School of Engineering and Design\n# IDP project\nBayWa r.e."
    offer = empty_offer(provider_name=TextField(stated=True, value="BayWa r.e.",
                                                evidence=[Evidence(page=1, excerpt="BayWa r.e.")]))
    values = extract_organization_candidates([page], offer)
    assert [(item.name, item.evidence.page) for item in values.academic_units] == [("Chair of Spacecraft Systems", 1)]
    assert [(item.name, item.evidence.excerpt) for item in values.project_partners] == [("BayWa r.e.", "BayWa r.e.")]


def test_registered_unit_alias_deduplicates_provider_and_header():
    page = "Institute for Machine Tools and Industrial Management (iwb) TUM School of Engineering and Design"
    offer = empty_offer(provider_name=TextField(stated=True, value="iwb",
                                                evidence=[Evidence(page=1, excerpt="iwb")]))
    values = extract_organization_candidates([page], offer)
    assert len(values.academic_units) == 1
    assert values.academic_units[0].canonical_name == "Institute for Machine Tools and Industrial Management"
    assert values.project_partners == []


def test_header_pattern_stops_before_school_and_normalizes_german_iwb():
    page = "Institut für Werkzeugmaschinen und Betriebswissenschaften ( _iwb_ ) TUM School of Engineering and Design"
    values = extract_organization_candidates([page], empty_offer())
    assert len(values.academic_units) == 1
    assert values.academic_units[0].canonical_name == "Institute for Machine Tools and Industrial Management"
    page = "Lehrstuhl für Berufspädagogik Department Educational Sciences School of Social Sciences"
    values = extract_organization_candidates([page], empty_offer())
    assert values.academic_units[0].name == "Lehrstuhl für Berufspädagogik"
    page = "Chair of Spacecraft Systems (TUM SPS): https://www.asg.ed.tum.de/en/sps/"
    values = extract_organization_candidates([page], empty_offer())
    assert values.academic_units[0].name == "Chair of Spacecraft Systems (TUM SPS)"


def test_absent_organizations_stay_unknown():
    values = extract_organization_candidates(["# Data science project\nBuild a prototype."], empty_offer())
    assert values.academic_units == []
    assert values.project_partners == []


def test_provider_labeled_chair_without_of_is_academic_candidate():
    offer = empty_offer(provider_name=TextField(stated=True, value="Chair Digital Agriculture TUM School of Life Sciences",
                                                evidence=[Evidence(page=1, excerpt="Chair Digital Agriculture TUM School of Life Sciences")]))
    values = extract_organization_candidates(["Chair Digital Agriculture TUM School of Life Sciences"], offer)
    assert [item.name for item in values.academic_units] == ["Chair Digital Agriculture TUM School of Life Sciences"]
    assert values.project_partners == []


def test_backfill_is_dry_run_then_reviewed_publication(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'organizations.db'}")
    monkeypatch.setattr(db, "_engine", engine)
    config = SimpleNamespace(organization_attribution_preview=False,
                             public_url="http://localhost:8080")
    monkeypatch.setattr("app.api.settings", lambda: config)
    Base.metadata.create_all(engine)
    page = "Chair of Spacecraft Systems TUM School of Engineering and Design\n# IDP project\nBayWa r.e."
    offer = empty_offer(provider_name=TextField(stated=True, value="BayWa r.e.",
                                                evidence=[Evidence(page=1, excerpt="BayWa r.e.")]))
    with db.session_factory()() as session:
        department = Department(slug="idp", name="Interdisciplinary Projects")
        session.add(department)
        session.flush()
        chair = Chair(department_id=department.id, slug="informatics-idp-hub", name="Informatics IDP Hub")
        session.add(chair)
        session.flush()
        session.add(Listing(chair_id=chair.id, stable_source_key="project", slug="hub-project",
                            reference_code="idp-001", title="Project", content_hash="f" * 64,
                            normalized={"source_url": "https://example.org/hub", "artifact_url": "https://example.org/offer.pdf",
                                        "opportunity_type": "idp"}, status=Status.active))
        session.add(PDFArtifact(url="https://example.org/offer.pdf", content_hash="a" * 64))
        session.add(PDFAnalysis(content_hash="a" * 64, classification="digital_native", classifier_version="reader-v1",
                                extracted_markdown_pages=[page]))
        session.add(PDFProfileExtraction(content_hash="a" * 64, **profile_backfill.current_version("low"),
                                         status="ok", attempts=1, errors=[], evidence_issues=[], review_flags=[],
                                         document=document(offer).model_dump(mode="json")))
        session.commit()
    rows = organization_backfill.candidate_rows()
    assert len(rows) == 1
    assert rows[0]["review_id"] == "IDP-001"
    assert rows[0]["opportunity_type"] == "idp"
    assert rows[0]["title"] == "Project"
    assert rows[0]["artifact_url"] == "https://example.org/offer.pdf"
    assert rows[0]["academic_units"][0]["name"] == "Chair of Spacecraft Systems"
    with db.session_factory()() as session:
        assert session.query(OrganizationAttribution).count() == 0
    assert organization_backfill.apply_candidates(rows) == {"created": 1, "existing": 0}
    assert organization_backfill.apply_candidates(rows) == {"created": 0, "existing": 1}
    assert persisted_projects()[0].academic_units == []
    config.organization_attribution_preview = True
    preview = persisted_projects()[0]
    assert preview.chair == "Chair of Spacecraft Systems"
    assert [item.name for item in preview.project_partners] == ["BayWa r.e."]
    config.organization_attribution_preview = False
    review_file = tmp_path / "reviewed.jsonl"
    unsupported = {**rows[0], "approve": True, "academic_units": [
        {**rows[0]["academic_units"][0], "name": "Chair of Fiction"}]}
    review_file.write_text(json.dumps(unsupported) + "\n")
    with pytest.raises(ValueError, match="Unverified organization quote"):
        organization_backfill.approve_rows(review_file)
    review_file.write_text(json.dumps({**rows[0], "approve": True}) + "\n")
    assert organization_backfill.approve_rows(review_file) == {"approved": 1}
    with db.session_factory()() as session:
        assert session.query(OrganizationAttribution).one().status == "approved"
    approved = persisted_projects()[0]
    assert approved.chair == "Chair of Spacecraft Systems"
    assert [item.name for item in approved.project_partners] == ["BayWa r.e."]
