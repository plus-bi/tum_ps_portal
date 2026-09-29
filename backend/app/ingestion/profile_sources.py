"""Versioned single-page Markdown from chair HTML descriptions."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass


HTML_MARKDOWN_VERSION = "html-description-markdown-v1"


def html_description_hash(source_url: str, markdown: str) -> str:
    return hashlib.sha256(f"{HTML_MARKDOWN_VERSION}|{source_url}|{markdown}".encode()).hexdigest()


@dataclass(frozen=True)
class HtmlMarkdownAnalysis:
    content_hash: str
    extracted_markdown_pages: list[str]
    classification: str = "digital_native"
    classifier_version: str = HTML_MARKDOWN_VERSION
