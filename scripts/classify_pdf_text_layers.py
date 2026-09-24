"""Classify stored PDFs by usable native text layer without emitting their content."""
from __future__ import annotations

import contextlib
import io
import json
import logging
from pathlib import Path

from pypdf import PdfReader
from sqlalchemy import select

from app.config import settings
from app.db import PDFArtifact, session_factory


logging.disable(logging.CRITICAL)
counts = {"scanned": 0, "digital_native": 0, "mixed": 0}

with session_factory()() as session:
    artifacts = list(session.scalars(select(PDFArtifact).where(PDFArtifact.storage_key.is_not(None))))

for artifact in artifacts:
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        reader = PdfReader(str(Path(settings().artifact_storage_path) / artifact.storage_key), strict=False)
        text_lengths = [len((page.extract_text() or "").strip()) for page in reader.pages]
    useful_pages = sum(length >= 40 for length in text_lengths)
    category = "scanned" if useful_pages == 0 else "digital_native" if useful_pages == len(text_lengths) else "mixed"
    counts[category] += 1

print(json.dumps({"files": counts, "useful_text_threshold_characters_per_page": 40}))
