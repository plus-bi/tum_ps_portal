from __future__ import annotations
from dataclasses import dataclass
from urllib.parse import parse_qs, urljoin, urlparse
from bs4 import BeautifulSoup, Tag
from .classifier import classify
from .registry import ChairAdapter


@dataclass(frozen=True)
class Candidate:
    stable_source_key: str
    title: str
    source_url: str
    application_url: str | None
    source_text: str
    description_markdown: str | None = None
    pdf_url: str | None = None


class HtmlParser:
    _generic_titles = {
        "project study", "project studies", "projektstudium", "projektstudien",
        "current project study offerings", "available project studies", "open project studies",
        "ongoing project studies", "current project studies with companies", "current internal project studies",
        "topics", "topic", "general information", "application", "application process", "procedure",
        "scope", "evaluation", "grading", "contact", "important information", "submission requirements",
        "process of the project study", "execution of the project study", "durchführung des projektstudiums",
        "modalities of the project study idp",
        "bewertung", "themen", "bewerbung", "recent proposals", "project modules",
        "aktuelle projektstudien", "vergangene projektstudien",
        "project studies and interdisciplinary projects for informatics idp",
        "theses project studies idps", "project studies idps", "project studies idp",
    }

    @staticmethod
    def _under_archive_heading(block: Tag, adapter: ChairAdapter) -> bool:
        heading = block.find_previous(["h1", "h2", "h3", "h4"])
        if not heading: return False
        label = " ".join(heading.stripped_strings).casefold()
        return any(marker in label for marker in adapter.archive_markers)

    def discover(self, adapter: ChairAdapter, source_url: str, content: bytes) -> list[Candidate]:
        soup = BeautifulSoup(content, "html.parser")
        for node in soup(["script", "style", "nav", "footer", "noscript"]): node.decompose()
        blocks: list[Tag] = []; seen: set[int] = set()
        for selector in adapter.candidate_selectors:
            for block in soup.select(selector):
                if id(block) not in seen: blocks.append(block); seen.add(id(block))
        results: dict[str, Candidate] = {}
        for block in blocks:
            text = " ".join(block.stripped_strings)
            anchors = block.find_all("a", href=True)
            classification_text = (f"{text} {' '.join(a['href'] for a in anchors)}"
                                   if adapter.classify_link_targets else text)
            if not classify(classification_text, adapter, in_archive=self._under_archive_heading(block, adapter)).accepted: continue
            heading = (block.select_one(adapter.title_selector) if adapter.title_selector
                       else block.find(["h1", "h2", "h3", "h4", "h5"]))
            offer_link = (block.select_one(adapter.offer_link_selector) if adapter.offer_link_selector
                          else next((a for a in anchors
                                     if adapter.source_implies_active_type or any(
                                         marker in f"{' '.join(a.stripped_strings)} {a['href']}".casefold()
                                         for marker in adapter.active_markers)), None))
            if heading is None and offer_link is None: continue
            title = " ".join((heading or offer_link).stripped_strings)
            normalized_title = " ".join(title.casefold().replace("&", " ").replace("/", " ").split()).strip(":")
            if normalized_title in self._generic_titles or normalized_title in adapter.excluded_titles: continue
            title_marker_text = classification_text.casefold() if adapter.title_selector else normalized_title
            if not adapter.source_implies_active_type and not any(
                    marker in title_marker_text for marker in adapter.active_markers): continue
            if any(noise in normalized_title for noise in ("registration form", "information sheet", "report", "submission", "submisson", "submit your", "overview", "contact person")): continue
            links = [urljoin(source_url, a.get("href")) for a in anchors]
            detail = (urljoin(source_url, offer_link.get("href")) if offer_link is not None else
                      next((link for link in links if any(m in link.casefold() for m in ("project", "projekt", ".pdf", ".docx"))), None))
            origin = detail or source_url; key = adapter.stable_key(origin, title)
            candidate = Candidate(key, title, origin, detail, text)
            existing = results.get(normalized_title)
            if (existing is None or (candidate.application_url and not existing.application_url)
                    or (bool(candidate.application_url) == bool(existing.application_url)
                        and len(candidate.source_text) < len(existing.source_text))):
                results[normalized_title] = candidate
        return list(results.values())

    def child_links(self, adapter: ChairAdapter, source_url: str, content: bytes) -> list[str]:
        soup = BeautifulSoup(content, "html.parser"); links = set()
        for anchor in soup.find_all("a", href=True):
            absolute = urljoin(source_url, anchor["href"]); label = f"{' '.join(anchor.stripped_strings)} {absolute}".casefold()
            matches = (any(pattern.casefold() in absolute.casefold() for pattern in adapter.child_url_patterns)
                       if adapter.child_url_patterns else any(marker in label for marker in adapter.child_link_markers))
            if matches and not any(marker in label for marker in adapter.excluded_markers): links.add(absolute)
        return sorted(links)


class Typo3Parser(HtmlParser): pass
class SquarespaceParser(HtmlParser): pass
class LegacyHtmlParser(HtmlParser): pass
PARSERS = {"typo3": Typo3Parser(), "squarespace": SquarespaceParser(), "legacy_html": LegacyHtmlParser()}


class ManagementAccountingParser(HtmlParser):
    """Extract the chair's linked proposals, excluding completed project studies."""

    _proposal_sections = {"recent proposals", "older proposals"}
    _document_suffixes = (".pdf", ".doc", ".docx", ".png")

    def discover(self, adapter: ChairAdapter, source_url: str, content: bytes) -> list[Candidate]:
        soup = BeautifulSoup(content, "html.parser")
        results: dict[str, Candidate] = {}

        def add(link: Tag) -> None:
            document_url = urljoin(source_url, link["href"])
            if not urlparse(document_url).path.casefold().endswith(self._document_suffixes):
                return
            title = " ".join(link.stripped_strings)
            if not title or document_url in results:
                return
            key = adapter.stable_key(document_url, title)
            results[document_url] = Candidate(key, title, document_url, document_url, title)

        for frame in soup.select("div.frame"):
            for heading in frame.find_all("p", recursive=False):
                strong = heading.find("strong")
                if strong is None:
                    continue
                label = " ".join(strong.stripped_strings).casefold().rstrip(":")
                if label in {"current topics", "aktuelle themen"}:
                    for sibling in heading.next_siblings:
                        if not isinstance(sibling, Tag):
                            continue
                        if sibling.name not in {"p", "ul"} or sibling.find("strong") and not sibling.find("a"):
                            break
                        for link in sibling.find_all("a", href=True):
                            add(link)
                    continue
                if label not in self._proposal_sections:
                    continue
                proposals = heading.find_next_sibling()
                if proposals is None or proposals.name != "ul":
                    continue
                for item in proposals.find_all("li", recursive=False):
                    link = item.find("a", href=True)
                    if link is not None:
                        add(link)
        return list(results.values())


class LmtIdpParser(HtmlParser):
    """The LMT offers are IDP-labelled accordions with descriptions and download endpoints."""

    _legacy_title = (
        "BA , MA , IDP , FP , IP , SHK : Multi-level Fingerprinting-based Indoor Localization Scheme"
    )
    _legacy_robot_title = (
        "BA , IDP , FP , IP : Robot Learning from Demonstration - Designing the Data Collection Hardware"
    )

    @staticmethod
    def _markdown(section: Tag) -> str:
        lines: list[str] = []
        for node in section.find_all(["h2", "h3", "h4", "p", "li"]):
            if node.name == "p" and node.find_parent("li"):
                continue
            value = " ".join(node.stripped_strings)
            if not value:
                continue
            if node.name in {"h2", "h3", "h4"}:
                lines.append(f"## {value}")
            elif node.name == "li":
                lines.append(f"- {value}")
            else:
                lines.append(value)
        return "\n\n".join(lines)

    def discover(self, adapter: ChairAdapter, source_url: str, content: bytes) -> list[Candidate]:
        soup = BeautifulSoup(content, "html.parser")
        results: list[Candidate] = []
        for block in soup.select(".tx-curlcontent-main > .accordion"):
            button = block.select_one("h5 button")
            collapse = block.select_one(".collapse")
            if button is None or collapse is None:
                continue
            if not button.select('abbr[title="Interdisciplinary Project"]'):
                continue
            title_node = collapse.find("h2")
            title = (" ".join(title_node.stripped_strings) if title_node else
                     " ".join(button.stripped_strings).split(":", 1)[-1].strip())
            if not title:
                continue
            pdf_url = None
            for anchor in collapse.find_all("a", href=True):
                url = urljoin(source_url, anchor["href"])
                parsed = urlparse(url)
                if (parsed.hostname == "tumanager.ei.tum.de" and parsed.path == "/service.php"
                        and parse_qs(parsed.query).get("mode") == ["pdfdownload"]):
                    pdf_url = url
                    break
            markdown = [f"# {title}"]
            keywords = collapse.select_one(".keywords")
            if keywords:
                markdown.append(f"**{' '.join(keywords.stripped_strings)}**")
            for heading in collapse.find_all("h4"):
                if heading.find_parent(".description"):
                    continue
                section = heading.find_next_sibling("div")
                if section is not None:
                    body = self._markdown(section)
                    if body:
                        markdown.append(f"## {' '.join(heading.stripped_strings)}\n\n{body}")
            short = next((node.parent for node in collapse.find_all("strong")
                          if "short description" in node.get_text(" ", strip=True).casefold()), None)
            if short:
                markdown.insert(1, f"**{' '.join(short.stripped_strings)}**")
            description_markdown = "\n\n".join(markdown).strip()
            source_text = " ".join(description_markdown.replace("#", "").replace("**", "").split())
            # Preserve the listing/reference code created by the former generic parser.
            identity_title = {
                "Multi-level Fingerprinting-based Indoor Localization Scheme": self._legacy_title,
                "Robot Learning from Demonstration - Designing the Data Collection Hardware": self._legacy_robot_title,
            }.get(title, title)
            results.append(Candidate(adapter.stable_key(source_url, identity_title), title, source_url, None,
                                     source_text, description_markdown, pdf_url))
        return results


def parser_for(adapter: ChairAdapter) -> HtmlParser:
    from .specialized import SPECIALIZED_PARSERS
    if adapter.slug in SPECIALIZED_PARSERS:
        return SPECIALIZED_PARSERS[adapter.slug]
    return PARSERS[adapter.family]
