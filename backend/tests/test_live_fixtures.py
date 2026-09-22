import hashlib, json
from pathlib import Path
import pytest
from app.ingestion.adapters import parser_for
from app.ingestion.registry import BY_SLUG

ROOT = Path(__file__).parent / "fixtures/chairs"
MANIFEST = json.loads((ROOT / "manifest.json").read_text())
CAPTURED = [row for row in MANIFEST["sources"] if "fixture" in row]

@pytest.mark.parametrize("row", CAPTURED, ids=lambda row: row["slug"])
def test_frozen_live_fixture_integrity_and_parser_contract(row):
    fixture = ROOT / row["fixture"]
    content = fixture.read_bytes()
    assert hashlib.sha256(content).hexdigest() == row["sha256"]
    adapter = BY_SLUG[row["slug"]]
    if row["fixture"].endswith(".html"):
        candidates = parser_for(adapter).discover(adapter, row["final_url"], content)
        assert len({candidate.stable_source_key for candidate in candidates}) == len(candidates)

def test_known_broken_source_is_recorded_not_faked():
    broken = next(row for row in MANIFEST["sources"] if row["slug"] == "marketing-and-technology")
    assert broken["status"] == "error"
    assert "404" in broken["error"]

def test_known_live_offer_counts_are_stable():
    expected = {
        "economics-of-innovation": 1,
        "management-accounting": 1,
        "corporate-management": 25,
        "technology-and-innovation-management": 9,
        "family-business-culture-and-ownership": 4,
        "digital-marketing": 2,
    }
    rows = {row["slug"]: row for row in CAPTURED}
    for slug, count in expected.items():
        row = rows[slug]; content = (ROOT / row["fixture"]).read_bytes()
        assert len(parser_for(BY_SLUG[slug]).discover(BY_SLUG[slug], row["final_url"], content)) == count

def test_nested_netzero_listing_uses_specific_list_item():
    row = next(row for row in CAPTURED if row["slug"] == "management-accounting")
    adapter = BY_SLUG[row["slug"]]
    candidates = parser_for(adapter).discover(adapter, row["final_url"], (ROOT / row["fixture"]).read_bytes())
    assert candidates[0].title == "Project Study @NetZero"
    assert candidates[0].source_text == "Project Study @NetZero"
