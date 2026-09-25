"""Check model citations against the extracted PDF pages without exposing document text."""
from __future__ import annotations

import html
import re
import unicodedata

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


# Glyphs the PDF text layer could not map to Unicode: control characters, U+FFFD and private-use
# codepoints. Broken "ti"/"tt" ligatures in Word-exported Calibri PDFs arrive as \x18 or U+FFFD.
UNMAPPED_GLYPH = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f\ufffd\ue000-\uf8ff]")
LIGATURES = ("ffi", "ffl", "ff", "fi", "fl", "ft", "fj", "tt", "ti", "tf", "th")
SPACING_DIACRITICS = {"\u00a8": "\u0308", "\u00b4": "\u0301"}  # "¨o" -> "ö", "´e" -> "é"
MIN_FOLDED_CHARS = 12  # shorter quotes need an exact match: letters alone would match inside other words


def _fold(text: str) -> str:
    """Letters and digits only, casefolded, after undoing PDF text-layer artifacts: "~~" strikethrough
    marks that split words ("So ~~ft~~ ware"), HTML tags such as <br> and <sup>, table pipes, spacing diacritics before a letter
    ("¨o"), and compatibility forms ("²"). Unmapped glyphs become \\x00 placeholders."""
    text = re.sub(r"<[^>]+>", " ", html.unescape(text))
    text = re.sub(r"\s*~~\s*", "", text)
    text = re.sub("([\u00a8\u00b4])\\s*([A-Za-z])", lambda m: m.group(2) + SPACING_DIACRITICS[m.group(1)], text)
    text = unicodedata.normalize("NFKC", text)
    text = UNMAPPED_GLYPH.sub("\x00", text)
    return "".join(char for char in text.casefold() if char.isalnum() or char == "\x00")


def _folded_pattern(folded_quote: str) -> re.Pattern:
    """Lets a placeholder on the page stand for one ligature in the quote."""
    pattern, position = [], 0
    while position < len(folded_quote):
        ligature = next((lig for lig in LIGATURES if folded_quote.startswith(lig, position)), None)
        if ligature:
            pattern.append(f"(?:{re.escape(ligature)}|\x00)")
            position += len(ligature)
        else:
            pattern.append(re.escape(folded_quote[position]))
            position += 1
    return re.compile("".join(pattern))


def _quote_on_page(excerpt: str, normalized_page: str, folded_page: str) -> bool:
    if _normalize_quote(excerpt) in normalized_page:
        return True
    folded = _fold(excerpt)
    if len(folded) < MIN_FOLDED_CHARS:
        return False
    if folded in folded_page:
        return True
    if "\x00" not in folded_page:
        return False
    # A placeholder stands either for punctuation the quote drops ("2\ue0884" for "2-4") or for a ligature.
    return folded in folded_page.replace("\x00", "") or _folded_pattern(folded).search(folded_page) is not None


def check_profile_evidence(document: DocumentExtraction, pages: list[str]) -> list[EvidenceIssue]:
    """Flag invalid page numbers, quotes absent from their cited page, and quotes cited from
    pages outside the offer's own source_pages (a sign of facts leaking between offers)."""
    normalized_pages = [_normalize_quote(page) for page in pages]
    folded_pages = [_fold(page) for page in pages]
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
            if not _quote_on_page(evidence.excerpt, normalized_pages[evidence.page - 1], folded_pages[evidence.page - 1]):
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
