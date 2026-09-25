"""Check model citations against the extracted PDF pages without exposing document text."""
from __future__ import annotations

import html
import re

from .project_profile import (DocumentExtraction, Evidence, EvidenceIssue, ListField, ProgrammingSkill,
                              ProgrammingWork, TextField, WorkLocationMode)

ASSESSMENTS = (ProgrammingWork, ProgrammingSkill, WorkLocationMode)


def _normalize_quote(text: str) -> str:
    text = html.unescape(text)
    text = re.sub(r"<[^>]+>", "", text)
    # Line-start Markdown marks and bullet glyphs; "−" (U+2212) starts list lines in the FIT PDF.
    text = re.sub(r"(?m)^[ \t]*[#>*\-−▪•]+[ \t]*", "", text)
    text = re.sub(r"[*_`]", "", text)
    # Removing bold marks leaves "**Label** :" as "Label :", while models quote "Label:".
    text = re.sub(r"\s+([:;,.!?])", r"\1", text)
    # Models may quote the source's straight quotation marks as typographic ones.
    text = re.sub(r"[“”„]", '"', re.sub(r"[‘’‚]", "'", text))
    return " ".join(text.casefold().split())


def check_profile_evidence(document: DocumentExtraction, pages: list[str]) -> list[EvidenceIssue]:
    """Flag invalid page numbers, quotes absent from their cited page, and quotes cited from
    pages outside the offer's own source_pages (a sign of facts leaking between offers)."""
    normalized_pages = [_normalize_quote(page) for page in pages]
    issues: list[EvidenceIssue] = []

    for offer_index, offer in enumerate(document.offers):
        own_pages = set(offer.source_pages)
        for page in sorted(own_pages):
            if page > len(pages):
                issues.append(EvidenceIssue(offer_index=offer_index, field="source_pages",
                                            page=page, reason="page_out_of_range"))

        def check(field_name: str, item_index: int | None, evidence: Evidence) -> None:
            def issue(reason: str) -> EvidenceIssue:
                return EvidenceIssue(offer_index=offer_index, field=field_name, item_index=item_index,
                                     page=evidence.page, reason=reason)
            if evidence.page > len(pages):
                issues.append(issue("page_out_of_range"))
                return
            if _normalize_quote(evidence.excerpt) not in normalized_pages[evidence.page - 1]:
                issues.append(issue("quote_not_found"))
            if evidence.page not in own_pages:
                issues.append(issue("outside_offer_pages"))

        for field_name in type(offer).model_fields:
            field = getattr(offer, field_name)
            if isinstance(field, (TextField, *ASSESSMENTS)):
                for evidence in field.evidence:
                    check(field_name, None, evidence)
            elif isinstance(field, ListField):
                for item_index, item in enumerate(field.items):
                    for evidence in item.evidence:
                        check(field_name, item_index, evidence)
    return issues
