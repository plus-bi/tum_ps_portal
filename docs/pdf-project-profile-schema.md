# Project profile schema (draft)

This is the original v1 draft. The current schema, prompt, citation checks, and language
decision are documented in [pdf-project-profile-v2.md](pdf-project-profile-v2.md).

Converted a sample of 14 stored PDFs from `pdf-artifacts/` to per-page markdown with `pymupdf4llm` (page_chunks=True, so each page's text stays addressable by page number) — 10 `digital_native`, 3 `mixed`, 1 `scanned`, spanning business, informatics, and engineering chairs in German and English. This validates the two-step approach from [pdf-extraction-recommendations.md](pdf-extraction-recommendations.md): markdown conversion preserves headings, bullet structure, and bold emphasis well enough to make the second step (LLM structured extraction) tractable, but it is not a replacement for that document's page-image fallback — the one `scanned` sample produced 0 characters, as expected, and needs OCR before any text-based extraction can run.

## Observations from the sample

- The dimensions already listed in [student-project-discovery.md](student-project-discovery.md) (subject, application area, activities, deliverables, prerequisites, learning opportunities, practical fit) map cleanly onto what's actually in these PDFs — no new dimension was needed.
- Practical fields (team size, duration, start date, location, working language) are sometimes explicit labeled key-value pairs (`**Teamgröße:** 2 Studierende`, `Start Date: ASAP Duration: 3-6 months`), but just as often stated only in prose or not at all. Regex/pattern extraction would miss most of these; this has to be LLM-based free-text extraction, confirming the "explicit unknown" design in the MVP doc rather than a "field not found = empty string" approach.
- Prerequisites split into "required" vs. "recommended/plus" (e.g. `_is a plus_`, `Bonus:`) often within the same list — the schema needs to keep those distinct rather than flattening to one `prerequisites` list.
- Project type is not always singular: one IDP listing was labeled "Interdisciplinary Project (IDP), Semester Thesis" — allow multiple.
- Document language and working language are genuinely independent: a German-language PDF explicitly required "Strong German and English skills" as working languages.
- Multi-column layouts can reorder bullets in the markdown (seen in the `iwb` CAM-planning sample, where two scope-of-work bullets appeared after the Contact section). Evidence excerpts mitigate this — a human/reviewer can see the excerpt is legitimate scope text even if page position looks odd — but it means field order in the markdown cannot be trusted as document order.

## Proposed schema

Every content field carries its own evidence per [pdf-extraction-recommendations.md](pdf-extraction-recommendations.md) ("preserve the source page number and evidence excerpt for every extracted field") and its own "not specified" state per [student-project-discovery.md](student-project-discovery.md) ("missing information needs its own state"). A generic wrapper avoids repeating that shape per field:

```json
{
  "$defs": {
    "Evidence": {
      "type": "object",
      "properties": {
        "page": {"type": "integer", "description": "1-indexed source PDF page"},
        "excerpt": {"type": "string"}
      },
      "required": ["page", "excerpt"]
    },
    "TextField": {
      "type": "object",
      "properties": {
        "stated": {"type": "boolean"},
        "value": {"type": ["string", "null"]},
        "evidence": {"type": "array", "items": {"$ref": "#/$defs/Evidence"}}
      },
      "required": ["stated", "value", "evidence"]
    },
    "ListField": {
      "type": "object",
      "properties": {
        "stated": {"type": "boolean"},
        "values": {"type": "array", "items": {"type": "string"}},
        "evidence": {"type": "array", "items": {"$ref": "#/$defs/Evidence"}}
      },
      "required": ["stated", "values", "evidence"]
    }
  },
  "type": "object",
  "properties": {
    "schema_version": {"type": "string"},
    "extractor_version": {"type": "string"},
    "content_hash": {"type": "string", "description": "matches PDFArtifact.content_hash" },
    "page_count": {"type": "integer"},
    "document_language": {"type": "string", "description": "detected, e.g. de/en — metadata, not an extracted content field" },

    "title": {"$ref": "#/$defs/TextField"},
    "provider_name": {"$ref": "#/$defs/TextField", "description": "hosting company/lab, distinct from the TUM chair" },
    "project_types": {"$ref": "#/$defs/ListField", "description": "e.g. project_study, idp, bachelor_thesis, master_thesis, semester_thesis — multiple allowed" },
    "degree_level": {"$ref": "#/$defs/ListField", "description": "bachelor, master, any" },

    "subjects": {"$ref": "#/$defs/ListField"},
    "application_areas": {"$ref": "#/$defs/ListField"},
    "activities": {"$ref": "#/$defs/ListField"},
    "deliverables": {"$ref": "#/$defs/ListField"},
    "prerequisites_required": {"$ref": "#/$defs/ListField"},
    "prerequisites_recommended": {"$ref": "#/$defs/ListField"},
    "learning_opportunities": {"$ref": "#/$defs/ListField"},

    "team_size": {"$ref": "#/$defs/TextField", "description": "kept as stated text (e.g. \"2 Studierende\", \"15 people\") — do not force-parse to an integer at extraction time" },
    "duration": {"$ref": "#/$defs/TextField"},
    "start_date": {"$ref": "#/$defs/TextField", "description": "explicit date or stated text like \"asap\"/\"flexible\"" },
    "application_deadline": {"$ref": "#/$defs/TextField"},
    "location": {"$ref": "#/$defs/TextField", "description": "e.g. \"Munich (at least 2 days/week on-site)\", \"Remote / Hybrid\"" },
    "working_language": {"$ref": "#/$defs/ListField"},

    "contact_name": {"$ref": "#/$defs/TextField"},
    "contact_email": {"$ref": "#/$defs/TextField"},
    "application_instructions": {"$ref": "#/$defs/TextField"},
    "external_url": {"$ref": "#/$defs/TextField"}
  },
  "required": ["schema_version", "extractor_version", "content_hash", "page_count", "document_language"]
}
```

Notes on deliberate choices:

- `team_size`, `duration`, `start_date`, `location` stay as `TextField` (free text) rather than structured numbers/dates/enums. The sample shows too much variation ("3-6 months (min. 16h/week)" vs. "6 Monate Teilzeit") to force structure at extraction time without losing information; structure/normalize in a later, separately versioned pass so re-normalization doesn't require re-running the LLM extraction.
- `subjects`/`application_areas`/`activities` are free-text lists at this stage, not yet mapped to the "consistent topic taxonomy" the discovery doc calls for — taxonomy mapping should be a separate versioned step downstream of this schema, per the MVP doc's "version taxonomy mappings ... independently."
- No per-project "not specified" object is needed at the top level; `stated: false` on the relevant field already covers it, matching "show 'not specified' when information is absent."

## Suggested next step

Validate this schema by running it (via LLM structured extraction) against the same 14-sample set plus the German-heavy and scanned/mixed cases, and manually check the `evidence.page`/`excerpt` values against the source PDFs before treating any field as filter-ready, per the MVP doc's "validate extraction on a representative sample" step. I did not run LLM extraction in this pass — only the markdown conversion and schema drafting from what's actually printed in the sample.
