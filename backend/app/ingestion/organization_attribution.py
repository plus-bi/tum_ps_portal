"""Conservative organization candidates from stored, page-addressable PDF text."""
from __future__ import annotations

import re
import unicodedata
from typing import Literal

from pydantic import BaseModel

from .project_profile import Evidence, ProjectProfile
from .registry import ALL_REGISTRY

EXTRACTOR_VERSION = "pdf-organization-v1"


class OrganizationMention(BaseModel):
    name: str
    canonical_name: str | None = None
    evidence: Evidence
    method: Literal["registered_name", "header_pattern", "profile_provider"]


class OrganizationCandidates(BaseModel):
    academic_units: list[OrganizationMention] = []
    project_partners: list[OrganizationMention] = []


def _key(value: str) -> str:
    value = "".join(char for char in unicodedata.normalize("NFKD", value.casefold())
                    if not unicodedata.combining(char))
    return " ".join(re.findall(r"[a-z0-9]+", value))


UNIT_NAMES = tuple(sorted({adapter.name for adapter in ALL_REGISTRY
                           if adapter.slug != "informatics-idp-hub"}, key=len, reverse=True))
UNIT_BY_KEY = {_key(name): name for name in UNIT_NAMES}
UNIT_ALIASES = {
    "iwb": "Institute for Machine Tools and Industrial Management",
    "institut fur werkzeugmaschinen und betriebswissenschaften iwb":
        "Institute for Machine Tools and Industrial Management",
    "institut fur werkzeugmaschinen und betriebswissenschaften":
        "Institute for Machine Tools and Industrial Management",
}
ACADEMIC_PATTERN = re.compile(
    r"\b(?:Chair of|Chair for|Lehrstuhl f[üu]r|Professorship of|Institute for|Institute of|Institut f[üu]r)\s+",
    re.IGNORECASE,
)
ACADEMIC_HINT = re.compile(r"\b(?:chair|lehrstuhl|institute|institut|professorship)\b", re.IGNORECASE)
HEADER_STOP = re.compile(
    r"\b(?:TUM School|Technical University|Technische Universit[aä]t|Fakult[aä]t|Faculty|Department|"
    r"School of|School of Enginnering|Engineering and Design|Wissenschaftszentrum|der TU|at the|zu vergeben|"
    r"Prof\. Dr\.|Interdisciplinary Project|IDP Project|Semester Thesis)\b|https?://|[:#]",
    re.IGNORECASE,
)


def _canonical(name: str) -> str | None:
    key = _key(name)
    return UNIT_BY_KEY.get(key) or UNIT_ALIASES.get(key)


def _clean_line(line: str) -> str:
    line = re.sub(r"<[^>]+>", " ", line)
    line = re.sub(r"[*_`#]", " ", line)
    return " ".join(line.split())


def _append_unique(items: list[OrganizationMention], mention: OrganizationMention) -> None:
    key = _key(mention.canonical_name or mention.name)
    if key and not any(_key(item.canonical_name or item.name) == key for item in items):
        items.append(mention)


def extract_organization_candidates(pages: list[str], offer: ProjectProfile | None) -> OrganizationCandidates:
    """Return cited candidates only; a reviewer must approve them before public use."""
    result = OrganizationCandidates()
    if pages and pages[0]:
        for raw_line in pages[0][:1500].splitlines()[:24]:
            line = _clean_line(raw_line)
            if not line:
                continue
            matching = next((name for name in UNIT_NAMES if re.search(rf"(?<!\w){re.escape(name)}(?!\w)", line, re.I)), None)
            if matching:
                position = line.casefold().find(matching.casefold())
                excerpt = line[max(0, position - 25):position + len(matching) + 35]
                _append_unique(result.academic_units, OrganizationMention(
                    name=matching, canonical_name=matching, evidence=Evidence(page=1, excerpt=excerpt),
                    method="registered_name"))
                continue
            match = ACADEMIC_PATTERN.search(line)
            if not match:
                continue
            remainder = HEADER_STOP.split(line[match.start():], maxsplit=1)[0]
            name = remainder.strip(" :-–—,.;")
            if 8 <= len(name) <= 110:
                _append_unique(result.academic_units, OrganizationMention(
                    name=name, canonical_name=_canonical(name), evidence=Evidence(page=1, excerpt=name),
                    method="header_pattern"))
    if offer and offer.provider_name.stated and offer.provider_name.value:
        name = offer.provider_name.value.strip()
        evidence = offer.provider_name.evidence[0]
        mention = OrganizationMention(name=name, canonical_name=_canonical(name), evidence=evidence,
                                      method="profile_provider")
        target = (result.academic_units if mention.canonical_name or ACADEMIC_HINT.search(name)
                  else result.project_partners)
        _append_unique(target, mention)
    return result
