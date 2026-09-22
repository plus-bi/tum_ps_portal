from dataclasses import dataclass
from datetime import date, timedelta
from ..schemas import Freshness, Status


def freshness(published: date | None, today: date | None = None) -> Freshness:
    if published is None:
        return Freshness.undated
    today = today or date.today()
    return Freshness.old if today - published > timedelta(days=180) else Freshness.current


@dataclass(frozen=True)
class Lifecycle:
    status: Status
    consecutive_misses: int = 0


def after_crawl(current: Lifecycle, *, crawl_succeeded: bool, seen: bool) -> Lifecycle:
    if not crawl_succeeded:
        return current
    if seen:
        return Lifecycle(Status.active, 0)
    misses = current.consecutive_misses + 1
    return Lifecycle(Status.archived if misses >= 2 else current.status, misses)
