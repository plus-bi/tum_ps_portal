from datetime import date
from app.ingestion.classifier import classify
from app.ingestion.lifecycle import Lifecycle, after_crawl, freshness
from app.ingestion.registry import REGISTRY
from app.schemas import Freshness, Status


def test_project_only_classifier():
    adapter = REGISTRY[0]
    assert classify("Open Project Study: AI", adapter).accepted
    assert classify("Master thesis: AI", adapter).certain
    assert not classify("Master thesis: AI", adapter).accepted
    assert not classify("Interesting student opportunity", adapter).certain
    assert not classify("Project Study completed", adapter, in_archive=True).accepted


def test_failed_crawl_never_archives_and_two_successful_misses_do():
    state = Lifecycle(Status.active)
    assert after_crawl(state, crawl_succeeded=False, seen=False) == state
    once = after_crawl(state, crawl_succeeded=True, seen=False)
    assert once.status == Status.active
    assert after_crawl(once, crawl_succeeded=True, seen=False).status == Status.archived
    assert after_crawl(once, crawl_succeeded=True, seen=True) == Lifecycle(Status.active, 0)


def test_freshness_is_independent_of_status():
    assert freshness(None, date(2026, 9, 22)) == Freshness.undated
    assert freshness(date(2026, 1, 1), date(2026, 9, 22)) == Freshness.old
    assert freshness(date(2026, 9, 1), date(2026, 9, 22)) == Freshness.current
