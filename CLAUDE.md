# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

`AGENTS.md` is the authoritative source for repository conventions, ingestion safety invariants, and commit/PR rules. Read it first; this file adds commands and architecture context without repeating it.

## Commands

```bash
pip install -e '.[test]'                    # backend deps (Python 3.12+)
python -m pytest -q                         # all backend tests (pythonpath=backend is set in pyproject.toml)
python -m pytest backend/tests/test_live_ingestion.py::test_failed_live_crawl_is_logged_without_changing_listing_lifecycle
python -m pytest -k adapters                # subset by keyword

cd frontend && npm ci && npm run typecheck && npm run build   # what CI runs for the UI
# CI build needs NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY set; any fake pk_test_ value works (see .github/workflows/ci.yml)

docker compose up --build                   # full stack at http://localhost:8080, API docs at /api/docs
docker compose --profile maintenance up pdf-backfill   # optional PDF backfill loop
docker compose --profile maintenance run --rm profile-backfill   # LLM profile extraction, --dry-run by default
docker compose --profile maintenance run --rm profile-backfill python -m app.ingestion.profile_backfill --limit 20   # real run (Azure OpenAI cost)
docker compose --profile maintenance run --rm profile-backfill python -m app.ingestion.profile_backfill --recheck   # re-run citation checks on stored rows, no model calls
docker compose --profile maintenance run --rm -v tum_ps_portal_artifact_data:/var/lib/portal/artifacts:ro profile-backfill python -m app.ingestion.pdf_analysis   # re-classify stored PDFs (the pdf-backfill image may lack pymupdf4llm until rebuilt)
```

There is no Python linter configured. CI (`.github/workflows/ci.yml`) runs only `pytest` plus frontend `typecheck` and `build`.

## Architecture

**Services** (`compose.yaml`): Caddy proxies `/api/*` to FastAPI (`api`) and everything else to Next.js (`web`). `worker` and `beat` run Celery from the same backend image. Postgres holds all state and Redis is only the Celery broker. PDFs are stored on the shared `artifact_data` volume.

**Source registry** (`backend/app/ingestion/registry.py`): builds `ChairAdapter` objects from the two JSON inventories at the repo root. `tum_project_study_chairs.json` must contain exactly 32 records, or the import fails. `tum_idp_sources.json` feeds the IDP adapters. Per-chair tuning lives in dicts inside `_load_registry` / `_load_idp_registry`, not in the JSON files. That tuning covers `child_url_patterns`, excluded titles, and selector overrides. `ALL_REGISTRY` / `ALL_BY_SLUG` are what tasks and the API consume. Adapter `family` (typo3 / squarespace / legacy_html) selects a parser in `adapters.py`. Today these parsers all share `HtmlParser`.

**Live crawl pipeline** (`backend/app/ingestion/live.py`, entry `run_live` called from `app/tasks.py`):
1. `ingest_live` takes a Postgres advisory lock. It skips if another run holds it. It calls `Base.metadata.create_all`, and that is how the schema gets created at runtime.
2. `discover_adapter` fetches the top URL through `PoliteFetcher` (`fetcher.py` + `robots.py`, which reads `compliance/robots/`). It then does a breadth-first walk of child links, depth ≤ 2. It never touches the DB.
3. Child fetch errors are collected as `failures`. Any failure makes the run `partial`. A partial run increments `Source.consecutive_failures`, and the next run skips the conditional ETag request so the children are retried.
4. `_persist_success` upserts listings keyed by `ChairAdapter.stable_key` (a hash of slug, URL, and normalized title). It applies `ManualOverride` title/summary via `listing_overrides.py` and writes a `ListingVersion` when the content hash changes. It only increments `consecutive_misses` / archives when there are no failures. `lifecycle.after_crawl` is the pure model of this rule.
5. Candidate PDFs are downloaded to the artifact volume. `pdf_backfill.py` / `pdf_analysis.py` handle text-layer analysis separately.

**Frozen-fixture path** (`service.py`): ingests from `backend/tests/fixtures/` for deterministic tests. Refresh the fixtures with `scripts/audit_chair_sources.py`. Don't route production behavior through it.

**API** (`app/api.py`, `app/account_api.py`): `/api/v1/projects` loads all listings and filters/sorts/paginates in Python. If the DB is empty or unreachable, it falls back to a hard-coded demo `PROJECTS` list. Account endpoints use Clerk JWTs (`auth.py`) for bookmarks and saved searches. `deliver_alerts` is currently a stub.

**Frontend** (`frontend/app/[locale]/`): the server component `page.tsx` fetches from `NEXT_PUBLIC_API_URL` with `no-store` and passes the data to `CatalogClient.tsx`. Locale is `en` or `de`, with `de` chosen only when the path segment is `de`. Auth uses `@clerk/nextjs`.

**Schema changes**: models are in `app/db.py`. Alembic lives in `backend/alembic/versions/`, but runtime code relies on `create_all`. `create_all` does not alter existing tables, so new columns on existing tables need an Alembic migration.

## Testing patterns

- DB tests create a temp SQLite engine and `monkeypatch.setattr(app.db, "_engine", engine)`, then call `ingest_live(adapters, FakeFetcher(...))` directly. See `test_live_ingestion.py`.
- Fetcher-level tests build `PoliteFetcher(delay_seconds=0, robots=..., transport=httpx.MockTransport(handler))`.
- Settings default to `sqlite:///./portal.db` when `.env` is absent (`app/config.py`, `lru_cache`d).
