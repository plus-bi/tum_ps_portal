# TUM organization data

These files are a flat, source-traceable representation of the TUM academic
hierarchy described in the repository issue.

The TUM organization hierarchy is still provisional and must be verified
against current official School, Department, Institute/Clinic, and academic
unit pages before it is treated as complete or used for production decisions.

- `tum_school_departments.csv` is the canonical seven-School / 29-Department
  reference. It has one row per Department.
- `tum_academic_units.csv` is the recommended one-row-per-academic-unit
  export. `subunit` is intentionally empty when a unit is directly under its
  Department. Repeated academic-unit names are valid when the source lists
  different professors (for example, Operations Management).

Empty values mean that the supplied source material did not provide the field;
they are not inferred values. `source_url` points to the page used for the
row, while `unit_url` and `profile_url` are reserved for the unit's and
professor's dedicated pages once those pages have been audited.

## Crawl policy

Do not bulk-refresh these sources in parallel. Live requests must go through
`PoliteFetcher`, which applies cached robots rules and a per-origin delay. The
default delay is three seconds between requests to the same origin; use a
longer value for a source whose robots policy requests it. Prefer incremental,
source-by-source refreshes and retain conditional request headers.
