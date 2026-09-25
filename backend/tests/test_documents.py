from pathlib import Path

import pymupdf

from app.ingestion.documents import extract, html_text, pdf_text

FIXTURE_PDF = next(Path(__file__).parent.glob("fixtures/chairs/*/*.pdf"))


def test_html_text_discards_active_content():
    result = html_text(b"<h1>Project Study</h1><script>ignore me</script><p>Apply now</p>")
    assert result == "Project Study\nApply now"


def test_unknown_document_type_is_rejected():
    try: extract(b"x", "application/x-unknown")
    except ValueError as error: assert "Unsupported" in str(error)
    else: raise AssertionError("must reject unknown formats")


def test_pdf_text_extracts_markdown_with_page_markers():
    text = extract(FIXTURE_PDF.read_bytes(), "application/pdf")
    assert "<!-- page 1 -->" in text


def test_pdf_text_keeps_usable_short_text_across_pages():
    with pymupdf.open() as doc:
        doc.new_page().insert_text((72, 72), "Project text on the first page.")
        doc.new_page().insert_text((72, 72), "Project text on the next page.")
        data = doc.tobytes()

    text = pdf_text(data)
    assert "<!-- page 1 -->" in text
    assert "<!-- page 2 -->" in text
    assert "Project text" in text
