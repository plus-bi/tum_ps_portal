# TUM Project Studies Portal

Independent, bilingual discovery portal for Project Studies advertised by the 32 TUM School of Management chairs in Munich. The repository contains a FastAPI ingestion/API service, a Next.js web app, PostgreSQL/Redis/Celery deployment configuration, and deterministic scraper contracts.

## Quick start

```bash
cp .env.example .env
docker compose up --build
```

Open `http://localhost:8080`. API documentation is at `http://localhost:8080/api/docs`. Set `PORTAL_HTTP_PORT` in `.env` if you want another host port.

For a production deployment on a Google Cloud VM, follow [docs/deployment-gcp-vm.md](docs/deployment-gcp-vm.md). It covers DNS and TLS, secrets, service startup, the daily ingestion schedule, backups, monitoring, and updates.

For local backend checks without Docker:

```bash
python -m pytest -q
```

The audited chair inventory is `tum_project_study_chairs.json`; it is validated into 32 dedicated adapters by `backend/app/ingestion/registry.py`. Run `python -u scripts/audit_chair_sources.py` to refresh frozen source fixtures and their hash manifest. The current fixture set contains 31 successful captures and records the known Marketing and Technology 404 without inventing content.

Run `python -u scripts/audit_robots.py` before production crawls to refresh `compliance/robots/`. The fetcher fails closed when an origin has no cached policy, when robots retrieval was unavailable, or when the requested path is disallowed.

Adapters share three parser families (`typo3`, `squarespace`, and `legacy_html`) while retaining chair-owned source URLs, candidate selectors, inclusion/exclusion markers, and narrowly scoped child-link patterns. The live fixtures intentionally contain source material only and must never be served by the public application.

## Safety and lifecycle guarantees

- Only candidates with explicit Project Study terminology are accepted; theses, IDPs, jobs, internships, and completed/archive sections are rejected.
- Failed crawls never change listing status.
- A listing is archived only after two consecutive successful crawls in which it is absent.
- Same-chair source keys are consolidated; cross-chair listings remain independent.
- Deterministic discovery runs before optional OpenAI enrichment. Scraped text is untrusted, tools are disabled, and model output is validated.
- Manual overrides are stored separately and take precedence over subsequent extraction.

This is not an official TUM service. Applications always continue at the original chair source.
