# Persistent catalog publication and caching

Visitor requests read immutable catalog generations from `catalog_data`; they never build the catalog from PostgreSQL. The worker publishes after eligible completed crawls and enrichment under a pipeline advisory lock. Failed and skipped crawls leave the current generation intact. Snapshot construction uses a repeatable-read transaction, validates records and aliases, fsyncs files, and atomically replaces `current.json`. Database or validation failures propagate from the maintenance command. A genuinely empty catalog is valid. Generations older than seven days are removed except the current and previous generations.

Bootstrap includes the first 20 active records in pinned/date order, real totals, profile facet counts, chair metadata, aliases, published filter fields and generation metadata. Compact organizations contain display names; full evidence remains in detail payloads. Legacy project endpoints retain their shapes but read the published snapshot. No publication returns 503, and expired versions return uncached 410. The browser refreshes bootstrap and retries an expired download once.

Public bootstrap and legacy responses use browser revalidation with a five-minute shared TTL. Versioned compact/detail responses use ETags and one-year immutable caching. Account, administrative, contact and webhook routes use private/no-store. Caddy compresses HTML/JSON/CSS/JS without replacing Next.js navigation Vary headers. Catalog/detail pages and server fetches revalidate after 24 hours; publication invalidates tags and paths immediately through an authenticated endpoint, then prewarms both locales. Celery retries failures and Beat reconciles every five minutes. This adds no ingestion schedule.

The root browser provider retains the dataset/in-flight download and search, selected types, profile filters, unknown controls, age bands, pagination, display size and saved mode across locale navigation. Cookies remain browser-only. Full-catalog controls stay disabled until download completes; initial cards and real counts are available from HTML. Dataset preparation and facet counts are memoized; search filtering is deferred and cards are memoized. Detail links disable automatic prefetch; language controls prefetch on intent.

## Isolated verification

Never run staging by overlaying production Compose: that can recreate live services. Use the dedicated file and explicit project:

```bash
docker compose -p tum-catalog-staging -f compose.catalog-staging.yaml build
docker compose -p tum-catalog-staging -f compose.catalog-staging.yaml run --rm publisher
docker compose -p tum-catalog-staging -f compose.catalog-staging.yaml up -d
python scripts/check_catalog_browser.py
python scripts/benchmark_catalog.py http://127.0.0.1:8187 --output /tmp/catalog-staging-timings.json
```

The fixture publisher refuses any database URL except `fixture.db`. Staging does not load `.env`, uses its own volume, and binds only loopback 8187. It has no Beat. The refresh credential in this file is only for synthetic staging data. Browser checks require Playwright and its Chromium runtime. To stop staging, use the same explicit project/file with `stop`; preserve its volume until results are reviewed.

## Staged production rollout

Keep Nginx/Certbot -> loopback Caddy -> web/API. Keep one API process because account stores remain process-local. Do not change memory limits. Worker and maintenance CPU quotas are one CPU; Celery concurrency is one.

1. Finish isolated checks. Record existing application image IDs for rollback. Check `docker compose ps` and `celery -A app.tasks inspect active`; wait for ingestion and manual backfills before recreating worker containers. Validate `docker compose config --quiet`. No database migration is needed.
2. Set a randomly generated `CATALOG_REVALIDATION_SECRET` in the existing private `.env` without printing it. Web and worker must share it. Preserve every existing volume, including artifacts.
3. Build application images with the lockfile (`npm ci`, Next.js 16.3.6). Run `docker compose up -d artifact-init` to initialize writable snapshot storage. Publish from the existing database using `docker compose run --rm --no-deps worker python -m app.catalog_snapshot publish`. The CLI publishes without crawling or LLM work. If the old web has no refresh endpoint yet, the queued notification retries and reconciliation recovers after release.
4. Recreate API/worker/Beat with the new images and read-only API catalog mount; verify `/api/v1/catalog` returns the published version. Release web and reload Caddy for gzip. Do not stop the live proxy or change its bound ports.
5. Queue `app.tasks.refresh_catalog` and confirm `catalog_refresh_acknowledged` plus the same generation in both rendered locale pages. Verify gzip, cache-control/ETag, and retained Vary headers. Run public timing checks from the same client location used for baseline.
6. Roll back application images on failed checks. Keep `catalog_data` and all original volumes. Never use `down -v`.

Structured events include publication version/duration, refresh acknowledgement, notification/publication failure, overdue refresh (> five minutes), and stale publication (>36 hours). Connect ERROR events to the VM's existing log alerting; no external alert destination is configured by this change. Do not log search terms, cookies, document bodies, or credentials.

## Acceptance measurements

Measure 30 warm sequential requests and 30 requests at concurrency ten with gzip from the same client. Targets: sequential p95 <500 ms, concurrent p95 <800 ms; browser language switch p95 <300 ms, typical interactions <200 ms; throttled mobile median LCP <2.5 s; both locale versions refreshed within five minutes. Benchmark All separately. Fixture measurements establish regression behavior, not production acceptance. Also repeat after API/web restarts and while a representative fixture ingestion workload is running. Do not claim mobile or live-ingestion performance without measured evidence.

## Verified rollout, 2026-10-01

Production snapshot `20261001T115455406339Z-55d8ae3a9428` contains 432 active projects. The VM release completed without recreating PostgreSQL, Redis or Caddy and without removing any volume. Both locale pages return `x-nextjs-cache: HIT`, gzip and the complete Next.js navigation Vary set. The authenticated refresh task prewarmed and acknowledged both pages in 0.558 seconds. The initial publication completed before API/frontend replacement.

Validation: 234 backend tests passed, ten existing parser-contract tests skipped; frontend typecheck and `npm ci`/production build passed with Next.js 16.3.6; both Compose configurations and `git diff --check` passed. Production-mode Playwright checks passed in staging and on the real published catalog (initial 20 HTML cards, real total, disabled controls before readiness, one dataset download across locales, search/display/pagination preservation, empty type selection, saved mode across languages, cookie isolation, detail-language navigation, download failure/retry).

Measured results (milliseconds; JSON data in `catalog-validation-results.json`):

| Check | EN | DE |
|---|---:|---:|
| Public warm TTFB p95, 30 requests | 64.0 | 37.5 |
| Public TTFB p95, concurrency ten | 275.7 | 177.5 |
| Loopback warm TTFB p95 | 14.5 | 12.7 |
| Loopback concurrent TTFB p95 | 100.5 | 49.5 |

Production browser language switching p95: 246.7 ms. Search interaction including automation and two animation frames: 66.7 ms with 20 display, 101.2 ms with 100, 97.2 ms with All (search reduces the rendered set). All remains a separate stress measurement, not a guarantee for unbounded catalog sizes. Production mobile median LCP: 1.088 s over five cold contexts, viewport 390x844, 150 ms network latency, 200,000 bytes/s download, 93,750 bytes/s upload, CPU slowdown four. Staging retained snapshots after API/web restart and stayed below the TTFB targets.

The original public baseline run timed out during the concurrency-ten phase; the loopback baseline was interrupted by application replacement and returned 502. No complete before/after percentage is claimed; the earlier plan's 3.8–4.3 s estimate remains a supplied baseline. Initial simultaneous API/web startup produced transient connection-refused render failures; the refresh/prewarm task recovered, and subsequent live verification succeeded. Use API-first rollout and health verification to avoid that transient on future releases.

Remaining operational verification: document-conversion/LLM peak workloads have not been benchmarked; the deterministic captured-chair parser workload checks CPU contention only. ERROR log events are implemented, but delivery to an external alert destination is not configured. The existing log platform must route those events for operational paging.

Captured-chair workload verification: 767 deterministic HTML parser executions under a one-CPU maintenance quota; staging warm p95 stayed at 9–10 ms and concurrency-ten p95 at 75–76 ms. Staging containers were stopped after verification, preserving their volume.
