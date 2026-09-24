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
    opportunity_type: str = "project_study"
    source_implies_active_type: bool = False
    state: SourceState = SourceState.needs_audit
    candidate_selectors: tuple[str, ...] = ("article", ".news-list-item", ".news-single", ".frame", ".accordion-item", "li")
    title_selector: str | None = None
    offer_link_selector: str | None = None
    classify_link_targets: bool = False
    child_link_markers: tuple[str, ...] = ("project stud", "projektstud", "open project", ".pdf", ".docx")
    child_url_patterns: tuple[str, ...] = ()
    active_markers: tuple[str, ...] = ("project study", "project studies", "projektstudium", "projektstudien")
    archive_markers: tuple[str, ...] = ("archive", "completed", "past project", "abgeschlossen")
    excluded_titles: tuple[str, ...] = ()
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
    "interdisciplinary-projects": "Interdisciplinary Projects",
}


def _slug(value: str) -> str:
    value = value.casefold().replace("&", " and ")
    return re.sub(r"^-+|-+$", "", re.sub(r"[^a-z0-9]+", "-", value))


def _family(url: str) -> str:
    host = urlparse(url).netloc.casefold()
    if host == "www.tumcso.com": return "squarespace"
    if host == "www.bwl.wi.tum.de": return "legacy_html"
    return "typo3"


def _inventory_path(filename: str) -> Path:
    candidates = (Path(__file__).resolve().parents[3] / filename, Path(filename))
    for path in candidates:
        if path.is_file(): return path
    raise RuntimeError(f"{filename} is required for the chair registry")


def _load_registry() -> tuple[ChairAdapter, ...]:
    rows = json.loads(_inventory_path("tum_project_study_chairs.json").read_text(encoding="utf-8"))
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
                    "corporate-management", "controlling", "technology-and-innovation-management", "marketing-and-technology",
                    "family-business-culture-and-ownership", "digital-marketing"}
    excluded_titles = {
        "Economics of Energy Markets": ("open project studies for students to apply",),
        "Production and Supply Chain Management": ("project study (projektstudium)",),
    }
    source_overrides = {
        "TUM Entrepreneurship Research Institute": {
            "candidate_selectors": ("div.article[data-testid='news-item']",),
            "title_selector": ".news-header-headline",
            "offer_link_selector": ".news-header-headline a",
        },
    }
    adapters = tuple(ChairAdapter(
        slug=_slug(row["chair_name"]), name=row["chair_name"], department=row["department"],
        source_urls=(row["project_study_url"],), family=_family(row["project_study_url"]),
        excluded_markers=(tuple(marker for marker in ChairAdapter.excluded_markers if marker != "idp")
                          if row["chair_name"] == "Marketing and Technology" else ChairAdapter.excluded_markers),
        child_url_patterns=audited_children.get(_slug(row["chair_name"]), ()),
        excluded_titles=excluded_titles.get(row["chair_name"], ()),
        state=(SourceState.active if _slug(row["chair_name"]) in known_direct or _slug(row["chair_name"]) in audited_children else
               SourceState.empty),
        **source_overrides.get(row["chair_name"], {}),
    ) for row in rows)
    if len({a.slug for a in adapters}) != 32 or len({a.source_urls[0] for a in adapters}) != 32:
        raise RuntimeError("Chair slugs and source URLs must be unique")
    if set(a.department for a in adapters) != set(DEPARTMENTS.values()) - {DEPARTMENTS["interdisciplinary-projects"]}:
        raise RuntimeError("Unexpected department in chair inventory")
    return adapters


REGISTRY = _load_registry()
BY_SLUG = {adapter.slug: adapter for adapter in REGISTRY}


IDP_HUB_URL = "https://www.cit.tum.de/en/cit/studies/degree-programs/master-informatics/interdisciplinary-project/"
IDP_MARKERS = ("idp", "interdisciplinary project", "interdisziplinäres projekt")
IDP_EXCLUDED_TITLES = {
    "Chair of Aerodynamics and Fluid Mechanics": ("interdisciplinary project (idp)",),
    "Chair of Financial Accounting": ("idp",),
    "Chair for Entrepreneurial Finance": ("idp: interdisciplinary project",),
    "Chair of Operations Management": ("ongoing idps", "open idps", "interdisciplinary projects (idp)"),
    "Chair of Operations Research": ("interdisciplinary project (idp)",),
    "Dr. Theo Schöller-Stiftungslehrstuhl für Technologie- und Innovationsmanagement": (
        "project studies and interdisciplinary projects (idps)",
    ),
    "Human-Centered Technologies for Learning": ("idp projects",),
    "Logistics and Supply Chain Management": ("theses, project studies idps",),
    "Production and Supply Chain Management": ("idp offers",),
    "Professorship of Business Analytics & Intelligent Systems": ("interdisciplinary projects (idps)",),
    "TUM Entrepreneurship Research Institute": (
        "project studies and interdisciplinary projects for informatics (idp)",
        "information for companies offering idps or project studies",
        "available project studies and idp",
    ),
}

IDP_SOURCE_OVERRIDES = {
    "Chair of Aerodynamics and Fluid Mechanics": {
        "candidate_selectors": ("table.ce-table tr",),
        "title_selector": "td a",
        "offer_link_selector": "td a",
        "classify_link_targets": True,
    },
    "Chair of Operations Management": {
        "candidate_selectors": ("li.list-group-item.e2e-item",),
        "title_selector": ".publication-title",
        "offer_link_selector": "a.full",
        "archive_markers": (*ChairAdapter.archive_markers, "ongoing idps"),
    },
    "TUM Entrepreneurship Research Institute": {
        "candidate_selectors": ("div.article[data-testid='news-item']",),
        "title_selector": ".news-header-headline",
        "offer_link_selector": ".news-header-headline a",
    },
}


def _load_idp_registry() -> tuple[ChairAdapter, ...]:
    """Load the chair links published by the official Informatics IDP hub.

    These sources are intentionally a separate, versioned inventory: the hub is an
    announcement source itself, while individual chairs remain responsible for
    their own narrowly scoped pages.
    """
    rows = json.loads(_inventory_path("tum_idp_sources.json").read_text(encoding="utf-8"))
    required = {"chair_name", "idp_url"}
    if any(set(row) != required for row in rows):
        raise RuntimeError("IDP inventory contains invalid records")
    hub = ChairAdapter(
        slug="informatics-idp-hub", name="Informatics IDP Hub", department=DEPARTMENTS["interdisciplinary-projects"],
        source_urls=(IDP_HUB_URL,), family="typo3", opportunity_type="idp", source_implies_active_type=True,
        # Offer links are extracted directly from the hub page.  Do not download
        # every linked PDF during a daily listing crawl.
        candidate_selectors=(".ce-uploads li",),
        active_markers=IDP_MARKERS,
        excluded_markers=tuple(marker for marker in ChairAdapter.excluded_markers if marker != "idp"),
    )
    chairs = tuple(ChairAdapter(
        slug=f"idp-{_slug(row['chair_name'])}", name=row["chair_name"], department=DEPARTMENTS["interdisciplinary-projects"],
        source_urls=(row["idp_url"],), family=_family(row["idp_url"]), opportunity_type="idp",
        active_markers=IDP_MARKERS,
        excluded_titles=IDP_EXCLUDED_TITLES.get(row["chair_name"], ()),
        excluded_markers=tuple(marker for marker in ChairAdapter.excluded_markers if marker != "idp"),
        state=SourceState.active,
        **IDP_SOURCE_OVERRIDES.get(row["chair_name"], {}),
    ) for row in rows)
    adapters = (hub, *chairs)
    if len(adapters) != 31 or len({adapter.slug for adapter in adapters}) != len(adapters):
        raise RuntimeError("IDP inventory must contain the hub and 30 unique chair records")
    return adapters


IDP_REGISTRY = _load_idp_registry()
ALL_REGISTRY = (*REGISTRY, *IDP_REGISTRY)
ALL_BY_SLUG = {adapter.slug: adapter for adapter in ALL_REGISTRY}
