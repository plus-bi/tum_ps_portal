"""Resumable, deliberately slow archival of already-discovered PDF links."""
from __future__ import annotations

import argparse
import asyncio
import logging
import random
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from sqlalchemy import select

from ..config import settings
from ..db import Base, Listing, PDFArtifact, engine, session_factory
from .fetcher import PoliteFetcher

logger = logging.getLogger(__name__)


def is_pdf_url(url: str) -> bool:
    return urlparse(url).path.casefold().endswith(".pdf")


def _pdf_urls() -> list[str]:
    with session_factory()() as session:
        urls = {
            artifact_url
            for (normalized,) in session.execute(select(Listing.normalized))
            if isinstance(normalized, dict)
            for artifact_url in [normalized.get("artifact_url")]
            if isinstance(artifact_url, str) and is_pdf_url(artifact_url)
        }
    return sorted(urls)


def _storage_path(storage_root: Path, digest: str) -> Path:
    return storage_root / "sha256" / digest[:2] / digest[2:4] / f"{digest}.pdf"


async def _fetch_and_store(url: str, fetcher: PoliteFetcher | None = None) -> tuple[str, int, str]:
    config = settings()
    fetcher = fetcher or PoliteFetcher(
        delay_seconds=config.crawler_delay_seconds,
        timeout_seconds=config.crawler_timeout_seconds,
        max_attempts=config.crawler_max_attempts,
        max_content_bytes=config.crawler_max_content_bytes,
    )
    fetched = await fetcher.fetch(url)
    media_type = fetched.media_type.split(";", 1)[0].casefold().strip()
    if media_type != "application/pdf" and not fetched.content.startswith(b"%PDF-"):
        raise ValueError(f"Expected PDF, received {media_type or 'unknown media type'}")
    destination = _storage_path(config.artifact_storage_path, fetched.content_hash)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not destination.exists():
        temporary = destination.with_suffix(".part")
        temporary.write_bytes(fetched.content)
        temporary.replace(destination)
    return fetched.content_hash, len(fetched.content), str(destination.relative_to(config.artifact_storage_path))


def _already_stored(url: str) -> bool:
    with session_factory()() as session:
        artifact = session.scalar(select(PDFArtifact).where(PDFArtifact.url == url))
        if artifact is None or not artifact.storage_key:
            return False
        return (settings().artifact_storage_path / artifact.storage_key).is_file()


def _record_success(url: str, digest: str, byte_size: int, storage_key: str) -> None:
    with session_factory()() as session:
        artifact = session.scalar(select(PDFArtifact).where(PDFArtifact.url == url))
        if artifact is None:
            artifact = PDFArtifact(url=url)
            session.add(artifact)
        artifact.content_hash = digest
        artifact.storage_key = storage_key
        artifact.byte_size = byte_size
        artifact.media_type = "application/pdf"
        artifact.fetched_at = datetime.now(timezone.utc)
        artifact.error = None
        session.commit()


def _record_failure(url: str, error: Exception) -> None:
    with session_factory()() as session:
        artifact = session.scalar(select(PDFArtifact).where(PDFArtifact.url == url))
        if artifact is None:
            artifact = PDFArtifact(url=url)
            session.add(artifact)
        artifact.error = f"{type(error).__name__}: {error}"[:1500]
        session.commit()


async def store_pdf_url(url: str, fetcher: PoliteFetcher) -> bool:
    """Fetch and retain a new PDF once; a failure never changes listing lifecycle."""
    if _already_stored(url):
        return False
    try:
        digest, byte_size, storage_key = await _fetch_and_store(url, fetcher)
        _record_success(url, digest, byte_size, storage_key)
        logger.info('{"event":"pdf_artifact_stored","bytes":%d}', byte_size)
        return True
    except Exception as error:
        _record_failure(url, error)
        logger.warning('{"event":"pdf_artifact_failed","error_type":"%s"}', type(error).__name__)
        return False


def run_pdf_backfill(interval_seconds: int, jitter_seconds: int) -> dict[str, int]:
    """Store pending PDFs with a base delay and bounded random jitter; safe to resume."""
    Base.metadata.create_all(engine())
    urls = [url for url in _pdf_urls() if not _already_stored(url)]
    if not urls:
        return {"scheduled": 0, "stored": 0, "failed": 0, "interval_seconds": interval_seconds}
    stored = failed = 0
    for index, url in enumerate(urls):
        if index:
            asyncio.run(asyncio.sleep(interval_seconds + random.uniform(0, jitter_seconds)))
        try:
            if asyncio.run(store_pdf_url(url, PoliteFetcher(
                delay_seconds=settings().crawler_delay_seconds,
                timeout_seconds=settings().crawler_timeout_seconds,
                max_attempts=settings().crawler_max_attempts,
                max_content_bytes=settings().crawler_max_content_bytes,
            ))):
                stored += 1
            else:
                failed += 1
        except Exception:
            failed += 1
    return {"scheduled": len(urls), "stored": stored, "failed": failed, "interval_seconds": interval_seconds}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--interval-seconds", type=int, default=30)
    parser.add_argument("--jitter-seconds", type=int, default=10)
    args = parser.parse_args()
    if args.interval_seconds < 1 or args.jitter_seconds < 0:
        raise ValueError("interval must be positive and jitter cannot be negative")
    run_pdf_backfill(args.interval_seconds, args.jitter_seconds)


if __name__ == "__main__":
    main()
