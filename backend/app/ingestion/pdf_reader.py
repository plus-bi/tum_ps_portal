"""Single PyMuPDF-based reader shared by PDF classification and markdown extraction.

Opens each PDF once and derives both the text-layer classification (digital_native /
scanned / mixed) and per-page markdown from the same pass, instead of reading the file
twice with two different libraries.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

USEFUL_TEXT_THRESHOLD = 40
# A page whose visible characters are mostly glyph codes without a Unicode mapping (control
# characters, U+FFFD, private use) has an unreadable text layer and needs OCR like a scan.
UNMAPPED_GLYPH = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f\ufffd\ue000-\uf8ff]")
MAX_UNMAPPED_SHARE = 0.3


@dataclass(frozen=True)
class PdfPages:
    pages: list[str]
    classification: str
    pages_with_usable_text: int
    native_text_length: int
    unreadable_pages: list[int]


def read_pdf(data: bytes) -> PdfPages:
    import pymupdf
    import pymupdf4llm

    with pymupdf.open(stream=data, filetype="pdf") as doc:
        native_text = [page.get_text() or "" for page in doc]
        chunks = pymupdf4llm.to_markdown(doc, page_chunks=True)
    if len(chunks) != len(native_text):
        raise ValueError("Markdown page count does not match PDF page count")
    unreadable = [number for number, page in enumerate(native_text, start=1) if is_unreadable(page)]
    # Unreadable pages are stored blank, so downstream coverage treats them like scanned pages.
    pages = ["" if number in unreadable else chunk["text"] for number, chunk in enumerate(chunks, start=1)]
    useful_pages = sum(len(page.strip()) >= USEFUL_TEXT_THRESHOLD
                       for number, page in enumerate(native_text, start=1) if number not in unreadable)
    classification = ("scanned" if useful_pages == 0
                       else "digital_native" if useful_pages == len(pages) else "mixed")
    return PdfPages(pages=pages, classification=classification,
                    pages_with_usable_text=useful_pages,
                    native_text_length=sum(len(page.strip()) for number, page in enumerate(native_text, start=1)
                                           if number not in unreadable),
                    unreadable_pages=unreadable)


def is_unreadable(text: str) -> bool:
    visible = [char for char in text if not char.isspace()]
    return bool(visible) and len(UNMAPPED_GLYPH.findall(text)) / len(visible) > MAX_UNMAPPED_SHARE


def render_for_llm(pages: list[str]) -> str:
    """Join per-page markdown with an explicit page marker so a model can cite page numbers."""
    return "\n\n".join(f"<!-- page {number} -->\n\n{text}" for number, text in enumerate(pages, start=1))
