from collections import Counter
from app.ingestion.registry import ALL_REGISTRY, BY_SLUG, IDP_REGISTRY, REGISTRY, SourceState


def test_all_32_chairs_have_dedicated_entries():
    assert len(REGISTRY) == len(BY_SLUG) == 32
    assert sorted(Counter(a.department for a in REGISTRY).values()) == [5, 6, 7, 7, 7]
    assert all(a.source_urls and a.stable_key(a.source_urls[0], "A") for a in REGISTRY)
    assert BY_SLUG["economics-of-innovation"].source_urls == ("https://www.ep.mgt.tum.de/en/eoi/teaching/project-studies/",)
    assert BY_SLUG["marketing-and-technology"].source_urls == ("https://www.msl.mgt.tum.de/en/mt/teaching-student-matters/project-studies-idp/",)
    assert BY_SLUG["marketing-and-technology"].state == SourceState.active
    assert "idp" not in BY_SLUG["marketing-and-technology"].excluded_markers
    assert {a.family for a in REGISTRY} == {"typo3", "squarespace", "legacy_html"}
    assert BY_SLUG["financial-accounting"].child_url_patterns
    assert BY_SLUG["governance-in-international-agribusiness"].state == SourceState.empty


def test_official_informatics_idp_hub_and_all_published_chair_sources_are_registered():
    assert len(IDP_REGISTRY) == 32
    assert len(ALL_REGISTRY) == 64
    hub = IDP_REGISTRY[0]
    assert hub.slug == "informatics-idp-hub"
    assert hub.opportunity_type == "idp"
    assert hub.source_implies_active_type
    assert all(adapter.opportunity_type == "idp" for adapter in IDP_REGISTRY)
