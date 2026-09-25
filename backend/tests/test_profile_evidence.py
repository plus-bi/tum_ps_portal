from app.ingestion.profile_evidence import check_profile_evidence
from app.ingestion.project_profile import Contact, Evidence, ListField, ProgrammingWork, SourcedValue, TextField
from profile_builders import document, empty_offer


def test_evidence_is_checked_per_item_and_against_its_page():
    offer = empty_offer(subjects=ListField[str](stated=True, items=[
        SourcedValue[str](value="Data", evidence=[Evidence(page=1, excerpt="Data")]),
        SourcedValue[str](value="Python", evidence=[Evidence(page=2, excerpt="Python")]),
        SourcedValue[str](value="Robotics", evidence=[Evidence(page=1, excerpt="Robotics")]),
    ]))

    issues = check_profile_evidence(document(offer), ["# **Data** project"])
    assert [(issue.offer_index, issue.item_index, issue.reason) for issue in issues] == [
        (0, 1, "page_out_of_range"), (0, 2, "quote_not_found"),
    ]


def test_evidence_normalization_accepts_visible_text_inside_html_tags():
    offer = empty_offer(start_date=TextField(stated=True, value="1st of October", evidence=[
        Evidence(page=1, excerpt="1st of October"),
    ]))
    assert check_profile_evidence(document(offer), ["1<sup>st</sup> of October"]) == []


def test_evidence_normalization_ignores_space_left_before_punctuation_by_bold_marks():
    # Observed on a JAX-Fluids IDP: the Markdown had "**Testing differentiability** :".
    offer = empty_offer(activities=ListField[str](stated=True, items=[SourcedValue[str](
        value="Test differentiability",
        evidence=[Evidence(page=1, excerpt="Testing differentiability: An essential goal")])]))
    pages = ["4. **Testing differentiability** : An essential goal is to ensure"]
    assert check_profile_evidence(document(offer), pages) == []


def test_evidence_normalization_accepts_typographic_quotation_marks():
    # Observed on the Fraunhofer FIT PDF: the model quoted straight quotes as typographic ones.
    offer = empty_offer(application_areas=ListField[str](stated=True, items=[SourcedValue[str](
        value="Privacy-preserving matching",
        evidence=[Evidence(page=1, excerpt="such a “matching” of offers and queries")])]))
    pages = ['With privacy preserving computing technologies, such a "matching" of offers and queries could happen']
    assert check_profile_evidence(document(offer), pages) == []


def test_evidence_normalization_ignores_bullet_glyphs_between_list_lines():
    # Observed on the Fraunhofer FIT PDF: one sentence split over two bold list lines, the second
    # starting with a minus sign (U+2212).
    offer = empty_offer(application_instructions=TextField(stated=True, value="Apply by mail", evidence=[
        Evidence(page=1, excerpt="short motivation letter, CVs and Transcripts of records via mail to")]))
    pages = ["- **short motivation letter, CVs and** \n\n− **Transcripts of records via mail to** **<u>a@b.de</u>**"]
    assert check_profile_evidence(document(offer), pages) == []


def test_evidence_stitched_across_interleaved_columns_is_still_flagged():
    # Observed on a thesis poster: the model rejoined a list the Markdown splits with a column heading.
    offer = empty_offer(subjects=ListField[str](stated=True, items=[SourcedValue[str](
        value="Control", evidence=[Evidence(page=1, excerpt="Positions in: Perception, Planning, Control")])]))
    pages = ["Positions in: Perception, Planning, **WHAT:** Control, Simulation"]
    assert [issue.reason for issue in check_profile_evidence(document(offer), pages)] == ["quote_not_found"]


def test_evidence_outside_an_offers_pages_is_flagged_as_possible_leakage():
    first = empty_offer(source_pages=[1], contacts=ListField[Contact](stated=True, items=[SourcedValue[Contact](
        value=Contact(name=None, email="b@example.org"), evidence=[Evidence(page=2, excerpt="b@example.org")])]))
    second = empty_offer(source_pages=[2], programming_performed=ProgrammingWork(
        level="central", evidence=[Evidence(page=2, excerpt="implement")]))
    issues = check_profile_evidence(document(first, second), ["Offer A: a@example.org", "Offer B: implement, b@example.org"])
    assert [(issue.offer_index, issue.field, issue.reason) for issue in issues] == [
        (0, "contacts", "outside_offer_pages"),
    ]


def test_source_pages_beyond_the_document_are_flagged():
    issues = check_profile_evidence(document(empty_offer(source_pages=[1, 3])), ["Offer"])
    assert [(issue.field, issue.page, issue.reason) for issue in issues] == [("source_pages", 3, "page_out_of_range")]


def subject_quoted(excerpt: str):
    return document(empty_offer(subjects=ListField[str](stated=True, items=[SourcedValue[str](
        value="Topic", evidence=[Evidence(page=1, excerpt=excerpt)])])))


def test_evidence_matches_words_split_by_spurious_strikethrough_marks():
    # Observed on an IDP flyer whose Type3 font made pymupdf4llm mark "t" and "f" glyphs as struck out.
    pages = ["## So ~~ft~~ ware Engineering Projec ~~t~~ \n\nWe deliver ~~f~~ as ~~t~~ & reliable answers"]
    assert check_profile_evidence(subject_quoted("Software Engineering Project"), pages) == []
    assert check_profile_evidence(subject_quoted("We deliver fast & reliable answers"), pages) == []


def test_evidence_matches_ligatures_the_text_layer_could_not_map():
    # Observed on a Word-exported Calibri PDF: "ti" and "tt" ligatures arrive as U+0018 or U+FFFD.
    pages = ["improving the computa\x18onal \x18mes for laypeople with li�le experience"]
    assert check_profile_evidence(subject_quoted("improving the computational times"), pages) == []
    assert check_profile_evidence(subject_quoted("laypeople with little experience"), pages) == []
    assert len(check_profile_evidence(subject_quoted("improving the computational costs"), pages)) == 1


def test_evidence_matches_spacing_diaeresis_private_use_glyphs_and_table_cells():
    # Observed as "Str¨omung" (separate diaeresis) and a private-use glyph for the dash in "2-4".
    pages = ["Grundkenntnisse in Str¨omungsmechanik und Ans¨atze<br>für 2\ue0884 Studierende | Python |"]
    assert check_profile_evidence(subject_quoted("Grundkenntnisse in Strömungsmechanik"), pages) == []
    assert check_profile_evidence(subject_quoted("für 2–4 Studierende Python"), pages) == []


def test_short_quotes_still_need_an_exact_match():
    pages = ["We trust our partners"]
    assert len(check_profile_evidence(subject_quoted("trus tour"), pages)) == 1
    assert check_profile_evidence(subject_quoted("We trus tour partners"), pages) == []
