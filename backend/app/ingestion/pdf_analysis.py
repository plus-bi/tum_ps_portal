"""Classify each stored PDF's text layer and retain its extracted markdown, keyed by checksum."""
from __future__ import annotations

import contextlib
import io
import json
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select

from ..config import settings
from ..db import Base, PDFAnalysis, PDFArtifact, engine, session_factory
from .pdf_reader import USEFUL_TEXT_THRESHOLD, read_pdf

CLASSIFIER_VERSION = "pymupdf-native-markdown-v2"


def classify_stored_pdfs() -> dict[str, int]:
    """Classify and extract markdown for each unique stored PDF, deduplicated by content hash."""
    Base.metadata.create_all(engine())
    with session_factory()() as session:
        artifacts = list(session.scalars(select(PDFArtifact).where(
            PDFArtifact.content_hash.is_not(None), PDFArtifact.storage_key.is_not(None),
        )))

    unique_artifacts = {artifact.content_hash: artifact for artifact in artifacts}
    summary = {"digital_native": 0, "scanned": 0, "mixed": 0, "unknown": 0}
    for content_hash, artifact in unique_artifacts.items():
        classification = "unknown"
        details: dict[str, int | str] = {"useful_text_threshold_characters_per_page": USEFUL_TEXT_THRESHOLD}
        pages: list[str] | None = None
        try:
            data = (Path(settings().artifact_storage_path) / artifact.storage_key).read_bytes()
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                result = read_pdf(data)
            classification = result.classification
            pages = result.pages
            details.update({"page_count": len(pages), "pages_with_usable_text":
                            result.pages_with_usable_text})
        except Exception as error:
            details["error_type"] = type(error).__name__

        with session_factory()() as session:
            analysis = session.scalar(select(PDFAnalysis).where(PDFAnalysis.content_hash == content_hash))
            if analysis is None:
                analysis = PDFAnalysis(content_hash=content_hash, classifier_version=CLASSIFIER_VERSION)
                session.add(analysis)
            analysis.classification = classification
            analysis.classifier_version = CLASSIFIER_VERSION
            analysis.classified_at = datetime.now(timezone.utc)
            analysis.details = details
            analysis.extracted_markdown_pages = pages
            session.commit()
        summary[classification] += 1
    return summary


def main() -> None:
    print(json.dumps(classify_stored_pdfs(), sort_keys=True))


if __name__ == "__main__":
    main()
