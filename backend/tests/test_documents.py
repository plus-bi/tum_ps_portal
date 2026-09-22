from app.ingestion.documents import html_text, extract


def test_html_text_discards_active_content():
    result = html_text(b"<h1>Project Study</h1><script>ignore me</script><p>Apply now</p>")
    assert result == "Project Study\nApply now"


def test_unknown_document_type_is_rejected():
    try: extract(b"x", "application/x-unknown")
    except ValueError as error: assert "Unsupported" in str(error)
    else: raise AssertionError("must reject unknown formats")
