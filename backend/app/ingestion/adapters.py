from __future__ import annotations
from dataclasses import dataclass
from urllib.parse import urljoin
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


class HtmlParser:
    _generic_titles = {
        "project study", "project studies", "projektstudium", "projektstudien",
        "current project study offerings", "available project studies", "open project studies",
        "ongoing project studies", "current project studies with companies", "current internal project studies",
        "topics", "topic", "general information", "application", "application process", "procedure",
        "scope", "evaluation", "grading", "contact", "important information", "submission requirements",
        "process of the project study", "execution of the project study", "durchführung des projektstudiums",
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
            if not classify(text, adapter, in_archive=self._under_archive_heading(block, adapter)).accepted: continue
            heading = block.find(["h1", "h2", "h3", "h4", "h5"])
            offer_link = next((a for a in block.find_all("a", href=True)
                               if any(marker in " ".join(a.stripped_strings).casefold() for marker in adapter.active_markers)), None)
            if heading is None and offer_link is None: continue
            title = " ".join((heading or offer_link).stripped_strings)
            normalized_title = " ".join(title.casefold().replace("&", " ").replace("/", " ").split()).strip(":")
            if normalized_title in self._generic_titles: continue
            if not any(marker in normalized_title for marker in adapter.active_markers): continue
            if any(noise in normalized_title for noise in ("registration form", "information sheet", "report", "submission", "submisson", "submit your", "overview", "contact person")): continue
            links = [urljoin(source_url, a.get("href")) for a in block.find_all("a", href=True)]
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
            matches = (any(pattern in absolute.casefold() for pattern in adapter.child_url_patterns)
                       if adapter.child_url_patterns else any(marker in label for marker in adapter.child_link_markers))
            if matches and not any(marker in label for marker in adapter.excluded_markers): links.add(absolute)
        return sorted(links)


class Typo3Parser(HtmlParser): pass
class SquarespaceParser(HtmlParser): pass
class LegacyHtmlParser(HtmlParser): pass
PARSERS = {"typo3": Typo3Parser(), "squarespace": SquarespaceParser(), "legacy_html": LegacyHtmlParser()}


def parser_for(adapter: ChairAdapter) -> HtmlParser: return PARSERS[adapter.family]
