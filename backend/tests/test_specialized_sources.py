import asyncio
from pathlib import Path

import httpx
from sqlalchemy import create_engine, select

import app.db as db
from app.db import Base, Listing
from app.ingestion.adapters import parser_for
from app.ingestion.fetcher import PoliteFetcher
from app.ingestion.live import discover_adapter, ingest_live
from app.ingestion.registry import ALL_BY_SLUG, IDP_ENERGY_WIKI_URL, IDP_HCTL_PROJECTS_URL


class AllowRobots:
    def require_allowed(self, url):
        pass


def test_data_innovation_lab_is_other_and_only_current_cards_are_listed():
    adapter = ALL_BY_SLUG["other-tum-data-innovation-lab"]
    page = (Path(__file__).parent / "fixtures/chairs/idp-tum-data-innovation-lab.html").read_bytes()
    candidates = parser_for(adapter).discover(adapter, adapter.source_urls[0], page)
    assert adapter.opportunity_type == "other"
    assert len(candidates) == 14
    assert all("/di-lab/projekte/" in item.source_url for item in candidates)


def test_other_crawl_persists_separate_reference_codes(tmp_path, monkeypatch):
    test_engine = create_engine(f"sqlite:///{tmp_path / 'other.db'}")
    monkeypatch.setattr(db, "_engine", test_engine)
    Base.metadata.create_all(test_engine)
    adapter = ALL_BY_SLUG["other-tum-data-innovation-lab"]
    page = b'''<h1>Projects for winter semester 2026</h1>
        <div class="c-card"><h6><a href="/di-lab/projekte/energy/">Energy Lab</a></h6></div>
        <div class="c-card"><h6><a href="/di-lab/projekte/robotics/">Robotics Lab</a></h6></div>'''
    fetcher = PoliteFetcher(delay_seconds=0, max_attempts=1, robots=AllowRobots(),
                            transport=httpx.MockTransport(lambda request: httpx.Response(
                                200, content=page, headers={"content-type": "text/html"},
                            )))
    outcome = asyncio.run(ingest_live((adapter,), fetcher))
    assert outcome["results"][0]["status"] == "success"
    with db.session_factory()() as session:
        listings = session.scalars(select(Listing).order_by(Listing.reference_code)).all()
        assert [row.reference_code for row in listings] == ["oth-001", "oth-002"]
        assert all(row.normalized["opportunity_type"] == "other" for row in listings)


def test_energy_wiki_follows_only_audited_link_and_extracts_idp_rows():
    adapter = ALL_BY_SLUG["idp-professorship-of-energy-management-technologies"]
    top = f'<a href="{IDP_ENERGY_WIKI_URL}">Available topics on our wiki</a>'.encode()
    wiki = b'''<div id="main-content"><table>
        <tr><td>IDP</td><td><strong>Energy model for Munich</strong><p>Build a model.</p></td></tr>
        <tr><td>Master thesis</td><td><strong>Wind turbine review</strong></td></tr>
        <tr><td>IDP / Application Project</td><td><strong>Grid flexibility dashboard</strong></td></tr>
    </table></div>'''
    requests = []

    def respond(request):
        requests.append(str(request.url))
        if str(request.url) == adapter.source_urls[0]:
            return httpx.Response(200, content=top, headers={"content-type": "text/html"})
        if str(request.url) == IDP_ENERGY_WIKI_URL:
            return httpx.Response(302, headers={"location": "/spaces/TUMenmantech/pages/76053729"})
        return httpx.Response(200, content=wiki, headers={"content-type": "text/html"})

    fetcher = PoliteFetcher(delay_seconds=0, max_attempts=1, robots=AllowRobots(),
                            transport=httpx.MockTransport(respond))
    result = asyncio.run(discover_adapter(adapter, fetcher))
    assert not result.failures
    assert [item.title for item in result.candidates] == [
        "Energy model for Munich", "Grid flexibility dashboard",
    ]
    assert requests == [adapter.source_urls[0], IDP_ENERGY_WIKI_URL,
                        "https://collab.dvb.bayern/spaces/TUMenmantech/pages/76053729"]


def test_hctl_child_page_is_scoped_and_yields_three_idp_offers():
    adapter = ALL_BY_SLUG["idp-human-centered-technologies-for-learning"]
    top = f'<h1>Teaching</h1><a href="{IDP_HCTL_PROJECTS_URL}">Interdisciplinary Projects (IDP)</a>'.encode()
    child = b'''<h1>IDP Projects</h1>
        <h2><a href="/en/hctl/teaching/idp-projects/dichoptic-text-highlighting-for-focus-support-in-vr/">Dichoptic Text Highlighting for Focus Support in VR</a></h2>
        <h3>Machine learning meets education and VR</h3>
        <h3>VR Classroom Design with Generative Models</h3>
        <h2>Chair for Human-Centered Technologies for Learning</h2>
        <h3>Team member</h3>'''

    requests = []

    def respond(request):
        requests.append(str(request.url))
        body = top if str(request.url) == adapter.source_urls[0] else child
        return httpx.Response(200, content=body, headers={"content-type": "text/html"})

    fetcher = PoliteFetcher(delay_seconds=0, max_attempts=1, robots=AllowRobots(),
                            transport=httpx.MockTransport(respond))
    result = asyncio.run(discover_adapter(adapter, fetcher))
    assert [item.title for item in result.candidates] == [
        "Dichoptic Text Highlighting for Focus Support in VR",
        "Machine learning meets education and VR",
        "VR Classroom Design with Generative Models",
    ]
    assert all("Team member" != item.title for item in result.candidates)
    assert requests == [adapter.source_urls[0], IDP_HCTL_PROJECTS_URL]
    assert result.candidates[0].stable_source_key == adapter.stable_key(
        "https://www.edu.sot.tum.de/hctl/teaching/idp-projects/dichoptic-text-highlighting-for-focus-support-in-vr/",
        result.candidates[0].title,
    )
    assert result.candidates[1].stable_source_key == adapter.stable_key(
        "https://www.edu.sot.tum.de/hctl/teaching/idp-projects/", result.candidates[1].title,
    )


def test_operations_management_skips_ongoing_and_completed_studies():
    adapter = ALL_BY_SLUG["operations-management"]
    page = b'''<div class="frame"><h2>Open Project Studies</h2>
        <li class="list-group-item e2e-item"><span class="publication-title">Open offer</span>
        <a href="https://mediatum.ub.tum.de/doc/open.pdf">Download</a></li></div>
        <div class="frame"><h2>Ongoing Project Studies</h2>
        <li class="list-group-item e2e-item"><span class="publication-title">Ongoing offer</span>
        <a href="https://mediatum.ub.tum.de/doc/ongoing.pdf">Download</a></li></div>
        <div class="frame"><h2>Completed Project Studies</h2>
        <li class="list-group-item e2e-item"><span class="publication-title">Past offer</span>
        <a href="https://mediatum.ub.tum.de/doc/past.pdf">Download</a></li></div>'''
    parser = parser_for(adapter)
    assert [item.title for item in parser.discover(adapter, adapter.source_urls[0], page)] == ["Open offer"]
    assert parser.child_links(adapter, adapter.source_urls[0], page) == [
        "https://mediatum.ub.tum.de/doc/open.pdf",
    ]


def test_data_processing_extracts_individual_idp_news_items():
    adapter = ALL_BY_SLUG["idp-chair-for-data-processing"]
    page = b'''<h1>Aktuelle Ausschreibungen f\xc3\xbcr IDP</h1>
        <div class="article articletype-0"><div class="header"><span>IDP, Aktuelles</span>
        <h3><a href="/en/ldv/news/article/video-parser/">IDP Video Bitstream Parser</a></h3></div></div>
        <div class="article articletype-0"><div class="header"><span>IDP, Aktuelles</span>
        <h3><a href="/en/ldv/news/article/full-stack/">IDP in Full-Stack Development</a></h3></div></div>
        <div class="article articletype-0"><div class="header"><span>Thesis</span>
        <h3><a href="/en/ldv/news/article/thesis/">Video thesis</a></h3></div></div>'''
    rows = parser_for(adapter).discover(adapter, adapter.source_urls[0], page)
    assert [row.title for row in rows] == ["IDP Video Bitstream Parser", "IDP in Full-Stack Development"]
    assert all(row.source_url.startswith("https://www.ce.cit.tum.de/en/ldv/news/article/") for row in rows)


def test_human_machine_communication_requires_idp_in_offer_type_row():
    adapter = ALL_BY_SLUG["idp-chair-of-human-machine-communication"]
    page = b'''<div class="c-accordion__item"><h2><button>3D Perception and Sensor Fusion</button></h2>
        <div class="accordion-body"><table>
        <tr><td>Topic</td><td>3D Perception and Sensor Fusion</td></tr>
        <tr><td>Type</td><td>Forschungspraxis, Interdisziplin\xc3\xa4res Projekt (IDP), Master's Thesis</td></tr>
        <tr><td>Description</td><td>Work with camera and radar data.</td></tr>
        </table></div></div>
        <div class="c-accordion__item"><h2><button>Thesis only</button></h2>
        <div class="accordion-body"><table><tr><td>Type</td><td>Master's Thesis</td></tr></table></div></div>'''
    rows = parser_for(adapter).discover(adapter, adapter.source_urls[0], page)
    assert [row.title for row in rows] == ["3D Perception and Sensor Fusion"]
    assert rows[0].description_markdown and "Work with camera and radar data." in rows[0].description_markdown
