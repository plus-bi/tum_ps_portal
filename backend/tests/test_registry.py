from collections import Counter
from app.ingestion.registry import BY_SLUG, REGISTRY, SourceState


def test_all_32_chairs_have_dedicated_entries():
    assert len(REGISTRY) == len(BY_SLUG) == 32
    assert sorted(Counter(a.department for a in REGISTRY).values()) == [5, 6, 7, 7, 7]
    assert all(a.source_urls and a.stable_key(a.source_urls[0], "A") for a in REGISTRY)
    assert BY_SLUG["economics-of-innovation"].source_urls == ("https://www.ep.mgt.tum.de/en/eoi/teaching/project-studies/",)
    assert BY_SLUG["marketing-and-technology"].state == SourceState.broken
    assert {a.family for a in REGISTRY} == {"typo3", "squarespace", "legacy_html"}
    assert BY_SLUG["financial-accounting"].child_url_patterns
    assert BY_SLUG["governance-in-international-agribusiness"].state == SourceState.empty
