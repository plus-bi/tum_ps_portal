# TUM Project Opportunities Portal

Independent, bilingual discovery portal for Project Studies advertised by 32 TUM School of Management chairs and Informatics Interdisciplinary Projects (IDPs) published by the official CIT hub and its linked chair sources. The repository contains a FastAPI ingestion/API service, a Next.js web app, PostgreSQL/Redis/Celery deployment configuration, and deterministic scraper contracts.

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

The audited Project Study inventory is `tum_project_study_chairs.json`. `tum_idp_sources.json` records the 30 chair links currently published by the [official Informatics IDP hub](https://www.cit.tum.de/en/cit/studies/degree-programs/master-informatics/interdisciplinary-project/), alongside the hub itself. Both are validated into dedicated adapters by `backend/app/ingestion/registry.py`. Run `python -u scripts/audit_chair_sources.py` to refresh frozen source fixtures and their hash manifest.

The production Celery task fetches live sources daily at 03:00 Europe/Berlin. Frozen fixtures are retained exclusively for deterministic parser tests and manual audits. Each live attempt is recorded in `crawl_runs`; failed or partial crawls do not advance missing-listing archival state.

Run `python -u scripts/audit_robots.py` before production crawls to refresh `compliance/robots/`. The fetcher fails closed when an origin has no cached policy, when robots retrieval was unavailable, or when the requested path is disallowed.

Adapters share three parser families (`typo3`, `squarespace`, and `legacy_html`) while retaining chair-owned source URLs, candidate selectors, inclusion/exclusion markers, and narrowly scoped child-link patterns. The live fixtures intentionally contain source material only and must never be served by the public application.

## Safety and lifecycle guarantees

- Only candidates with explicit Project Study or IDP terminology are accepted; theses, jobs, internships, and completed/archive sections are rejected. The official IDP hub's dedicated project-document list is the sole source whose position supplies the IDP context when an individual document title omits it.
- Failed crawls never change listing status.
- A listing is archived only after two consecutive successful crawls in which it is absent.
- Same-chair source keys are consolidated; cross-chair listings remain independent.
- Deterministic discovery runs before optional OpenAI enrichment. Scraped text is untrusted, tools are disabled, and model output is validated.
- Manual overrides are stored separately and take precedence over subsequent extraction.

This is not an official TUM service. Applications always continue at the original chair source.
