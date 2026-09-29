# Catalog profile filters

The Project Study / IDP filter uses the existing listing type. The new profile filters use only structured values from a linked, current-schema PDF extraction. They never use embedding matches. An ambiguous multi-offer document gives the listing unknown values rather than assigning another offer's fields to it.

The profile fields are `degree_level`, `work_modes`, `programming_performed`, `programming_required`, `work_location_mode`, and `working_language`. Within a field, selected values are alternatives; selected fields combine with AND. Unknown or not-stated values are included only when the student selects the separate option. “No programming” selects exactly `programming_performed=none`.

Working-language filter values are `en`, `de`, and `other`, derived from the source-backed free-text field. “English” and “German” mean the working language includes that language. They do not promise that knowledge of that language alone is sufficient. The original wording and evidence remain on the project profile.

All six controls are visible in the catalog. The former `PUBLISHED_PROFILE_FILTERS` / `PROFILE_FILTER_PREVIEW` publication gate has been removed. Values come only from a linked, current-schema PDF profile with an unambiguous offer match. Listings without one display unknown or not-stated values.

The field-label evaluation remains incomplete: `backend/tests/fixtures/profile_eval/labels.json` is still a draft, and only three offers have work-mode labels. Treat coverage and accuracy as unmeasured until reviewers approve the label set and record a threshold for each field. Visibility does not imply that a field has passed that review.

For local evaluation, run `docker compose up --build -d caddy` from the repository root, then open `http://localhost:8080/en`. This starts the local proxy, web, API, and database without starting the crawl worker. The filters use existing local PDF extractions. If there are no usable extractions in the local database, they show unknown or not-stated counts. Stop the local stack with `docker compose stop caddy web api postgres` when done.

For the field-label review, check representative Project Studies and IDPs, both languages, unstated values, multi-offer PDFs, and extraction records with citation issues. In particular, the `programming_performed=none` label needs explicit supporting source text; silence stays unknown.
