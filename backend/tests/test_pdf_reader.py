from pathlib import Path

import pymupdf
import pymupdf4llm

from app.ingestion.pdf_reader import is_unreadable, read_pdf, render_for_llm

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


def test_pages_of_unmapped_glyph_codes_are_blank_and_need_ocr(monkeypatch):
    # Observed on an e-truck charging PDF whose fonts map every glyph to control characters.
    with pymupdf.open() as doc:
        doc.new_page().insert_text((72, 72), "readable project description " * 3)
        doc.new_page().insert_text((72, 72), "placeholder")
        data = doc.tobytes()
    garbled = "\x12\x15\x0e\r\x0f\x10FK\x15\x0e\x11\x0b\x0c\x13\x0e\x17 F \x16FE\x19\x15\x0e\r\x12F"
    monkeypatch.setattr(pymupdf.Page, "get_text", lambda page, *a, **k: "readable project description " * 3
                        if page.number == 0 else garbled)
    monkeypatch.setattr(pymupdf4llm, "to_markdown", lambda doc, page_chunks: [{"text": "Readable"}, {"text": garbled}])

    result = read_pdf(data)
    assert result.unreadable_pages == [2]
    assert result.pages == ["Readable", ""]
    assert result.classification == "mixed"


def test_occasional_unmapped_ligatures_leave_a_page_readable():
    assert not is_unreadable("improving the computa\x18onal \x18mes for laypeople")
    assert is_unreadable("\x12\x15\x0e\r\x0f\x10FK\x15\x0e\x11")
