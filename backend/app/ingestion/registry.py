from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from urllib.parse import urlparse


class SourceState(StrEnum):
    active = "active"
    empty = "empty"
    broken = "broken"
    needs_audit = "needs_audit"


@dataclass(frozen=True)
class ChairAdapter:
    """Chair-owned discovery rules; parsing machinery can be shared by family."""
    slug: str
    name: str
    department: str
    source_urls: tuple[str, ...]
    family: str
    state: SourceState = SourceState.needs_audit
    candidate_selectors: tuple[str, ...] = ("article", ".news-list-item", ".news-single", ".frame", ".accordion-item", "li")
    child_link_markers: tuple[str, ...] = ("project stud", "projektstud", "open project", ".pdf", ".docx")
    child_url_patterns: tuple[str, ...] = ()
    active_markers: tuple[str, ...] = ("project study", "project studies", "projektstudium", "projektstudien")
    archive_markers: tuple[str, ...] = ("archive", "completed", "past project", "abgeschlossen")
    excluded_markers: tuple[str, ...] = (
        "master thesis", "bachelor thesis", "internship", "job opening", "individual project",
        "masterarbeit", "bachelorarbeit", "praktikum", "stellenangebot", "idp",
    )

    def stable_key(self, source_url: str, title: str) -> str:
        normalized = " ".join(title.casefold().split())
        return hashlib.sha256(f"{self.slug}|{source_url}|{normalized}".encode()).hexdigest()[:32]


DEPARTMENTS = {
    "economics-policy": "Economics and Policy",
    "finance-accounting": "Finance and Accounting",
    "innovation-entrepreneurship": "Innovation and Entrepreneurship",
    "marketing-strategy-leadership": "Marketing, Strategy and Leadership",
    "operations-technology": "Operations and Technology",
}


def _slug(value: str) -> str:
    value = value.casefold().replace("&", " and ")
    return re.sub(r"^-+|-+$", "", re.sub(r"[^a-z0-9]+", "-", value))


def _family(url: str) -> str:
    host = urlparse(url).netloc.casefold()
    if host == "www.tumcso.com": return "squarespace"
    if host == "www.bwl.wi.tum.de": return "legacy_html"
    return "typo3"


def _inventory_path() -> Path:
    candidates = (Path(__file__).resolve().parents[3] / "tum_project_study_chairs.json", Path("tum_project_study_chairs.json"))
    for path in candidates:
        if path.is_file(): return path
    raise RuntimeError("tum_project_study_chairs.json is required for the chair registry")


def _load_registry() -> tuple[ChairAdapter, ...]:
    rows = json.loads(_inventory_path().read_text(encoding="utf-8"))
    required = {"department", "chair_name", "project_study_url"}
    if len(rows) != 32 or any(set(row) != required for row in rows):
        raise RuntimeError("Chair inventory must contain exactly 32 normalized records")
    audited_children = {
        "global-center-for-family-enterprise": ("/project_studies/",),
        "economics-of-energy-markets": ("/open-project-studies/",),
        "financial-accounting": ("projektstud", "project_study", "project-study"),
        "financial-management-and-capital-markets": ("/list-of-open-project-studies/",),
        "tum-entrepreneurship-research-institute": ("/news-single-view-project/article/project-study-",),
        "strategy-and-organization": ("/available-topics/projektstudium-",),
        "production-and-supply-chain-management": ("/project_studies/", "/project-study/"),
        "operations-management": ("mediatum.ub.tum.de/doc/",),
        "business-analytics-and-intelligent-systems": ("project_study_", "project-study-"),
        "management-of-digital-food-businesses": ("/project_studies/project_study_",),
    }
    known_direct = {"economics-of-innovation", "management-accounting", "corporate-governance-and-capital-markets-law",
                    "corporate-management", "controlling", "technology-and-innovation-management",
                    "family-business-culture-and-ownership", "digital-marketing"}
    adapters = tuple(ChairAdapter(
        slug=_slug(row["chair_name"]), name=row["chair_name"], department=row["department"],
        source_urls=(row["project_study_url"],), family=_family(row["project_study_url"]),
        child_url_patterns=audited_children.get(_slug(row["chair_name"]), ()),
        state=(SourceState.broken if row["chair_name"] == "Marketing and Technology" else
               SourceState.active if _slug(row["chair_name"]) in known_direct or _slug(row["chair_name"]) in audited_children else
               SourceState.empty),
    ) for row in rows)
    if len({a.slug for a in adapters}) != 32 or len({a.source_urls[0] for a in adapters}) != 32:
        raise RuntimeError("Chair slugs and source URLs must be unique")
    if set(a.department for a in adapters) != set(DEPARTMENTS.values()):
        raise RuntimeError("Unexpected department in chair inventory")
    return adapters


REGISTRY = _load_registry()
BY_SLUG = {adapter.slug: adapter for adapter in REGISTRY}
