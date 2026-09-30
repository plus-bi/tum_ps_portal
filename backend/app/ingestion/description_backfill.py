"""Materialize offer descriptions from scoped HTML, DOCX, PNG, or inline chair text.

Run on the worker with ``python -m app.ingestion.description_backfill --dry-run`` first.
This step creates Markdown sources for a later ``profile_backfill`` run; it makes no
project-profile model calls. PNG transcription uses the configured Azure OpenAI client.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
from dataclasses import dataclass
from urllib.parse import urlparse

from sqlalchemy import select

from ..config import settings
from ..db import Chair, Listing, session_factory
from ..schemas import Status
from .description_markdown import docx_to_markdown, html_to_markdown, inline_to_markdown
from .fetcher import PoliteFetcher
from .llm_client import extract_image_markdown
from .pdf_backfill import is_pdf_url
from .profile_sources import description_source_url, html_description_hash

logger = logging.getLogger(__name__)

# Only these chair-owned URL prefixes may be fetched for project descriptions.
# Every other artifact URL is skipped; redirects still pass through PoliteFetcher.
CHILD_URL_PATTERNS: dict[str, tuple[str, ...]] = {
    "idp-chair-for-data-processing": ("https://www.ce.cit.tum.de/en/ldv/news-singleview-en/",),
    "idp-tum-entrepreneurship-research-institute": (
        "https://www.ie.mgt.tum.de/en/ent/teaching/project-studies-and-idps/news-single-view-project/article/idp-",),
    "tum-entrepreneurship-research-institute": (
        "https://www.ie.mgt.tum.de/en/ent/teaching/project-studies-and-idps/news-single-view-project/article/project-study-",
        "https://www.ie.mgt.tum.de/en/ent/teaching/project-studies-and-idps/news-single-view-project/article/project-studymoosyc-get-moosyc-into-every-artists-head/"),
    "idp-institute-for-machine-tools-and-industrial-management": (
        "https://www.mec.ed.tum.de/en/iwb/departments/machine-tools/",),
    "other-tum-data-innovation-lab": ("https://www.mdsi.tum.de/en/di-lab/projekte/ws26-",),
    "idp-human-centered-technologies-for-learning": (
        "https://www.edu.sot.tum.de/en/hctl/teaching/idp-projects/",
        "https://www.edu.sot.tum.de/en/hctl/teaching/interdisciplinary-projects/"),
    "idp-chair-of-proteomics-and-bioanalytics": (
        "https://www.mls.ls.tum.de/proteomics/research/projects/",),
    "idp-institute-of-automotive-technology": ("https://classic.fsmb.de/basama-hiwi/entry/",),
    "idp-chair-of-aerodynamics-and-fluid-mechanics": ("https://classic.fsmb.de/basama-hiwi/entry/",),
    "idp-institute-for-materials-handling-material-flow-logistics": (
        "https://classic.fsmb.de/basama-hiwi/entry/",),
    "operations-management": ("https://mediatum.ub.tum.de/node?id=",),
    "controlling": ("https://www.fa.mgt.tum.de/fileadmin/w00chf/controlling/Projektstudien",),
    "management-accounting": ("https://www.fa.mgt.tum.de/fileadmin/w00chf/controlling/Projektstudien",),
    "digital-marketing": ("https://www.msl.mgt.tum.de/fileadmin/w00cja/dm/_my_direct_uploads/",),
    "marketing-and-technology": ("https://www.msl.mgt.tum.de/fileadmin/w00cja/mt/_my_direct_uploads/",),
}
INLINE_ONLY_CHAIRS = {"idp-professorship-of-energy-management-technologies"}
HTML_CONTAINER_SELECTORS = {
    # Two IDPs share this page. Each offer has its own card and heading.
    "idp-human-centered-technologies-for-learning": ".c-main > .frame",
}


@dataclass(frozen=True)
class DescriptionTarget:
    listing_id: object
    chair_slug: str
    title: str
    summary: str
    source_url: str
    artifact_url: str | None
    listing_content_hash: str


def _kind(target: DescriptionTarget) -> str:
    if target.chair_slug in INLINE_ONLY_CHAIRS or not target.artifact_url:
        return "inline"
    path = urlparse(target.artifact_url).path.casefold()
    if path.endswith((".doc", ".docx")):
        return "docx" if path.endswith(".docx") else "unsupported"
    if path.endswith(".png"):
        return "png"
    if path.endswith((".jpg", ".jpeg", ".gif", ".svg")):
        return "unsupported"
    return "html"


def _allowed(target: DescriptionTarget) -> bool:
    if target.chair_slug in INLINE_ONLY_CHAIRS or not target.artifact_url:
        return True
    return any(target.artifact_url.startswith(prefix)
               for prefix in CHILD_URL_PATTERNS.get(target.chair_slug, ()))


def _targets(*, chair_slugs: set[str] | None = None) -> list[DescriptionTarget]:
    with session_factory()() as session:
        statement = (select(Listing, Chair).join(Chair, Listing.chair_id == Chair.id)
                     .where(Listing.status == Status.active))
        if chair_slugs is not None:
            if not chair_slugs:
                return []
            statement = statement.where(Chair.slug.in_(chair_slugs))
        rows = session.execute(statement).all()
        targets = []
        for listing, chair in rows:
            normalized = listing.normalized or {}
            artifact_url = normalized.get("artifact_url")
            if isinstance(artifact_url, str) and is_pdf_url(artifact_url):
                continue
            markdown = normalized.get("description_markdown")
            source_url = description_source_url(normalized)
            if (isinstance(markdown, str) and markdown.strip() and isinstance(source_url, str)
                    and normalized.get("description_hash") == html_description_hash(source_url, markdown)):
                continue
            listing_url = normalized.get("source_url")
            if not isinstance(listing_url, str):
                continue
            targets.append(DescriptionTarget(listing.id, chair.slug, listing.title,
                                             listing.summary or "", listing_url,
                                             artifact_url if isinstance(artifact_url, str) else None,
                                             listing.content_hash))
        return targets


def _store(target: DescriptionTarget, markdown: str, source_url: str, fetched_hash: str | None) -> bool:
    with session_factory()() as session:
        listing = session.get(Listing, target.listing_id)
        if (listing is None or listing.status != Status.active or
                listing.content_hash != target.listing_content_hash or
                (listing.normalized or {}).get("artifact_url") != target.artifact_url):
            return False
        normalized = dict(listing.normalized)
        normalized["description_markdown"] = markdown
        normalized["description_source_url"] = source_url
        normalized["description_hash"] = html_description_hash(source_url, markdown)
        if fetched_hash:
            normalized["description_content_hash"] = fetched_hash
        listing.normalized = normalized
        session.commit()
        return True


async def run_description_backfill(*, limit: int | None = None, dry_run: bool = False,
                                   chair_slugs: set[str] | None = None,
                                   fetcher: PoliteFetcher | None = None) -> dict:
    """Convert each eligible active listing; leave failures and lifecycle untouched."""
    targets = _targets(chair_slugs=chair_slugs)
    if limit is not None:
        targets = targets[:limit]
    summary = {"selected": len(targets), "converted": 0, "fallback_inline": 0,
               "failed": 0, "skipped": {},
               "kinds": {}, "dry_run": dry_run}
    config = settings()
    fetcher = fetcher or PoliteFetcher(delay_seconds=config.crawler_delay_seconds,
                                       timeout_seconds=config.crawler_timeout_seconds,
                                       max_attempts=config.crawler_max_attempts,
                                       max_content_bytes=config.crawler_max_content_bytes)
    fetched: dict[str, object] = {}
    for number, target in enumerate(targets, start=1):
        kind = _kind(target)
        summary["kinds"][kind] = summary["kinds"].get(kind, 0) + 1
        reason = ("unsupported_media" if kind == "unsupported" else
                  "unapproved_child_url" if not _allowed(target) else None)
        if reason:
            summary["skipped"][reason] = summary["skipped"].get(reason, 0) + 1
            continue
        if dry_run:
            continue
        try:
            if kind == "inline":
                markdown = inline_to_markdown(target.summary, title=target.title)
                source_url = (target.artifact_url if target.chair_slug in INLINE_ONLY_CHAIRS
                              and target.artifact_url else target.source_url)
                content_hash = None
            else:
                assert target.artifact_url is not None
                item = fetched.get(target.artifact_url)
                if item is None:
                    item = await fetcher.fetch(target.artifact_url)
                    fetched[target.artifact_url] = item
                media = item.media_type.split(";", 1)[0].casefold()
                if kind == "html":
                    if media not in {"text/html", "application/xhtml+xml"}:
                        raise ValueError("Expected HTML detail page")
                    markdown = html_to_markdown(item.content, title=target.title,
                                                container_selector=HTML_CONTAINER_SELECTORS.get(target.chair_slug))
                elif kind == "docx":
                    markdown = docx_to_markdown(item.content, title=target.title)
                else:
                    markdown = await asyncio.to_thread(extract_image_markdown, item.content,
                                                       title=target.title)
                source_url, content_hash = item.url, item.content_hash
        except Exception as error:
            if kind != "inline":
                try:
                    markdown = inline_to_markdown(target.summary, title=target.title)
                    source_url, content_hash = target.source_url, None
                    summary["fallback_inline"] += 1
                    logger.info(json.dumps({"event": "description_fallback_inline", "chair": target.chair_slug,
                                            "url": target.artifact_url, "error_type": type(error).__name__}))
                except ValueError:
                    markdown = ""
            else:
                markdown = ""
            if not markdown:
                summary["failed"] += 1
                logger.warning(json.dumps({"event": "description_conversion_failed", "chair": target.chair_slug,
                                           "url": target.artifact_url or target.source_url,
                                           "error_type": type(error).__name__}))
                continue
        try:
            if _store(target, markdown, source_url, content_hash):
                summary["converted"] += 1
            else:
                summary["skipped"]["listing_changed"] = summary["skipped"].get("listing_changed", 0) + 1
        except Exception as error:
            summary["failed"] += 1
            logger.warning(json.dumps({"event": "description_store_failed", "chair": target.chair_slug,
                                       "url": target.artifact_url or target.source_url,
                                       "error_type": type(error).__name__}))
        if number % 10 == 0 or number == len(targets):
            logger.info(json.dumps({"event": "description_backfill_progress", "processed": number,
                                    "selected": len(targets), "converted": summary["converted"],
                                    "failed": summary["failed"]}))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if args.limit is not None and args.limit < 0:
        parser.error("--limit cannot be negative")
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    print(json.dumps(asyncio.run(run_description_backfill(limit=args.limit, dry_run=args.dry_run)),
                     sort_keys=True))


if __name__ == "__main__":
    main()
