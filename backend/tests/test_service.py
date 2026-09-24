from datetime import date
from app.ingestion.service import publication_from_title


def test_publication_date_is_removed_from_display_title():
    title, published = publication_from_title("Project Study at Example (published at 13/04/2026)")
    assert title == "Project Study at Example"
    assert published == date(2026, 4, 13)


def test_leading_bracketed_publication_date_is_parsed_from_title():
    title, published = publication_from_title("[22.07.2026] Development and Evaluation of AI Agents")
    assert title == "Development and Evaluation of AI Agents"
    assert published == date(2026, 7, 22)

def test_title_without_date_remains_undated():
    assert publication_from_title("Project Study @NetZero") == ("Project Study @NetZero", None)
