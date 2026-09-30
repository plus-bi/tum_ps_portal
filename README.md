# TUM Project Opportunities Portal

Independent, bilingual discovery portal for Project Studies advertised by 32 TUM School of Management chairs, Informatics Interdisciplinary Projects (IDPs), and other TUM projects. The repository contains a FastAPI ingestion/API service, a Next.js web app, PostgreSQL/Redis/Celery deployment configuration, and deterministic scraper contracts.

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

The audited Project Study inventory is `tum_project_study_chairs.json`. `tum_idp_sources.json` records 28 chair sources alongside the [official Informatics IDP hub](https://www.cit.tum.de/en/cit/studies/degree-programs/master-informatics/interdisciplinary-project/). `tum_other_sources.json` currently contains TUM Data Innovation Lab, whose projects are shown as Others because the source does not identify them as IDPs or Project Studies. `backend/app/ingestion/registry.py` validates all three inventories. Run `python -u scripts/audit_chair_sources.py` to refresh frozen source fixtures and their hash manifest.

The production Celery task fetches live sources daily at 03:00 Europe/Berlin. Frozen fixtures are retained exclusively for deterministic parser tests and manual audits. Each live attempt is recorded in `crawl_runs`; failed or partial crawls do not advance missing-listing archival state.

Run `python -u scripts/audit_robots.py` before production crawls to refresh `compliance/robots/`. The fetcher fails closed when an origin has no cached policy, when robots retrieval was unavailable, or when the requested path is disallowed.

Adapters use the generic `typo3`, `squarespace`, and `legacy_html` parsers unless `backend/app/ingestion/specialized.py` assigns a source-specific parser. That module shares reusable section, document, table, and list extractors for both Project Studies and IDPs. Add a new parser by registering its chair slug there, scoping any child URLs in the registry, and adding a deterministic fixture contract. Energy Management Technologies follows only its audited external wiki link; the cached wiki policy requires a 60-second delay. The live fixtures intentionally contain source material only and must never be served by the public application.

## Safety and lifecycle guarantees

- Project types come from the audited source and its scoped offer section. Source-specific parsers can accept a title without a type label when the section supplies that context; the Data Innovation Lab is classified as Others. Generic parsing rejects theses, jobs, internships, and completed/archive sections.
- Failed crawls never change listing status.
- A listing is archived only after two consecutive successful crawls in which it is absent.
- Same-chair source keys are consolidated; cross-chair listings remain independent.
- Deterministic discovery runs before optional OpenAI enrichment. Scraped text is untrusted, tools are disabled, and model output is validated.
- Manual overrides are stored separately and take precedence over subsequent extraction.

This is not an official TUM service. Applications always continue at the original chair source.
