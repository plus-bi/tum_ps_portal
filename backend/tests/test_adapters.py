import pytest
from app.ingestion.adapters import parser_for
from app.ingestion.registry import REGISTRY


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
