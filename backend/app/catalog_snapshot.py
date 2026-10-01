"""Persistent public catalog generations. No database reads on visitor requests."""
import argparse
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from functools import lru_cache
import hashlib
import json
import logging
import os
from pathlib import Path
import re
import shutil
import time
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import text

from .config import settings
from .db import engine, session_factory
from .schemas import Project, ProjectDescriptionDetail, ProjectProfileDetail

logger = logging.getLogger(__name__)
PIPELINE_LOCK_ID = 1414876499
VERSION = re.compile(r"^[0-9]{8}T[0-9]{12}Z-[a-f0-9]{12}$")


@contextmanager
def pipeline_lock():
    with engine().connect() as connection:
        postgres = connection.dialect.name == "postgresql"
        acquired = not postgres or bool(connection.scalar(
            text("SELECT pg_try_advisory_lock(:key)"), {"key": PIPELINE_LOCK_ID}))
        try:
            yield acquired
        finally:
            if postgres and acquired:
                connection.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": PIPELINE_LOCK_ID})


def encode(value) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode()


def _write(path: Path, value) -> None:
    with path.open("wb") as file:
        file.write(encode(value))
        file.flush()
        os.fsync(file.fileno())


def _sync_directory(path: Path) -> None:
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def compact(project: dict) -> dict:
    result = dict(project)
    for field in ("academic_units", "project_partners"):
        result[field] = [{"name": item["name"], "canonical_name": item.get("canonical_name")}
                         for item in result.get(field, [])]
    for field in ("last_seen_at", "deadline", "application_url", "company", "location", "status"):
        result.pop(field, None)
    return result


def construct(version: str, now: datetime) -> dict:
    from .api import persisted_projects, project_aliases, project_description, project_profile, chairs
    from .profile_filters import available_fields
    from .schemas import Status, Topic
    # All publication reads share a consistent committed transaction, including detail payloads.
    with session_factory()() as session:
        if session.bind.dialect.name == "postgresql":
            session.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"))
        records = persisted_projects(session)
        aliases = project_aliases(session)
        details = {}
        for project in records:
            payload = {"project": project.model_dump(mode="json"), "profile": None, "description": None}
            for field, enabled, loader in (("profile", project.has_profile, project_profile),
                                            ("description", project.has_description, project_description)):
                if enabled:
                    try:
                        payload[field] = loader(project.slug, session).model_dump(mode="json")
                    except HTTPException as error:
                        if error.status_code != 404:
                            raise
            details[project.slug] = payload
    pins = list(settings().pinned_project_codes)
    order = {code: i for i, code in enumerate(pins)}
    def timestamp(value):
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).replace(tzinfo=timezone.utc).timestamp()
    active = [p for p in records if p.status == Status.active]
    active.sort(key=lambda p: (order.get(p.reference_code.casefold(), len(order)),
                               -timestamp(p.published_at or p.first_seen_at), -timestamp(p.first_seen_at)))
    index = [compact(p.model_dump(mode="json")) for p in active]
    fields = available_fields()
    profile_counts = {}
    for field in fields:
        counts = {}
        for p in active:
            raw = getattr(p.filter_values, field, None) if p.filter_values else None
            values = raw if isinstance(raw, list) else [raw]
            for value in values or [None]:
                value = "unknown" if value in (None, "unknown", "not_stated") else value
                counts[value] = counts.get(value, 0) + 1
            if field == "degree_level" and "any" in values:
                for value in ("bachelor", "master"):
                    if value not in values:
                        counts[value] = counts.get(value, 0) + 1
        profile_counts[field] = counts
    bootstrap = {"version": version, "published_at": now.isoformat(), "items": index[:20],
                 "total": len(index), "page": 1, "page_size": 20,
                 "last_updated_at": max((p.last_seen_at.isoformat() for p in records), default=None),
                 "chairs": chairs(), "aliases": aliases, "published_profile_filters": fields,
                 "pinned_project_codes": pins,
                 "facets": {"departments": {d: sum(p.department == d for p in active) for d in {p.department for p in active}},
                            "topics": {t.value: sum(t in p.topics for p in active) for t in Topic},
                            "profiles": profile_counts}}
    return {"bootstrap": bootstrap, "catalog": {"version": version, "items": index},
            "projects": [p.model_dump(mode="json") for p in records], "details": details}


def validate(data: dict) -> None:
    records = [Project.model_validate(p) for p in data["projects"]]
    slugs = {p.slug for p in records}
    if len(slugs) != len(records) or set(data["details"]) != slugs:
        raise ValueError("Duplicate or missing project details")
    index = data["catalog"]["items"]
    if len(index) != data["bootstrap"]["total"] or index[:20] != data["bootstrap"]["items"]:
        raise ValueError("Bootstrap does not match catalog")
    for detail in data["details"].values():
        Project.model_validate(detail["project"])
        if detail["profile"]:
            ProjectProfileDetail.model_validate(detail["profile"])
        if detail["description"]:
            ProjectDescriptionDetail.model_validate(detail["description"])
    for slug in data["bootstrap"]["aliases"]:
        seen = set()
        while slug in data["bootstrap"]["aliases"]:
            if slug in seen:
                raise ValueError("Alias cycle")
            seen.add(slug)
            slug = data["bootstrap"]["aliases"][slug]
        if slug not in slugs:
            raise ValueError("Alias target missing")


def publish_locked(root: Path | None = None) -> dict:
    started = time.monotonic()
    root = root or settings().catalog_storage_path
    now = datetime.now(timezone.utc)
    version = now.strftime("%Y%m%dT%H%M%S%fZ-") + uuid4().hex[:12]
    data = construct(version, now)
    validate(data)
    root.mkdir(parents=True, exist_ok=True)
    previous = json.loads((root / "current.json").read_text())["version"] if (root / "current.json").exists() else None
    temporary = root / (".building-" + version)
    temporary.mkdir()
    try:
        for name, value in (("snapshot", data), ("bootstrap", data["bootstrap"]), ("catalog", data["catalog"])):
            _write(temporary / f"{name}.json", value)
        _sync_directory(temporary)
        temporary.rename(root / version)
        _sync_directory(root)
        _write(root / ".current.tmp", {"version": version, "previous": previous})
        os.replace(root / ".current.tmp", root / "current.json")
        _sync_directory(root)
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)
    logger.info(json.dumps({"event": "catalog_published", "version": version,
                            "publication_seconds": round(time.monotonic() - started, 3), "total": len(data["catalog"]["items"])}))
    # Retention failure cannot retract an already committed publication.
    try:
        cutoff = (now - timedelta(days=7)).timestamp()
        for path in root.iterdir():
            if VERSION.fullmatch(path.name) and path.name not in {version, previous} and path.stat().st_mtime < cutoff:
                shutil.rmtree(path)
    except OSError as error:
        logger.error(json.dumps({"event": "catalog_retention_failed", "error_type": type(error).__name__}))
    return data["bootstrap"]


def current_version() -> str:
    try:
        return json.loads((settings().catalog_storage_path / "current.json").read_text())["version"]
    except (OSError, ValueError, KeyError):
        raise HTTPException(503, "Catalog has not been published") from None


@lru_cache(maxsize=8)
def _read(path: str):
    return json.loads(Path(path).read_bytes())


def read_data(version: str | None = None, name: str = "snapshot") -> dict:
    version = version or current_version()
    if not VERSION.fullmatch(version):
        raise HTTPException(410, "Catalog generation expired")
    path = settings().catalog_storage_path / version / f"{name}.json"
    if not path.is_file():
        raise HTTPException(410, "Catalog generation expired")
    return _read(str(path))


def current_data() -> dict:
    return read_data()


def detail_data(slug: str, version: str | None = None) -> dict:
    data = read_data(version)
    aliases = data["bootstrap"]["aliases"]
    while slug in aliases:
        slug = aliases[slug]
    result = data["details"].get(slug)
    if result is None:
        raise HTTPException(404, "Project not found")
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["publish"])
    parser.parse_args()
    with pipeline_lock() as acquired:
        if not acquired:
            raise RuntimeError("Another catalog pipeline is running")
        bootstrap = publish_locked()
    from .tasks import refresh_catalog
    refresh_catalog.delay(bootstrap["version"])
    print(json.dumps({"version": bootstrap["version"], "total": bootstrap["total"]}))


if __name__ == "__main__":
    main()
