# Review: student project discovery

Comments on [student-project-discovery.md](student-project-discovery.md), checked against the current codebase (September 2026).

## Summary

The document identifies the right student needs. Its most useful ideas are:

- filtering by **the work a student will actually do**, not just the topic
- treating **missing information as its own state**
- **evidence-backed explanations** instead of match scores
- building an **evaluation set before choosing a model**

Keep all four.

Its main weaknesses:

1. It is not tied to what the repository already has, or lacks.
2. It does not say how enrichment stays current when the source documents change.
3. It leaves out the practical constraints that often decide whether a student can take a project, and does not warn how easily those constraints are misread.
4. It has no concrete schema, taxonomy process, or success metrics.

The first release should stay focused. Across the whole design, be strict about evidence, missing information, and updates to source documents.

## 1. Ground the proposal in the current system

| Assumption the document makes | Current state in the repo |
|---|---|
| Projects have topics that can be refined | `Topic` in `backend/app/schemas.py` is a coarse enum with 9 values. Live and fixture ingestion write `topics: []` (`live.py:180`, `service.py:70`), so the topic filter has nothing to match. |
| An extraction step exists to build on | `enrichment.enrich()` exists but nothing calls it. Its prompt also rejects anything not labeled "Project Study/Projektstudium", so **it would drop IDPs**. |
| PDF text is available | `pdf_analysis.py` records only whether a text layer exists (`text-layer-v1`) and intentionally discards the text. No page-level text store exists yet. |
| Saved searches can notify students | `account_api.py` keeps bookmarks and saved searches in in-process dicts, which are lost on restart. `tasks.deliver_alerts()` is a placeholder that returns `{"status": "scheduled"}`. Resend exists only as configuration and a webhook endpoint; nothing sends email. |
| Human correction is possible | `ExtractionReview` and `ManualOverride` exist. Crawls currently re-apply only the `title` and `summary` overrides (`live.py:199–200`). |

**Suggested change:** Add a "Current state and gaps" section. Make extracting from a representative sample, IDPs included, the first step.

## 2. Keep enrichment current without losing it

Neither document covers this, but it decides whether enriched data can be trusted over time. "Reprocess when `Listing.content_hash` changes" is not enough, for three reasons:

- **The listing hash ignores linked PDFs.** It is computed from the discovered candidate text only (`live.py:173`). A linked PDF can change while that text stays identical, so the listing hash never changes.
- **Stored PDFs are never re-fetched.** `store_pdf_url()` skips any URL whose file is already stored (`pdf_backfill.py:95`). If a chair replaces a PDF at the same URL, the portal keeps the old file.
- **Every crawl overwrites the listing's data.** `listing.normalized = normalized` runs on every crawl (`live.py:201`), not only when the text changed, and resets fields such as `topics` to empty. Anything stored there would be wiped nightly.

**Recommendation:**

- **Store enrichment in its own table,** separate from `Listing.normalized`, so crawls cannot overwrite it.
- **Record the version of every input** each profile was built from:
  - the hash of the listing text
  - the content hash of each PDF it used
  - the hash of any chair guidance it inherited (see §7)
  - the extractor and prompt version
  
  A profile is out of date when any of these differ from the current values. Checking only the listing hash would miss PDF and guidance changes.
- **Version taxonomy mappings and embeddings separately.** A taxonomy change should re-map stored extraction output without re-running extraction. An embedding model change should re-embed without re-extracting.
- **Detect PDF changes.** Re-check stored PDF URLs periodically with conditional requests through `PoliteFetcher`. When the content hash changes, store the new file and mark the dependent profiles out of date. Keep the old artifact, because existing evidence links point to its pages.
- **Keep the last good profile when extraction fails.** Store the failure next to it with a timestamp. Enrichment never changes listing lifecycle: archiving stays with the crawler, as AGENTS.md requires. An out-of-date profile can still be served, flagged as such, until re-extraction succeeds.
- **Apply manual overrides to profile fields as well,** not only to `title` and `summary`. Otherwise a reviewer's correction is lost the next time the profile is regenerated.

Tests should cover these cases:

- A changed PDF with unchanged listing text marks the profile out of date.
- A failed extraction keeps the previous profile.
- A re-crawl does not erase enrichment.
- An enrichment failure never changes `status` or `consecutive_misses`.

## 3. Size the architecture by measurement, not corpus size

There are about **230 unique PDFs across 32 chairs**. That makes some things cheap:

- **Structured filters can stay client-side.** `CatalogClient.tsx` already filters the full list in the browser.
- **Profile-level embeddings are a reasonable first step.** Embed one compact profile per listing (objectives, tasks, methods, prerequisites) instead of chunking passages. Add passage-level retrieval only if evaluation shows profile-level matching misses relevant content.
- **Most work can be precomputed.** Profiles, embeddings, facets, and nearest neighbours only change when their inputs change (§2).

A small catalog does **not** by itself make query-time LLM calls cheap or fast. Their cost and latency depend on search volume, profile length, and the model used.

**LLM reranking should earn its place through evaluation.** It cannot recover a suitable project that the first retrieval step missed, so retrieval recall has to be measured first. Suggested order:

1. Build a baseline: keyword search plus profile embeddings, measured on the evaluation set (§9).
2. Add reranking as an experiment and compare it against the baseline on the same queries.
3. Keep reranking only if the gain justifies the cost and latency at realistic traffic. It also needs a query budget and a fallback that works without it.

`pgvector` is a reasonable storage choice because PostgreSQL is already deployed, but it isn't required at first.

## 4. Add practical constraints, and keep interpretations separate

Students often rule out projects they cannot take before looking at topics. These constraints are also the easiest to misrepresent, so each must record its **source, the date it was observed, and a "not specified" state**.

Three statuses must stay separate:

| Field | What it means | What it does *not* mean |
|---|---|---|
| **Course type** | The listing is labeled as an IDP or a Project Study | That every student, programme, or examination regulation can count it |
| **Crawl status** | The crawler still finds the listing on the source page (the current `active` status) | That applications are open |
| **Application status** | The source states open, closed, rolling, or a deadline, with the date it was seen | Anything, when the source says nothing: it stays unknown |

Show eligibility as "Offered as: IDP (per chair page, seen 2026-09-20)" together with a link to the relevant module or programme rules. Don't show "You are eligible." An expired deadline should hide or flag a listing even while it remains in the crawl.

Other constraints worth extracting, each with evidence:

- **IDP split.** For IDPs, record the informatics component (what gets built) separately from the application domain (the field outside informatics), as far as the source states them.
- **Start semester and duration.** Normalize values such as "WiSe 2026/27" into a semester facet, and keep the original wording.
- **Credits and workload.** ECTS, where stated.
- **Partner type.** Industry, research, startup, or public sector.
- **Contact and self-proposed topics.** Many chair pages say whether they accept self-proposed topics.
- **Team formation and size.** `team_size_min/max` already exist in the schema.

## 5. Make the extraction schema concrete

- **Store one profile per combination of input versions** (§2), in its own table. Keep the versioning rule from `pdf-extraction-recommendations.md`.
- **Give every field evidence**: excerpt, page, source (`pdf` or `chair_page`), and the source's content hash. The existing `Confidence(value, evidence)` pattern is a starting point.
- **Separate stated facts from inferred suggestions** in the schema, not only in the UI. Career relevance and "skills you'll learn" are usually inferred.
- **Allow multiple offers per PDF.** The aggregate-listing split (`d7180c4`) shows they occur, so keep profiles per listing, not per PDF.

### Exclusion queries need separate, defined fields

A rating scale such as "programming intensity" does not solve "no programming" on its own. It needs written definitions and evidence, and it must not turn silence into "none". Two fields are needed, because these are different questions:

| Field | Question it answers | Example evidence |
|---|---|---|
| `programming_prerequisite` | Must the student already know how to program? | "No prior programming experience required" → `not_required` |
| `programming_involvement` | Does the project work itself involve programming? | "Students will implement a simulation in Python" → `substantial` |

Rules:

- **No mention means `unknown`,** never `none`. Assign `none` only when the source says so, for example "purely qualitative study".
- **Define each level in writing,** with an example, before extraction. Two reviewers labeling the same listing should reach the same value. Measure how often they agree on the sample.
- **Let students choose how to treat unknowns.** A "no programming" filter shows `none` by default, and students can opt to include `unknown`.

The same pattern applies to quantitative methods, German-language requirements, and fieldwork.

## 6. Build the taxonomy from the data

1. Extract free-text labels for subject, application area, and methods from the sample.
2. Cluster and curate a small set of tags. Map them to the existing 9 `Topic` values as parents, so current filters keep working.
3. Version the taxonomy (§2), and provide German and English labels for the localized UI.

## 7. Scope chair-level guidance explicitly

Chair pages often contain conditions that apply to more than one listing: application procedure, required documents, language. Using them is necessary, because some listings have no PDF, but inheritance must be explicit:

- **Store chair guidance as its own sourced items,** each with an explicit scope, such as "all Project Studies at this chair", "summer semester 2026", or "listed course X". Keep the source URL and content hash.
- **Inherit a condition only when the source supports its scope.** A general application procedure may apply chair-wide. A language requirement stated next to one course applies only there.
- **Keep the link to the source.** An inherited field should read, for example, "Application documents: CV and transcript (chair page, applies to all Project Studies)", so students can see where it came from.
- **Let listings override guidance.** When a listing's own text contradicts chair guidance, the listing wins, and the conflict is shown to reviewers.
- **Track guidance hashes as a profile input** (§2), so a change to the chair page marks the dependent profiles out of date.

## 8. Handle multilinguality explicitly

Many PDFs and queries will be in German. Normalizing profiles into English helps consistency but does not solve search by itself: **a German query must also reach the same representation.** Options:

- Use a multilingual embedding model for both profiles and queries.
- Or translate the query into the profile language before embedding and keyword search.

Include German, English, and mixed queries in the evaluation set so the chosen option is measured. Also:

- Generate profile summaries in both languages when extracting, not at query time.
- Keep document language, working language, and required German level as separate fields, each with evidence.

## 9. Evaluation plan

The 30–50 query set is the best part of the original rollout section. Extend it:

- **Source real queries** from students, for example through the student council or a short survey.
- **Assess extraction on the sample before scaling it up.** Hand-label per-field values, and measure accuracy and agreement between reviewers, especially "unknown" versus a wrong value. Only fields that reach an agreed accuracy become public filters.
- **Measure retrieval before ranking.** Report recall@20 for the first retrieval step, since reranking can't recover a project that step missed. Then report nDCG@10 for the final ranking.
- **For exclusion queries,** count the results that violate the constraint. The target is zero.
- **Run the checks offline, on every change.** Re-run the set whenever the extractor, taxonomy, embedding model, or prompt changes. Store it next to `backend/tests/fixtures/` and run it against stored profiles, with no live requests.
- **Track online signals once live,** such as clicks through to the source or application link, and shortlisting by result position.

## 10. Additional discovery modes

| Idea | Value | Prerequisites |
|---|---|---|
| **"More like this"** | Useful discovery with no accounts or email infrastructure | Profile embeddings; can ship right after semantic search |
| **Compare selected projects** | Side-by-side view of practical constraints | Profiles only. It can work within a session. Persistent bookmarks are needed only to keep a shortlist across visits or devices. |
| **Deadline and semester views** | High value for planning | Application status and semester extraction at agreed accuracy (§4, §9) |
| **Chair profiles** ("chairs that regularly offer X") | Helps when nothing matching is open | Aggregating past and archived listings |
| **Archive search** | Sets expectations for coming semesters | Profiles kept for archived listings |
| **Short preference quiz** → pre-set filters | Structured alternative to conversational refinement | Reliable filters |
| **Paste your skills or CV** → suggested filters | Personalization | Opt-in, temporary processing, nothing stored |
| **Email digest of new matches** | Retention | Persistent saved searches, a matcher that runs after ingestion, and real email delivery. `deliver_alerts()` is currently a placeholder, so this is a substantial piece of work. |

## 11. Safety and privacy

- **Prompt injection.** PDF and chair-page text is untrusted. At query time, pass profiles to any model as data only, and never let source text change the model's instructions.
- **No public mirroring.** Link evidence to the chair's original URL with a page reference, not to a stored copy, and keep excerpts short (AGENTS.md).
- **Explanations built from evidence.** Assemble "Why this matches" from extracted fields and evidence. A model may phrase the text, but must not state requirements that are not in the profile.
- **Query privacy.** Free-text queries may contain personal details. Don't log raw queries next to user IDs, and say so in the privacy notice if queries go to an external provider.

## 12. Revised rollout

Filters are released according to how accurately and consistently the documents support them. They do not all ship at once.

1. **Extract and manually assess a representative sample.** Include Project Studies and IDPs, PDF-based and HTML-only listings, German and English, and scanned documents. Write the field definitions (§5) and measure accuracy and reviewer agreement per field.
2. **Build profiles and evidence across the catalog.** Use the separate, versioned enrichment table from §2, re-check PDFs for changes, keep the last good profile on failure, and preserve reviewer overrides.
3. **Release a small set of reliable filters.** Start with the fields that passed step 1, such as course type, subject tags, and team size. Each has a visible "not specified" state and evidence. Add more filters as their measured accuracy allows.
4. **Add semantic search.** Use keyword search plus profile embeddings, with multilingual handling (§8), as a measured baseline. Add **"more like this"** here, since it reuses the same embeddings. Session-only comparison can also ship at this point.
5. **Evaluate optional reranking** against the baseline, and keep it only if it measurably helps at acceptable cost and latency.

Later, depending on demand: persistent shortlists and saved searches, email digests (which need delivery implemented), chair profiles, archive search, and the preference quiz. Consider conversational refinement only if the chips-based flow proves insufficient.

## Smaller edits to the original document

- **"Match a team"** assumes sources describe team composition, and few do. Scope it to team size and whether students apply individually or as a team.
- **"Discover through career interests"** is entirely inferred. Label it experimental, or merge it into learning opportunities.
- **"Reprocess documents when their contents change"** should list every input: listing text, each linked PDF, applicable chair guidance, extractor version, taxonomy version, and embedding version (§2).
- **Chair-page content** should be handled as scoped guidance (§7), not folded into every listing.
- **Add a note on cost and latency:** extraction runs when inputs change, and any query-time model call needs a budget and a fallback that works without it.
