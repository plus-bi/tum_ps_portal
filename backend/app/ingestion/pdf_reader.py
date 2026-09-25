"""Single PyMuPDF-based reader shared by PDF classification and markdown extraction.

Opens each PDF once and derives both the text-layer classification (digital_native /
scanned / mixed) and per-page markdown from the same pass, instead of reading the file
twice with two different libraries.
"""
from __future__ import annotations

from dataclasses import dataclass

USEFUL_TEXT_THRESHOLD = 40


@dataclass(frozen=True)
class PdfPages:
    pages: list[str]
    classification: str
    pages_with_usable_text: int
    native_text_length: int


def read_pdf(data: bytes) -> PdfPages:
    import pymupdf
    import pymupdf4llm

    with pymupdf.open(stream=data, filetype="pdf") as doc:
        native_text = [page.get_text() or "" for page in doc]
        chunks = pymupdf4llm.to_markdown(doc, page_chunks=True)
    if len(chunks) != len(native_text):
        raise ValueError("Markdown page count does not match PDF page count")
    pages = [chunk["text"] for chunk in chunks]
    useful_pages = sum(len(page.strip()) >= USEFUL_TEXT_THRESHOLD for page in native_text)
    classification = ("scanned" if useful_pages == 0
                       else "digital_native" if useful_pages == len(pages) else "mixed")
    return PdfPages(pages=pages, classification=classification,
                    pages_with_usable_text=useful_pages,
                    native_text_length=len("\n".join(native_text).strip()))


def render_for_llm(pages: list[str]) -> str:
    """Join per-page markdown with an explicit page marker so a model can cite page numbers."""
    return "\n\n".join(f"<!-- page {number} -->\n\n{text}" for number, text in enumerate(pages, start=1))
