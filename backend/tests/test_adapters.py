import pytest
from app.ingestion.adapters import parser_for
from app.ingestion.registry import IDP_REGISTRY, REGISTRY


@pytest.mark.parametrize("adapter", REGISTRY, ids=lambda adapter: adapter.slug)
def test_every_chair_has_fixture_backed_discovery_contract(adapter):
    html = f"""<html><body><nav>Project Study navigation</nav>
    <article><h2>{adapter.name}: Project Study – Data Opportunity</h2>
    <p>Applications are open for this Project Study.</p><a href='/apply/{adapter.slug}.pdf'>Details</a></article>
    <article><h2>Master thesis</h2><p>Not available.</p></article>
    <section><h2>Completed Project Studies archive</h2><article><h3>Old offer</h3></article></section>
    </body></html>""".encode()
    candidates = parser_for(adapter).discover(adapter, adapter.source_urls[0], html)
    assert len(candidates) == 1
    assert adapter.name in candidates[0].title
    assert candidates[0].application_url.endswith(f"/apply/{adapter.slug}.pdf")


def test_project_study_modalities_heading_is_not_an_offer():
    adapter = next(adapter for adapter in REGISTRY if adapter.slug == "marketing-and-technology")
    html = b"<html><body><article><h2>Modalities of the Project Study/IDP</h2><p>General information.</p></article></body></html>"
    assert parser_for(adapter).discover(adapter, adapter.source_urls[0], html) == []


def test_informatics_idp_hub_accepts_announced_pdf_even_when_its_title_omits_idp():
    adapter = IDP_REGISTRY[0]
    html = b'''<html><body><ul class="ce-uploads"><li><a href="/fileadmin/w00byx/cit/IDP/offer.pdf">[01.09.2026] Human interaction in physical workspaces</a></li></ul></body></html>'''
    candidates = parser_for(adapter).discover(adapter, adapter.source_urls[0], html)
    assert len(candidates) == 1
    assert candidates[0].title.endswith("physical workspaces")
    assert candidates[0].source_url.endswith("offer.pdf")


def test_idp_adapter_rejects_thesis_only_content():
    adapter = IDP_REGISTRY[1]
    html = b"<article><h2>Master thesis: data science</h2><a href='/thesis.pdf'>Details</a></article>"
    assert parser_for(adapter).discover(adapter, adapter.source_urls[0], html) == []


def test_entrepreneurial_finance_rejects_generic_idp_invitation_but_keeps_offer():
    adapter = next(adapter for adapter in IDP_REGISTRY if adapter.slug == "idp-chair-for-entrepreneurial-finance")
    html = b"""<html><body>
    <article><h2>IDP: Interdisciplinary Project</h2>
    <p>The chair welcomes computer science students to complete their IDP with us.</p></article>
    <article><h2>MEDTANK: Interdisciplinary project for informatics (IDP)</h2>
    <a href='/fileadmin/ef/IDP/IDP_MEDTANK.pdf'>Project description</a></article>
    </body></html>"""

    candidates = parser_for(adapter).discover(adapter, adapter.source_urls[0], html)

    assert [candidate.title for candidate in candidates] == ["MEDTANK: Interdisciplinary project for informatics (IDP)"]


def test_tim_rejects_generic_overview_but_keeps_individual_idp():
    adapter = next(adapter for adapter in IDP_REGISTRY if adapter.slug.startswith("idp-dr-theo-sch-ller"))
    html = b"""<html><body>
    <article><h2>Project Studies and Interdisciplinary Projects (IDPs)</h2>
    <p>This page is primarily intended for students looking for an IDP or Project Study at our chair.</p></article>
    <article><h2>IDP Agentic Document Processing &amp; Development</h2>
    <a href='/tim/teaching/project-studiesidp/agentic-document-processing/'>Details</a></article>
    </body></html>"""

    candidates = parser_for(adapter).discover(adapter, adapter.source_urls[0], html)

    assert [candidate.title for candidate in candidates] == ["IDP Agentic Document Processing & Development"]
