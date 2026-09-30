"""Convert a single offer's HTML, Word document, or image to source-grounded Markdown."""
from __future__ import annotations

from io import BytesIO
import re

from bs4 import BeautifulSoup, Tag


_BLOCK_NAMES = {"h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "tr"}
_CHROME_SELECTORS = "script, style, noscript, nav, header, footer, aside, form, .breadcrumb, .share, .social"


def _text(node: Tag) -> str:
    return " ".join(node.stripped_strings)


def _normalized(value: str) -> str:
    return " ".join(re.findall(r"\w+", value.casefold()))


def _body_for_offer(soup: BeautifulSoup, title: str, *, container_selector: str | None = None) -> Tag:
    candidates = soup.select(container_selector) if container_selector else [
        *soup.select("article, .news-single, .news-detail, [role='main'], main")]
    wanted = _normalized(title)
    matches = [node for node in candidates if wanted and wanted in _normalized(_text(node))]
    if matches:
        return min(matches, key=lambda node: len(_text(node)))
    if container_selector:
        raise ValueError("No matching offer container on shared HTML page")
    return candidates[0] if candidates else (soup.body or soup)


def _heading_match(root: Tag, title: str) -> bool:
    title_terms = set(re.findall(r"\w+", title.casefold())) - {
        "idp", "project", "study", "in", "of", "for", "and", "with", "the", "a"}
    if not title_terms:
        return False
    for heading in root.find_all(["h1", "h2", "h3", "h4", "h5", "h6"]):
        heading_terms = set(re.findall(r"\w+", _text(heading).casefold()))
        if len(title_terms & heading_terms) / len(title_terms) >= 0.6:
            return True
    return False


def html_to_markdown(content: bytes, *, title: str, container_selector: str | None = None) -> str:
    soup = BeautifulSoup(content, "html.parser")
    root = _body_for_offer(soup, title, container_selector=container_selector)
    for node in root.select(_CHROME_SELECTORS):
        node.decompose()
    if _normalized(title) not in _normalized(_text(root)) and not _heading_match(root, title):
        raise ValueError("HTML page does not identify this offer")
    lines: list[str] = []
    for node in root.find_all(_BLOCK_NAMES):
        if node.find_parent(_BLOCK_NAMES) is not None and node.find_parent(_BLOCK_NAMES) is not root:
            continue
        if node.name == "tr":
            cells = [_text(cell) for cell in node.find_all(["th", "td"], recursive=False)]
            value = " | ".join(cell for cell in cells if cell)
        else:
            value = _text(node)
        if not value:
            continue
        if node.name.startswith("h"):
            value = f"{'#' * int(node.name[1])} {value}"
        elif node.name == "li":
            value = f"- {value}"
        if not lines or lines[-1] != value:
            lines.append(value)
    if not lines:
        raise ValueError("HTML page has no readable offer content")
    if _normalized(title) not in _normalized(" ".join(lines[:2])):
        lines.insert(0, f"# {title}")
    markdown = "\n\n".join(lines).strip()
    if len(markdown) > 120_000:
        raise ValueError("HTML Markdown exceeds profile extraction limit")
    return markdown


def docx_to_markdown(content: bytes, *, title: str) -> str:
    from docx import Document
    from docx.oxml.ns import qn
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    document = Document(BytesIO(content))
    lines: list[str] = []
    for element in document.element.body.iterchildren():
        if element.tag == qn("w:p"):
            paragraph = Paragraph(element, document)
            value = paragraph.text.strip()
            if not value:
                continue
            style = paragraph.style.name.casefold() if paragraph.style else ""
            heading = re.match(r"heading\s*(\d+)", style)
            if heading:
                value = f"{'#' * min(int(heading.group(1)), 6)} {value}"
            elif "list" in style:
                value = f"- {value}"
            lines.append(value)
        elif element.tag == qn("w:tbl"):
            table = Table(element, document)
            for row in table.rows:
                value = " | ".join(cell.text.strip().replace("\n", " ") for cell in row.cells)
                if value.strip(" |"):
                    lines.append(value)
    if not lines:
        raise ValueError("Word document has no readable text")
    if _normalized(title) not in _normalized(" ".join(lines[:2])):
        lines.insert(0, f"# {title}")
    markdown = "\n\n".join(lines).strip()
    if len(markdown) > 120_000:
        raise ValueError("Word Markdown exceeds profile extraction limit")
    return markdown


def inline_to_markdown(source_text: str, *, title: str) -> str:
    """Use an offer's own listing text when no separate detail document exists."""
    text = " ".join(source_text.split())
    if len(text) < 80 or _normalized(text) == _normalized(title):
        raise ValueError("Listing has no substantive inline description")
    markdown = f"# {title}\n\n{text}"
    if len(markdown) > 120_000:
        raise ValueError("Inline Markdown exceeds profile extraction limit")
    return markdown
