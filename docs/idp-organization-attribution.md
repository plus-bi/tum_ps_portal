# IDP organization attribution

The Informatics IDP Hub is a listing source, not automatically the academic unit for every PDF it links. Each PDF-backed offer can have TUM academic units and project partners. Both lists may be empty, and a missing partner is **not** evidence that there is no partner. Source ownership stays in `listings.chair_id` so crawl lifecycle behavior remains intact.

`organization_attributions` stores one versioned row per listing, PDF content hash, and extractor version. Each mention contains the name as written, an optional canonical name, a 1-indexed PDF page and excerpt, and the extraction method. Candidates begin with `needs_review`; public catalog responses use only `approved` rows. To inspect candidates locally, set `ORGANIZATION_ATTRIBUTION_PREVIEW=true` in the local `.env` and use a localhost `PUBLIC_URL`; restart the API to load the setting. The API ignores an attribution when its PDF hash no longer matches the listing's linked artifact.

The extractor reads existing `pdf_analysis.extracted_markdown_pages`. It looks for registered TUM names and explicit chair or institute headings in the first-page header, then uses a stated `provider_name` as another candidate. A registered TUM name or academic heading becomes a TUM unit; another provider becomes a project partner. These are **review candidates**, not verified supervision or funding claims. Ambiguous multi-offer PDFs are skipped until the offer can be linked to the listing uniquely. No web crawl, PDF download, or model call is made.

## Review workflow

Run the command from a backend environment with `DATABASE_URL` pointing to the intended database. It is read-only by default:

```bash
python -m app.ingestion.organization_backfill --limit 20 --output /tmp/organization-candidates.jsonl
```

Inspect each PDF page and excerpt in the report. Remove unsupported entries, correct names and roles, and add cited entries that the extractor missed. Set `"approve": true` on a row only after checking it. Leave unreviewed rows without that flag. The approval command checks that the linked PDF has not changed and that every remaining name and excerpt occurs on the cited page.

Each review row has a `PS-###` or `IDP-###` review ID, project title, reference code, and original PDF URL. The numbers are assigned separately by course type in slug order for this report; use `slug` and `listing_id` as stable identifiers when comparing regenerated reports. The generated root-level `organization-candidates.jsonl` is ignored by Git because it contains live source material.

After a database backup, apply Alembic revision `0006`, then store candidates without publishing them:

```bash
alembic upgrade head
python -m app.ingestion.organization_backfill --apply
python -m app.ingestion.organization_backfill --approve-file /tmp/organization-candidates.jsonl
```

The apply command is resumable for the same listing, PDF hash, and extractor version. Regenerate the report before reviewing a changed PDF. A failed or skipped extraction does not alter a previously approved attribution, and the catalog uses only an attribution matching the current PDF hash. The production schema step belongs in the VM deployment runbook and requires a PostgreSQL backup first. Do not run the write commands during an active profile backfill without checking the operational impact.

The catalog has one Organizations search box. It searches both TUM unit and project partner names; suggestions show the role. Selecting multiple organizations matches any selected name, then combines with other filters. A card may display `BayWa r.e. / Chair of Spacecraft Systems` while the underlying two roles and source citations remain separate.
