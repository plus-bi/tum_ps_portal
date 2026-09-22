import re
from dataclasses import dataclass
from .registry import ChairAdapter


@dataclass(frozen=True)
class Classification:
    accepted: bool
    certain: bool
    reason: str


def classify(text: str, adapter: ChairAdapter, *, in_archive: bool = False) -> Classification:
    normalized = re.sub(r"\s+", " ", text).casefold()
    if in_archive or any(marker in normalized for marker in adapter.archive_markers):
        return Classification(False, True, "archive section")
    if any(marker in normalized for marker in adapter.excluded_markers):
        return Classification(False, True, "excluded opportunity type")
    if any(marker in normalized for marker in adapter.active_markers):
        return Classification(True, True, "explicit Project Study marker")
    return Classification(False, False, "opportunity type is uncertain")
