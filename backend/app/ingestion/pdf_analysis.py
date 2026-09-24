"""Persist checksum-keyed, non-content PDF classification results."""
from __future__ import annotations

import contextlib
import io
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from pypdf import PdfReader
from sqlalchemy import select

from ..config import settings
from ..db import Base, PDFAnalysis, PDFArtifact, engine, session_factory

CLASSIFIER_VERSION = "text-layer-v1"
USEFUL_TEXT_THRESHOLD = 40


def classify_stored_pdfs() -> dict[str, int]:
    """Classify each unique stored PDF without retaining document text."""
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
        try:
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                reader = PdfReader(str(Path(settings().artifact_storage_path) / artifact.storage_key), strict=False)
                text_lengths = [len((page.extract_text() or "").strip()) for page in reader.pages]
            useful_pages = sum(length >= USEFUL_TEXT_THRESHOLD for length in text_lengths)
            classification = "scanned" if useful_pages == 0 else "digital_native" if useful_pages == len(text_lengths) else "mixed"
            details.update({"page_count": len(text_lengths), "pages_with_usable_text": useful_pages})
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
            session.commit()
        summary[classification] += 1
    return summary


def main() -> None:
    print(json.dumps(classify_stored_pdfs(), sort_keys=True))


if __name__ == "__main__":
    main()
