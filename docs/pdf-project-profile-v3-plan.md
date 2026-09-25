# PDF project profile v3: proposed changes

Status: **steps 1–4 implemented; labels are drafts awaiting review.** See
[Implementation status](#implementation-status) at the end. The plan combines two sources:

- a static review of `project_profile.py`, `llm_client.py`, `profile_evidence.py` and `pdf_reader.py`;
- 10 Azure calls on 2026-09-25. The calls compared the current v2 schema and prompt with an
  experimental variant on four PDFs: the three fixed notebook samples and the 8-offer Fraunhofer
  FIT PDF.

The review comments on the first draft are included. Where they differed from the draft, the
review's position is used and noted below.

The experiment scripts and raw outputs are in `/tmp/ppx/`. That directory is not in the repo and
is temporary. `variant.py` holds the variant schema and prompt. Each run's JSON has the token
counts, citation issues and the full profile.

## What the experiment showed

| Run | Input tok | Output tok | Time | Citation issues | Notes |
|---|---|---|---|---|---|
| v2 wiwamedia (de) | 3.3k | 2.8k | 14 s | 0 | good |
| v2 JAX-Fluids (en) | 3.2k | 2.4k | 12 s | 1 | false alarm from the checker, see §5 |
| v2 FIDENTIS (mixed) | 3.3k | 2.8k | 13 s | 0 | good |
| v2 FIT (8 offers) | 9.3k | 2.6k | 13 s | 0 | **only offer 1 returned; 7 silently lost** |
| variant, same four | 2.7k–8.7k | 1.7k–11.4k | 9–44 s | 0 | FIT split into 8 correct offers |
| variant de, medium effort | 2.8k | 3.5k (852 reasoning) | 17 s | 0 | slightly cleaner work modes |
| variant de, repeat (low) | 2.8k | 2.9k | 14 s | 0 | variance check |

**Worked:**

- **Offer splitting.** All 8 FIT offers came back with the correct titles and page ranges. The
  contact changes from Weibelzahl to Körner at page 5, and each offer got the right one.
- **English summaries and tags.** `search_summary_en` was accurate and neutral in all 11 offers,
  including the German one. Per-item `tag_en` values were fairly stable across three German runs.
- **One prerequisite list with a strength.** Every run classified strength correctly: "Beneficial:
  JAX" and "robotics desirable" became recommended. Degree level stopped leaking into prerequisites.
- **Date normalization.** "1st of October 2024 earliest" became `2024-10-01`. That start date is
  already past, so it could flag an expired offer.

**Failed or unstable:**

- **`work_modes`.** On the vague German offer, `software_development` appeared in 2 of 3 runs.
- **Deliverables.** One of three German variant runs invented a deliverable from an activity. The
  v2 prompt did not, because its wording on deliverables is stronger.
- **Location.** For FIDENTIS, the company blurb "Munich metropolitan region" became the work
  location. For wiwamedia, `remote_policy=hybrid` was chosen because a coworking space is only
  "in Planung" (planned).
- **FIT offer 6.** It was labeled `programming_involvement=none` without any explicit statement.
  Under the rule in §2, that should have been `unknown`.
- **Medium reasoning effort.** It used 3.4× the reasoning tokens and took +3 s. One sample cannot
  decide the setting (§8).

The three German runs (low, medium, low repeat) also differed in how finely they split
prerequisites. Item granularity is not stable, so evaluation must match items semantically rather
than one-to-one.

---

## 1. Multiple offers per document (priority 1)

**Change.** Replace the top-level `ProjectProfile` with a document wrapper:

```python
class DocumentExtraction(BaseModel):
    document_language: Literal["de", "en", "mixed", "other", "unknown"]
    document_kind: Literal["offer", "multi_offer", "not_an_offer", "unknown"]
    offers: list[OfferProfile]

class OfferProfile(BaseModel):
    source_pages: list[int]          # every page this offer draws facts from; may overlap other offers
    ...                              # current ProjectProfile fields, see §3–§4
```

**Rationale.** A correct single profile is impossible for the FIT PDF. The current extractor
silently returns offer 1 and drops the others, and nothing flags the loss.

In the variant, `page_start`/`page_end` worked for FIT. The review points out that page ranges are
too restrictive when offers share a page or span pages that are not contiguous. `source_pages`
(a list, with overlap allowed) covers both cases.

Shared boilerplate, such as the company description or the application process, may be cited by
several offers.

**Evaluation.** Check:

- offer count;
- offer boundaries (the `source_pages` for each offer);
- the contact for each offer;
- fact leakage: an item in offer A whose evidence is on a page used only by offer B.

The leakage check can be automated from `source_pages` plus the citations. The first three need
labels.

**Downstream impact.** `ProfileExtraction`, `check_profile_evidence` and future persistence all
need to handle a list of offers. Linking offers to listings is out of scope here. The "Split
aggregate opportunity listings" work may need an equivalent for PDFs.

## 2. Work modes and programming involvement (priority 2)

**Change.** Add these per-offer fields:

```python
work_modes: ListField[WorkMode]        # every item needs evidence from the stated activities
programming_performed: Literal["none", "some", "central", "unknown"] + evidence
programming_required_skill: Literal["required", "recommended", "not_stated"] + evidence
```

A starting `WorkMode` enum, taken from the experiment: `software_development`,
`data_analysis_ml`, `modeling_simulation`, `hardware_lab`, `literature_research`,
`empirical_user_research`, `business_strategy`, `process_optimization`, `marketing_content`,
`design_ux`.

**Rationale.** These fields support the "kind of work" searches in
`student-project-discovery.md` (§"Filtering by the work students will actually do"). None of the
current fields can be filtered this way.

Following the review, programming *performed during the project* is kept separate from
programming *required as a skill*. A project can require Python and still be mostly analysis, or
the reverse.

**Rules:**

- Silence yields `unknown`. `none` needs an explicit statement. "Purely qualitative" alone does
  not prove `none`. FIT offer 6 shows the model will guess `none` otherwise.
- `work_modes` needs evidence for each item. It was unstable across repeats, so it is used for
  ranking only until reviewers agree on the labels.
- A "no programming" filter is published only after reviewers agree on the labels over the
  evaluation set (§8).

## 3. Recoverable extraction failures (priority 3)

**Change:**

- On a Pydantic `ValidationError` (or a refusal or empty parse), retry once. Include the
  validation error message in the retry input.
- If the retry also fails, record a failed extraction with the error, prompt hash and model.
  **Keep any previous good extraction** for the same content hash, and do not overwrite it.
- Keep explicit unknown states. `stated: bool` stays on `TextField` and `ListField`. The review
  asked to keep it, and this reverses the first-draft idea of dropping it.

**Rationale.** The constrained JSON schema cannot express the cross-field rules in
`TextField.check_stated_value` / `ListField.check_stated_items`, or `min_length` on evidence. So a
model can produce schema-valid JSON that then fails validation, which currently ends the call.
None of the 10 calls failed, but at corpus scale the failures will add up.

## 4. Field definitions

| Change | Rationale |
|---|---|
| **Degree level.** "Bachelor or Master" produces two values. Remove `DegreeLevel.any`, or reserve it for an explicit all-levels statement. | `any` is ambiguous today. Two explicit values filter correctly. |
| **Engagement form** (internship, Werkstudent, thesis, …) becomes its own dimension, separate from `ProjectType`. | It describes the employment or contract form, not the academic format. The same offer can be an IDP *and* paid. |
| `team_size` stays its own field. | It is a separate dimension from project type. |
| `eligible_study_fields` stays separate from skills, even when one sentence supports both. | The FIDENTIS sentence "Team: 2-5 persons, studying Informatics…" was split correctly in both schemas. |
| Compare **one `prerequisites` list with `strength: required\|recommended`** against the current two lists. | The single list classified strength correctly in 4/4 runs. The review wants a paired comparison before switching. |
| Add optional derived `normalized` values to `start_date` and `application_deadline` (ISO date, `WiSe2026/27`-style semester code, `asap`, `flexible`), keeping the quoted wording. | Enables the semester facet and stale-offer detection. It worked on FIDENTIS and FIT. |
| Add `work_location_mode: on_site\|hybrid\|remote\|unknown`, only from explicit statements about where the student works. | Stricter location wording is needed, based on the FIDENTIS and wiwamedia errors above. |
| Add compensation, ECTS/workload and TUM supervisor **only if the evaluation-set coverage shows they occur**. | Avoids fields that are nearly always empty. FIT names a TUM supervisor (Prof. Schwenen), so the supervisor field has at least one case. |
| Evidence stays **item-level on all fields**, including subjects and learning opportunities. | The review's position: these fields drive search matches and need to be auditable. This withdraws the first-draft suggestion to drop quotes there. The cost is acceptable, at about 3k output tokens for a typical document. |

**Prompt.** Keep the v2 wording on deliverables, prerequisites and learning/support. The variant's
shorter wording invented a deliverable. Add only the new rules for offer splitting, work modes,
programming, location mode and date normalization.

## 5. Quote checker

**Change.** Extend `_normalize_quote` only for failures observed on real excerpts, and add a
regression test for each:

- **Observed:** whitespace before punctuation. The source has `**Testing differentiability** :`,
  which normalizes to `differentiability :`, while the model quoted `differentiability:`.
  Collapse `\s+([:;,.!?])` to `\1`.
- **Present in the Markdown but not yet a failure:** `~~` (on every FIT heading), `−` (U+2212)
  and `▪` bullet glyphs. Add them when a real failing excerpt shows up, with that excerpt as the
  test case.
- `<sup>` already has a passing normalization test, so no change.

**Rationale.** False alarms make citation issues noisy, and noisy issues get ignored. The review
asks for changes driven by real failures rather than guessed ones.

## 6. Search representations

**Change.** No search representation is chosen yet. Evaluate these separately, using German and
English queries:

1. embedding of the source-language profile text (concatenated fields);
2. embedding of an English summary per offer;
3. embedding of a bilingual summary.

**Rationale.** In the experiment, `search_summary_en` was accurate on all 11 offers. The review
asks that the summary be **generated per offer from verified facts**: after citation checks, not
freely in the same call. Two ways to evaluate this:

- (a) keep an in-call summary, and have a second check verify that each sentence is supported by
  cited items;
- (b) generate the summary in a second, cheap call that sees only the verified items.

(b) matches the review's intent more closely. It costs one extra call per offer.

**Tags.** Model-generated `tag_en` values are kept only as **translation suggestions**. Stable
facets come from a separately versioned, curated taxonomy (`student-project-discovery-review.md`
§"Version taxonomy mappings and embeddings separately"). A taxonomy change then re-maps stored
extractions without re-extracting.

## 7. Input handling

- **Short documents.** Flag for review or OCR assessment instead of skipping them. Some offers are
  genuinely terse. In the corpus, the only document under 300 chars is the scanned one (4 chars,
  `7dd51654…`), which is already `no_text`. The shortest digital documents are 576–867 chars
  (`a731392c…`, `0cad2915…`, `2dd69f73…`). These belong in the evaluation set to check terse
  extraction.
- **Settings path.** `AZURE_OPENAI_ENDPOINT` must be in `.env`. The shell had only
  `AZURE_ENDPOINT_URL`. `settings()` reads `.env` relative to the working directory, so the
  notebook or scripts need to run from the repo root. This is worth noting in the notebook.

## 8. Evaluation set and experiment order

**Evaluation set.** Hand-labeled and fixed, stored with the notebook samples. It should include:

- the FIT PDF (8 offers, one per page, two contacts);
- at least one PDF with **several offers on one page** (candidates still to be found);
- at least one offer **spanning several pages**;
- the three short digital documents above;
- the three current fixed samples: German Project Study, English IDP, and the IDP with a blank
  page;
- enough German and English examples to compare languages.

**Labels for each offer:**

- offer count and source pages;
- contact;
- the true items per field, with required/recommended for prerequisites;
- work modes;
- programming performed and programming required.

Two reviewers label work modes and programming, to measure agreement before any filter ships.

**Order:**

1. Build the evaluation set and labels.
2. Implement offer splitting (§1) and recoverable failures (§3). Measure offer count, boundaries,
   contacts and leakage.
3. Add the §2 and §4 fields and the quote-checker fix (§5). Run the paired comparison of one
   prerequisite list against two.
4. Run a **paired low versus medium reasoning comparison** across the whole set. Measure factual
   accuracy, offer separation, citation validity, cost and latency. One German sample was not
   enough to choose a setting.
5. Search representation comparison (§6).
6. Publish filters field by field, only once they pass agreed accuracy thresholds.

**Cost estimate.** A typical 1–2 page document takes about 3k input and 3k output tokens at low
effort. A full run over 247 PDFs is roughly 0.75M input and 0.75M output tokens. Output grows
with offer count: FIT took 11k.

## Decisions (answered)

1. `source_pages: list[int]`, overlap allowed: **approved**.
2. `DegreeLevel.any`: **kept**, only for explicit all-levels statements.
3. Search summary: **generated in the same call** (`search_summary_en`, placed last so it restates
   the extracted facts). Sentence-level verification against cited items is still open (§6).
4. Optional fields (compensation, ECTS/workload, TUM supervisor, engagement form): **not added**.

## Implementation status

**Code (steps 2–3).**

- `project_profile.py` (`project-profile-v3`): `DocumentExtraction` with `document_kind` and one
  `ProjectProfile` per offer, each with `source_pages`. It adds `work_modes`,
  `programming_performed`, `programming_required`, `work_location_mode`, `normalized` on
  `start_date` / `application_deadline`, and `search_summary_en`. `PdfTextCoverage.short_text`
  flags documents under 300 characters; they are still extracted.
- `ProfileExtraction` records `status` (`ok` / `failed`), `attempts`, validation `errors` (no
  document text) and token usage.
- `llm_client.py` (`project-profile-prompt-v3`): retries once after a validation error or empty
  parse, adding the validation messages to the trusted instructions. After the second failure it
  returns `status="failed"`.
- `profile_evidence.py`: citations are checked per offer. A citation from a page outside the
  offer's `source_pages` is flagged as `outside_offer_pages`, a possible leak between offers.
  Three observed false alarms are fixed, each with a regression test: space before punctuation
  after bold marks, typographic quotation marks (`“matching”` for `"matching"`), and `−`/`▪`
  bullet glyphs at line starts. Quotes
  stitched across interleaved columns are still flagged, which is correct.

**Evaluation (step 1).**

- `backend/tests/fixtures/profile_eval/labels.json`: 14 documents (the cases listed above plus a
  synthetic two-offers-on-one-page document). It is keyed by content hash and holds no scraped
  page text. `review_status: draft`: every label, and each `review_notes` entry, needs a
  reviewer.
- `app/ingestion/profile_eval.py`: pure scoring, with tests in `test_profile_eval.py`.
- `scripts/eval_project_profiles.py run|score`: outputs go outside the repo. `--variant
  one-list` runs the single-prerequisite-list schema and maps it back to the two lists, so both
  variants are scored the same way.

**Label review (2026-09-25).** The labels were revised after a review against the stored
Markdown:

- Deliverables now follow the prompt rule below, with a recall check as well as a check for
  invented items.
- Unstated working languages are scored as explicit empty expectations.
- BayWa must list all three contacts.
- The IDPX poster is `not_an_offer`.
- The motorsport flyer expects bachelor and master.
- wiwamedia is `remote` only.

Labels remain `draft`, and the `review_notes` entries explain each non-obvious call. They score
selected fields only, not complete profiles.

**Prompt v3.1.** The deliverable rule now reads: record a deliverable when the offer explicitly
names an output students are expected to create, implement, write, present or submit. A task
bullet counts when it names that output. Do not infer an output from an activity that names none,
exclude optional outputs, and do not turn "deliverables to be defined later" into a specific item.
Abstract outputs such as "an optimization approach" are allowed in the labels but not required.

**Results (14 documents, revised labels, citations rechecked with the current checker).**

| Check | low v3 | medium v3 | one list, low v3 | **low v3.1** |
|---|---|---|---|---|
| failed / retried | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 |
| document kind / offer count | 0.93 | 0.93 | 0.93 | 0.93 |
| boundaries, contact, title, leakage | 1.00 | 1.00 | 1.00 | 1.00 |
| all contacts (BayWa, n=1) | 0 | 1 | 0 | 0 |
| deliverable recall | 0.80 | 0.86 | 0.88 | **1.00** |
| deliverables with no invented item | 0.58 | 1.00 | 1.00 | 0.95 |
| programming performed / required | 0.95 / 0.95 | 1.00 / 1.00 | 1.00 / 0.95 | 1.00 / 1.00 |
| project types | 0.90 | 0.90 | 0.95 | 0.90 |
| work location mode | 0.92 | 1.00 | 1.00 | 1.00 |
| prerequisites, dates, degree, working language | 1.00 | 1.00 | 1.00 | 1.00 |
| citation issues | 0 | 0 | 8 (stitched quotes) | 0 |
| output / reasoning tokens | 46.0k / 3.4k | 55.1k / 13.0k | 46.8k / 3.2k | 49.4k / 3.0k |

The one-list run's 8 citation issues are real: the model stitched quotes across interleaved
columns, 7 of them in one document.

Two more checker false alarms were fixed with regression tests: typographic quotation marks,
and a `−` (U+2212) bullet glyph inside a split sentence. `score --recheck` re-runs the checker
on stored outputs.

**Findings.**

- **Offer splitting works on this set.**
  - FIT: 8 of 8 offers with exact pages and contacts.
  - The bilingual duplicate became one offer on [1, 2].
  - Synthetic document: no leakage, and the explicit "no programming" statement became `none`.
- **The deliverable rule fixed the weakest field at low effort.** The remaining invented
  deliverable is BayWa's "automatically generated documentation", which is what the students'
  application produces, not a student output.
- **Contacts (fixed in schema v3.1 / prompt v3.2).** The singular `contact_email` kept one of
  BayWa's three contacts at low effort. `contact_name` / `contact_email` became a `contacts`
  list of name and email items, and the next low run listed all three with no other regression
  beyond run-to-run noise. Anding's `programming_performed` has flipped between `unknown` and
  `some` across low runs, so 19 offers cannot separate 0.95 from 1.00. Outputs stored before v3.1
  no longer validate, so only runs on the same schema can be scored together.
- **The IDPX course poster** is still extracted as an offer in every run.
- **Project types.** "Interdisziplinäres Projekt" in a header became `project_study` in most
  runs. An IDP named only in prose was missed.
- **Low vs medium.** Low v3.1 now matches medium on every check except complete contacts, at
  lower cost. **Keep `low`.**
- **One list vs two.** No accuracy gain, and more stitched quotes. **Keep the two lists.**
- `work_modes` are checked on only 3 offers. They remain a ranking signal until two reviewers
  label them (§2).

**Open (steps 5–6).**

- The search representation comparison (§6) needs three inputs: an embedding deployment, a
  German and English query set with relevance judgments, and a check that each summary sentence
  is supported by cited items.
- Filters are published field by field only after reviewers agree on the labels and a threshold
  is set for each field.
- Extracted offers are not yet linked to listings and are not served by the API.

**Storage and batch runner.**

- `pdf_profile_extractions` (`PDFProfileExtraction` in `db.py`, Alembic `0004`) holds one row per
  attempt. The row stores the version columns (schema, prompt version and hash, deployment,
  reasoning effort), status, attempts, errors, token counts, coverage, citation issues and the
  `document` JSON. A failed attempt adds a row and never replaces an earlier `ok` row.
- `app.ingestion.profile_backfill` extracts every `pdf_analysis` row with stored Markdown.
  - A document is done when it has an `ok` row for the current version columns, so a run can
    resume, and changing the prompt or effort re-extracts everything.
  - It skips documents that are `no_text` (need OCR), have no pages, or exceed the single-call
    limit, and makes no model calls for them.
  - A validation failure is a stored `failed` row, which the next run retries.
  - An API or transport error is stored with the error type only, because provider messages
    may echo the request.
  - The run stops after `--max-consecutive-errors` API errors in a row (default 5).
  - At most `--workers` calls run at a time (default 2), and a PostgreSQL advisory lock stops
    runs from overlapping.
  - `--dry-run` counts pending documents without calling the model.
- Consumers should read the latest `ok` row per content hash for the chosen version.
