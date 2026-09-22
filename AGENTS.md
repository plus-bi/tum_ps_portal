# Repository Guidelines

## Project Structure & Module Organization

- `backend/app/` contains the FastAPI application, authentication, database models, task entry points, and ingestion logic. Keep chair-specific extraction behavior in `backend/app/ingestion/`.
- `backend/app/ingestion/live.py` is the production crawl path. `service.py` intentionally remains the frozen-fixture ingestion path used for deterministic development and tests.
- `backend/tests/` holds pytest tests; reusable captured source material lives in `backend/tests/fixtures/`.
- `frontend/app/` is the Next.js App Router UI, with localized routes under `frontend/app/[locale]/` and global styles in `globals.css`.
- `compliance/robots/` stores cached robots policies. `tum_project_study_chairs.json` is the audited source inventory. Treat both as controlled crawl inputs.
- `compose.yaml`, `Caddyfile`, and the Dockerfiles define the local and production service topology.
- `docs/deployment-gcp-vm.md` is the operational runbook for the supported single-VM deployment.

## Build, Test, and Development Commands

From the repository root:

```bash
cp .env.example .env       # create local configuration; never commit .env
docker compose up --build  # run proxy, web, API, worker, database, and Redis
python -m pytest -q        # run backend tests (requires Python 3.12+)
```

For frontend-only checks, run commands from `frontend/`:

```bash
npm install
npm run dev        # Next.js development server
npm run typecheck  # TypeScript validation
npm run build      # production build
```

Refresh crawler contracts deliberately with `python -u scripts/audit_chair_sources.py`; refresh cached robots policies before production crawls with `python -u scripts/audit_robots.py`.

Production ingestion is scheduled by Celery Beat at 03:00 Europe/Berlin. Useful operational commands are:

```bash
docker compose logs --since=24h worker beat
docker compose exec -T worker celery -A app.tasks call app.tasks.ingest_all
docker compose exec -T worker celery -A app.tasks call app.tasks.ingest_source --args='["chair-slug"]'
```

Do not add a second external schedule while Celery Beat is enabled. The PostgreSQL advisory lock intentionally skips overlapping ingestion runs.

## Coding Style & Naming Conventions

Use four spaces for Python and two spaces for TypeScript/CSS. Prefer explicit type annotations for backend interfaces and idiomatic React function components. Name Python modules and functions in `snake_case`, classes in `PascalCase`, and React components/files in `PascalCase` when component-specific. Keep ingestion selectors, source URLs, and inclusion/exclusion rules narrowly scoped to the owning chair adapter.

Use structured JSON event messages for ingestion logs and include a chair slug, source URL, and crawl-run ID when available. Never log scraped document bodies, credentials, authentication headers, or webhook payloads.

## Ingestion Safety Invariants

- Every live source request must pass through `PoliteFetcher` so cached robots rules, domain throttling, retry limits, redirect checks, timeouts, and response-size limits remain enforced.
- A source-level failure must create or update a `crawl_runs` record and increment source health counters, but must not change listing lifecycle state.
- A partial crawl may upsert observed listings but must not increment missing counts. Archive only after two complete successful source crawls miss the listing.
- Keep child traversal restricted to each adapter's audited `child_url_patterns`; never introduce an unrestricted site crawl.
- Use conditional requests for top-level sources and retain hashes/extracted text internally. Do not publicly mirror downloaded source documents.
- Frozen fixtures and live ingestion serve different purposes: tests must remain deterministic and must not contact live chair websites.

## Testing Guidelines

Add or update pytest coverage for backend behavior in `backend/tests/test_<feature>.py`; name tests `test_<expected_behavior>`. Favor deterministic fixture tests over live requests. Validate parsing changes against representative HTML in `backend/tests/fixtures/`, including rejected content and failure cases. Run `python -m pytest -q` before opening a pull request; run `npm run typecheck` and `npm run build` for UI changes.

Changes to live ingestion must cover both a successful crawl and the guarantee that failed or partial crawls cannot archive listings. Mock HTTP with `httpx.MockTransport`; live network smoke tests are manual deployment checks and never part of CI.

## Commit & Pull Request Guidelines

The available history starts with a concise imperative commit (`first commit`); continue with short, imperative subjects such as `Add chair adapter validation`. Keep commits focused. Pull requests should explain the user-facing or ingestion impact, list validation commands run, link the relevant issue when available, and include screenshots for visible UI changes. Never commit `.env`, credentials, API keys, or live scraped content intended only for test fixtures.

Before a VM deployment, validate `docker compose config --quiet`, take a PostgreSQL backup before schema changes, and follow `docs/deployment-gcp-vm.md`. Preserve the `postgres_data`, `caddy_data`, and `caddy_config` volumes during updates and rollbacks.
