from pathlib import Path

import pymupdf
import pymupdf4llm

from app.ingestion.pdf_reader import read_pdf, render_for_llm

FIXTURE_PDF = next(Path(__file__).parent.glob("fixtures/chairs/*/*.pdf"))


def test_read_pdf_classifies_digital_native_fixture():
    result = read_pdf(FIXTURE_PDF.read_bytes())
    assert result.classification == "digital_native"
    assert result.pages and all(page.strip() for page in result.pages)


def test_render_for_llm_marks_each_page():
    rendered = render_for_llm(["first", "second"])
    assert rendered == "<!-- page 1 -->\n\nfirst\n\n<!-- page 2 -->\n\nsecond"


def test_read_pdf_classifies_native_text_even_when_markdown_is_long(monkeypatch):
    with pymupdf.open() as doc:
        doc.new_page().insert_text((72, 72), "short text")
        data = doc.tobytes()
    monkeypatch.setattr(pymupdf4llm, "to_markdown", lambda doc, page_chunks: [{"text": "# " + "x" * 100}])

    result = read_pdf(data)
    assert result.classification == "scanned"
    assert result.pages_with_usable_text == 0
    assert result.pages[0].startswith("# ")
