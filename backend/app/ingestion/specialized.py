"""Source-owned extraction rules; all fetching and lifecycle decisions stay in live.py."""
from __future__ import annotations

import re
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup, Tag

from .adapters import Candidate, HtmlParser, LmtIdpParser, ManagementAccountingParser
from .registry import ChairAdapter, IDP_HCTL_PROJECTS_URL

DOCUMENT_SUFFIXES = (".pdf", ".doc", ".docx", ".png")
HEADING_NAMES = {"h1", "h2", "h3", "h4", "h5", "h6"}


def _title(node: Tag) -> str:
    return " ".join(node.stripped_strings)


def _candidate(adapter: ChairAdapter, page_url: str, title: str,
               artifact_url: str | None = None, source_text: str | None = None) -> Candidate:
    origin = artifact_url or page_url
    key = adapter.stable_key(origin, title)
    return Candidate(key, title, origin, artifact_url, source_text or title)


def _unique(candidates: list[Candidate]) -> list[Candidate]:
    return list({candidate.stable_source_key: candidate for candidate in candidates}.values())


def _heading(soup: BeautifulSoup, label: str) -> Tag | None:
    return next((node for node in soup.find_all(HEADING_NAMES)
                 if _title(node).casefold().rstrip(":") == label.casefold().rstrip(":")), None)


def _section_nodes(heading: Tag):
    """Elements after a heading until the next heading at its level or above."""
    level = int(heading.name[1])
    for node in heading.next_elements:
        if not isinstance(node, Tag):
            continue
        if node.name in HEADING_NAMES and int(node.name[1]) <= level:
            break
        yield node


def _document_candidates(adapter: ChairAdapter, page_url: str, nodes,
                         *, reject_idp: bool = False) -> list[Candidate]:
    rows: list[Candidate] = []
    for node in nodes:
        if node.name != "a" or not node.get("href"):
            continue
        title = _title(node)
        if not title or (reject_idp and ("idp" in title.casefold() or "interdisciplinary project" in title.casefold())):
            continue
        url = urljoin(page_url, node["href"])
        if urlparse(url).path.casefold().endswith(DOCUMENT_SUFFIXES):
            rows.append(_candidate(adapter, page_url, title, url))
    return _unique(rows)


class SectionDocumentParser(HtmlParser):
    def __init__(self, labels: tuple[str, ...], *, reject_idp: bool = False):
        self.labels = labels
        self.reject_idp = reject_idp

    def discover(self, adapter: ChairAdapter, source_url: str, content: bytes) -> list[Candidate]:
        soup = BeautifulSoup(content, "html.parser")
        rows: list[Candidate] = []
        for label in self.labels:
            heading = _heading(soup, label)
            if heading:
                rows.extend(_document_candidates(adapter, source_url, _section_nodes(heading),
                                                 reject_idp=self.reject_idp))
        return _unique(rows)


class PathDocumentParser(HtmlParser):
    def __init__(self, path_fragment: str):
        self.path_fragment = path_fragment.casefold()

    def discover(self, adapter: ChairAdapter, source_url: str, content: bytes) -> list[Candidate]:
        soup = BeautifulSoup(content, "html.parser")
        return _document_candidates(adapter, source_url,
                                    (link for link in soup.find_all("a", href=True)
                                     if self.path_fragment in urljoin(source_url, link["href"]).casefold()))


class OpenTableParser(HtmlParser):
    def __init__(self, label: str, *, title_column: int = 0,
                 type_column: int | None = None, type_marker: str = "idp"):
        self.label = label
        self.title_column = title_column
        self.type_column = type_column
        self.type_marker = type_marker

    def discover(self, adapter: ChairAdapter, source_url: str, content: bytes) -> list[Candidate]:
        soup = BeautifulSoup(content, "html.parser")
        heading = _heading(soup, self.label)
        if not heading:
            return []
        table = next((node for node in _section_nodes(heading) if node.name == "table"), None)
        if table is None:
            return []
        rows = []
        for tr in table.find_all("tr"):
            cells = tr.find_all("td", recursive=False)
            if not cells or (self.type_column is not None and
                             (len(cells) <= self.type_column or
                              self.type_marker not in _title(cells[self.type_column]).casefold())):
                continue
            if len(cells) <= self.title_column:
                continue
            title_cell = cells[self.title_column]
            title_node = title_cell.find(["strong", "h3", "h4"])
            title = _title(title_node) if title_node else _title(title_cell.find("a") or title_cell)
            if not title or title.casefold() in {"topic", "title"}:
                continue
            link = title_cell.find("a", href=True)
            artifact = urljoin(source_url, link["href"]) if link else None
            rows.append(_candidate(adapter, source_url, title, artifact, _title(title_cell)[:3000]))
        return _unique(rows)


class ListItemParser(HtmlParser):
    def __init__(self, selector: str, *, marker: str | None = None, title_selector: str | None = None):
        self.selector = selector
        self.marker = marker
        self.title_selector = title_selector

    def discover(self, adapter: ChairAdapter, source_url: str, content: bytes) -> list[Candidate]:
        soup = BeautifulSoup(content, "html.parser")
        rows = []
        for item in soup.select(self.selector):
            if self.marker and self.marker not in _title(item).casefold():
                continue
            node = item.select_one(self.title_selector) if self.title_selector else item.find("a", href=True)
            title = _title(node) if node else _title(item)
            if not title:
                continue
            link = (item if item.name == "a" and item.get("href") else
                    node if node and node.name == "a" and node.get("href") else
                    item.find("a", href=True))
            artifact = urljoin(source_url, link["href"]) if link else None
            rows.append(_candidate(adapter, source_url, title, artifact, _title(item)[:3000]))
        return _unique(rows)


class SectionListParser(ListItemParser):
    """Read offer rows inside one named TYPO3 frame, excluding later archive frames."""

    def __init__(self, label: str, selector: str, *, title_selector: str | None = None):
        super().__init__(selector, title_selector=title_selector)
        self.label = label

    def discover(self, adapter: ChairAdapter, source_url: str, content: bytes) -> list[Candidate]:
        soup = BeautifulSoup(content, "html.parser")
        heading = _heading(soup, self.label)
        if heading is None:
            return []
        frame = heading.find_parent("div", class_="frame")
        return super().discover(adapter, source_url, str(frame or heading).encode())

    def child_links(self, adapter: ChairAdapter, source_url: str, content: bytes) -> list[str]:
        soup = BeautifulSoup(content, "html.parser")
        heading = _heading(soup, self.label)
        if heading is None:
            return []
        frame = heading.find_parent("div", class_="frame")
        return super().child_links(adapter, source_url, str(frame or heading).encode())


class CurrentCardsParser(HtmlParser):
    """TUM Data Innovation Lab cards on its current-projects page."""

    def discover(self, adapter: ChairAdapter, source_url: str, content: bytes) -> list[Candidate]:
        soup = BeautifulSoup(content, "html.parser")
        heading = soup.find("h1")
        if heading is None or "projects for" not in _title(heading).casefold():
            return []
        rows = []
        for card in soup.select(".c-card h6 a[href*='/di-lab/projekte/']"):
            title = _title(card)
            if title:
                detail = urljoin(source_url, card["href"])
                rows.append(_candidate(adapter, source_url, title, detail))
        return _unique(rows)


class EnergyWikiParser(HtmlParser):
    """Only IDP-eligible rows in the audited Confluence topic table."""

    def discover(self, adapter: ChairAdapter, source_url: str, content: bytes) -> list[Candidate]:
        if urlparse(source_url).hostname != "collab.dvb.bayern":
            return []
        soup = BeautifulSoup(content, "html.parser")
        rows = []
        for table in soup.select("#main-content table"):
            for tr in table.find_all("tr"):
                cells = tr.find_all("td", recursive=False)
                if len(cells) < 2 or "idp" not in _title(cells[0]).casefold():
                    continue
                title_node = cells[1].find("strong") or cells[1].find("h4")
                title = _title(title_node) if title_node else ""
                if title:
                    rows.append(_candidate(adapter, source_url, title, None, _title(cells[1])[:3000]))
        return _unique(rows)


class HeadingOffersParser(HtmlParser):
    def __init__(self, selector: str, excluded: tuple[str, ...] = ()):
        self.selector = selector
        self.excluded = excluded

    def discover(self, adapter: ChairAdapter, source_url: str, content: bytes) -> list[Candidate]:
        soup = BeautifulSoup(content, "html.parser")
        rows = []
        for heading in soup.select(self.selector):
            title = _title(heading)
            if not title or any(excluded in title.casefold() for excluded in self.excluded):
                continue
            link = heading.parent.find("a", href=True)
            artifact = urljoin(source_url, link["href"]) if link else None
            rows.append(_candidate(adapter, source_url, title, artifact,
                                   _title(heading.parent)[:3000]))
        return _unique(rows)


class MarketingTechnologyStudiesParser(HtmlParser):
    def discover(self, adapter: ChairAdapter, source_url: str, content: bytes) -> list[Candidate]:
        soup = BeautifulSoup(content, "html.parser")
        rows = []
        in_offers = False
        for heading in soup.find_all("h2"):
            title = _title(heading)
            lowered = title.casefold()
            if "overview of industry project studies" in lowered or "overview of scientific project studies" in lowered:
                in_offers = True
                continue
            if lowered.startswith("professorship of marketing"):
                break
            if not in_offers or not title:
                continue
            container = heading.find_parent(".accordion-item") or heading.parent
            link = next((link for link in container.find_all("a", href=True)
                         if urlparse(urljoin(source_url, link["href"])).path.casefold().endswith(DOCUMENT_SUFFIXES)), None)
            artifact = urljoin(source_url, link["href"]) if link else None
            rows.append(_candidate(adapter, source_url, title, artifact,
                                   _title(container)[:3000]))
        return _unique(rows)


class AutomotiveIdpParser(ListItemParser):
    def __init__(self):
        super().__init__("a[href*='classic.fsmb.de/basama-hiwi/entry/']", marker="idp")


class RenewableIdpParser(OpenTableParser):
    def __init__(self):
        super().__init__("Student thesis topics", type_column=2)


class HctlIdpParser(HtmlParser):
    _legacy_offer_base = "https://www.edu.sot.tum.de/hctl/teaching/idp-projects/"

    def child_links(self, adapter: ChairAdapter, source_url: str, content: bytes) -> list[str]:
        return [url for url in super().child_links(adapter, source_url, content)
                if url.rstrip("/").casefold() == IDP_HCTL_PROJECTS_URL.rstrip("/").casefold()]

    def discover(self, adapter: ChairAdapter, source_url: str, content: bytes) -> list[Candidate]:
        soup = BeautifulSoup(content, "html.parser")
        start = _heading(soup, "IDP Projects")
        if not start:
            return []
        rows = []
        for node in start.next_elements:
            if not isinstance(node, Tag) or node.name not in {"h2", "h3"}:
                continue
            title = _title(node)
            if title.casefold().startswith("chair for human-centered"):
                break
            if title and title.casefold() != "idp projects":
                link = node.find("a", href=True)
                detail = urljoin(source_url, link["href"]) if link else None
                candidate = _candidate(adapter, source_url, title, detail)
                # Retain the published reference codes when the chair changes
                # its landing page and adds the /en/ prefix to offer links.
                legacy_origin = (detail.replace("/en/hctl/teaching/idp-projects/",
                                                "/hctl/teaching/idp-projects/")
                                 if detail else self._legacy_offer_base)
                rows.append(Candidate(adapter.stable_key(legacy_origin, title), candidate.title,
                                      candidate.source_url, candidate.application_url, candidate.source_text))
        return _unique(rows)


class ProteomicsIdpParser(HtmlParser):
    def discover(self, adapter: ChairAdapter, source_url: str, content: bytes) -> list[Candidate]:
        soup = BeautifulSoup(content, "html.parser")
        rows = []
        for item in soup.select("main li"):
            text = _title(item)
            if not re.search(r"\bIDP\b", text, re.IGNORECASE):
                continue
            link = item.find("a", href=True)
            if not link:
                continue
            rows.append(_candidate(adapter, source_url, _title(link), urljoin(source_url, link["href"]), text))
        return _unique(rows)


class DataProcessingIdpParser(ListItemParser):
    """The chair's dedicated IDP news list contains one article per offer."""

    def __init__(self):
        super().__init__("div.article.articletype-0", marker="idp", title_selector="h3 a")


class HumanMachineIdpParser(HtmlParser):
    """Only accordion topics whose Type row explicitly offers an IDP."""

    def discover(self, adapter: ChairAdapter, source_url: str, content: bytes) -> list[Candidate]:
        soup = BeautifulSoup(content, "html.parser")
        rows: list[Candidate] = []
        for item in soup.select(".c-accordion__item"):
            heading = item.select_one("h2 button")
            table = item.select_one(".accordion-body table")
            if heading is None or table is None:
                continue
            fields: list[tuple[str, str]] = []
            for tr in table.find_all("tr"):
                cells = tr.find_all("td", recursive=False)
                if len(cells) == 2:
                    fields.append((_title(cells[0]).rstrip(":"), _title(cells[1])))
            type_value = next((value for label, value in fields if label.casefold() == "type"), "")
            if not re.search(r"\bIDP\b", type_value, re.IGNORECASE):
                continue
            title = _title(heading)
            if not title:
                continue
            markdown = "\n\n".join([f"## {title}", *(f"**{label}:** {value}" for label, value in fields)])
            key = adapter.stable_key(source_url, title)
            rows.append(Candidate(key, title, source_url, None, _title(item)[:3000],
                                  description_markdown=markdown))
        return _unique(rows)


SPECIALIZED_PARSERS: dict[str, HtmlParser] = {
    "management-accounting": ManagementAccountingParser(),
    "controlling": ManagementAccountingParser(),
    "digital-marketing": SectionDocumentParser(("Current Internal Project Studies", "Current Project Studies with Companies"), reject_idp=True),
    "financial-accounting": OpenTableParser("List of open project studies", title_column=1),
    "management-of-digital-food-businesses": SectionDocumentParser(("Available project studies",)),
    "global-center-for-family-enterprise": PathDocumentParser("/project_studies/"),
    "family-business-culture-and-ownership": SectionDocumentParser(("Aktuelle Projektstudien",)),
    "operations-management": SectionListParser("Open Project Studies", "li.list-group-item.e2e-item", title_selector=".publication-title"),
    "production-and-supply-chain-management": PathDocumentParser("/project_studies/"),
    "logistics-and-supply-chain-management": SectionDocumentParser(("Project Studies",)),
    "marketing-and-technology": MarketingTechnologyStudiesParser(),
    "idp-institute-of-automotive-technology": AutomotiveIdpParser(),
    "idp-institute-for-machine-tools-and-industrial-management": HeadingOffersParser("main h4"),
    "idp-chair-of-renewable-and-sustainable-energy-systems": RenewableIdpParser(),
    "idp-human-centered-technologies-for-learning": HctlIdpParser(),
    "idp-professorship-of-multiscale-modeling-of-fluid-materials": SectionDocumentParser(("Interdisciplinary Projects (IDPs) for Informatics",)),
    "idp-chair-of-financial-accounting": OpenTableParser("List of open topics"),
    "idp-chair-of-proteomics-and-bioanalytics": ProteomicsIdpParser(),
    "idp-chair-for-data-processing": DataProcessingIdpParser(),
    "idp-chair-of-human-machine-communication": HumanMachineIdpParser(),
    "idp-professorship-of-energy-management-technologies": EnergyWikiParser(),
    "other-tum-data-innovation-lab": CurrentCardsParser(),
    "idp-chair-of-media-technology": LmtIdpParser(),
}
