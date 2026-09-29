"""Conservative, source-backed catalog filter values from one extracted offer."""
from __future__ import annotations

import re
import unicodedata
from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel

from .ingestion.project_profile import DocumentExtraction, ProjectProfile, WorkMode


class ProfileFilterValues(BaseModel):
    degree_level: list[Literal["bachelor", "master", "any"]] | None = None
    work_modes: list[WorkMode] | None = None
    programming_performed: Literal["none", "some", "central", "unknown"] = "unknown"
    programming_required: Literal["required", "recommended", "not_stated"] = "not_stated"
    work_location_mode: Literal["on_site", "hybrid", "remote", "unknown"] = "unknown"
    working_language: list[Literal["en", "de", "other"]] | None = None


FILTER_FIELDS = frozenset(ProfileFilterValues.model_fields)


def available_fields() -> list[str]:
    """The six structured profile filters are always available in the catalog."""
    return sorted(FILTER_FIELDS)


def local_preview_enabled(preview: bool, public_url: str) -> bool:
    return preview and urlparse(public_url).hostname in {"localhost", "127.0.0.1", "::1"}


def _normalized_title(value: str) -> str:
    folded = unicodedata.normalize("NFKD", value.casefold())
    return " ".join(re.findall(r"[a-z0-9]+", folded))


def offer_for_listing(document: DocumentExtraction, listing_title: str) -> ProjectProfile | None:
    """Never assign a PDF's other offers to a listing with an ambiguous title."""
    if len(document.offers) == 1:
        return document.offers[0]
    title = _normalized_title(listing_title)
    matches = [offer for offer in document.offers
               if offer.title.stated and _normalized_title(offer.title.value or "") == title]
    return matches[0] if len(matches) == 1 else None


_ENGLISH = re.compile(r"\b(?:english|englisch)\b", re.IGNORECASE)
_GERMAN = re.compile(r"\b(?:german|deutsch)\b", re.IGNORECASE)
_OTHER_LANGUAGE = re.compile(
    r"\b(?:french|français|französisch|spanish|español|spanisch|italian|italiano|italienisch|"
    r"chinese|mandarin|chinesisch|arabic|arabisch|portuguese|portugiesisch|russian|russisch)\b",
    re.IGNORECASE,
)


def normalize_working_languages(values: list[str] | None) -> list[Literal["en", "de", "other"]] | None:
    if values is None:
        return None
    found: set[Literal["en", "de", "other"]] = set()
    for value in values:
        en = bool(_ENGLISH.search(value))
        de = bool(_GERMAN.search(value))
        if en:
            found.add("en")
        if de:
            found.add("de")
        if _OTHER_LANGUAGE.search(value) or not en and not de:
            found.add("other")
    return [code for code in ("en", "de", "other") if code in found]


def values_from_offer(offer: ProjectProfile) -> ProfileFilterValues:
    return ProfileFilterValues(
        degree_level=[item.value.value for item in offer.degree_level.items] if offer.degree_level.stated else None,
        work_modes=[item.value.value for item in offer.work_modes.items] if offer.work_modes.stated else None,
        programming_performed=offer.programming_performed.level,
        programming_required=offer.programming_required.level,
        work_location_mode=offer.work_location_mode.level,
        working_language=normalize_working_languages(
            [item.value for item in offer.working_language.items] if offer.working_language.stated else None),
    )
