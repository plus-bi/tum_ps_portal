import hashlib, json
from pathlib import Path
import pytest
from app.ingestion.adapters import parser_for
from app.ingestion.registry import ALL_BY_SLUG

ROOT = Path(__file__).parent / "fixtures/chairs"
MANIFEST = json.loads((ROOT / "manifest.json").read_text())
CAPTURED = [row for row in MANIFEST["sources"] if "fixture" in row]

@pytest.mark.parametrize("row", CAPTURED, ids=lambda row: row["slug"])
def test_frozen_live_fixture_integrity_and_parser_contract(row):
    fixture = ROOT / row["fixture"]
    content = fixture.read_bytes()
    assert hashlib.sha256(content).hexdigest() == row["sha256"]
    adapter = ALL_BY_SLUG[row["slug"]]
    if row["fixture"].endswith(".html"):
        candidates = parser_for(adapter).discover(adapter, row["final_url"], content)
        assert len({candidate.stable_source_key for candidate in candidates}) == len(candidates)

def test_removed_and_replaced_idp_sources_are_current():
    slugs = {row["slug"] for row in MANIFEST["sources"]}
    assert "idp-cartken-robotics" not in slugs
    replacements = {
        "idp-chair-for-entrepreneurial-finance",
        "idp-chair-of-media-technology",
        "idp-dr-theo-sch-ller-stiftungslehrstuhl-f-r-technologie-und-innovationsmanagement",
        "idp-human-centered-technologies-for-learning",
        "idp-professorship-of-business-analytics-and-intelligent-systems",
    }
    rows = {row["slug"]: row for row in MANIFEST["sources"]}
    assert all(rows[slug]["status"] == 200 for slug in replacements)

def test_known_live_offer_counts_are_stable():
    expected = {
        "economics-of-innovation": 1,
        "management-accounting": 52,
        "corporate-management": 25,
        "technology-and-innovation-management": 9,
        "family-business-culture-and-ownership": 6,
        "digital-marketing": 24,
        "other-tum-data-innovation-lab": 14,
        "idp-institute-of-automotive-technology": 10,
        "idp-institute-for-machine-tools-and-industrial-management": 8,
        "idp-chair-of-renewable-and-sustainable-energy-systems": 4,
        "idp-professorship-of-multiscale-modeling-of-fluid-materials": 4,
        "idp-chair-of-financial-accounting": 2,
    }
    rows = {row["slug"]: row for row in CAPTURED}
    for slug, count in expected.items():
        row = rows[slug]; content = (ROOT / row["fixture"]).read_bytes()
        assert len(parser_for(ALL_BY_SLUG[slug]).discover(ALL_BY_SLUG[slug], row["final_url"], content)) == count

def test_management_accounting_extracts_proposals_without_previous_studies():
    row = next(row for row in CAPTURED if row["slug"] == "management-accounting")
    adapter = ALL_BY_SLUG[row["slug"]]
    candidates = parser_for(adapter).discover(adapter, row["final_url"], (ROOT / row["fixture"]).read_bytes())
    assert len(candidates) == 52
    assert len({candidate.stable_source_key for candidate in candidates}) == 52
    assert candidates[0].title == "Gipfeltour Business Development & Marketing @ Handballgemeinschaft München (German required)"
    assert candidates[0].source_url.endswith("20260408_TUMProjektstudium_HGM_vfin.pdf")
    assert candidates[1].title == "Redesigning Treasury Today with an AI-First Approach @ SAP"
    assert candidates[-1].title == "Sales Strategy or Operations @ Alpaka Climate"
    assert all(candidate.application_url == candidate.source_url for candidate in candidates)
    assert "Project Study @NetZero" not in {candidate.title for candidate in candidates}


def test_management_accounting_rejects_unlinked_and_previous_content():
    adapter = ALL_BY_SLUG["management-accounting"]
    content = b'''<div class="frame"><p><strong>Current topics:</strong></p>
        <p><a href="/files/open.pdf">Current topic with detail</a></p>
        <p><a href="/contact">Contact</a></p></div>
        <div class="frame">
        <p><strong>Recent Proposals:</strong></p>
        <ul><li><a href="/files/open.pdf">Open offer</a></li>
            <li><a href="/files/second.pdf">Second offer</a></li>
            <li><a href="/contact">Contact</a></li><li>No document</li></ul>
        <p><strong>Previous Project Studies:</strong></p>
        <ul><li><a href="/files/previous.pdf">Previous project</a></li></ul>
    </div>'''
    candidates = parser_for(adapter).discover(adapter, adapter.source_urls[0], content)
    assert [candidate.title for candidate in candidates] == ["Current topic with detail", "Second offer"]
