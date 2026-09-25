# Student project discovery MVP

The MVP should help students describe what interests them, narrow the catalog with reliable filters, and see evidence for why a project matches. Release fields and filters according to how accurately the source material supports them.

## MVP features

| Feature | MVP scope |
|---|---|
| Search by interest | Search in German or English using keyword and semantic matching. Combine search with filters students can inspect and change. |
| Reliable filters | Start with course type, subject, and activities or methods. Add fields such as working language and team size when extraction quality is sufficient. |
| Structured project profiles | Extract objectives, proposed work, deliverables, stated prerequisites, and practical details from Project Study and IDP sources, including HTML-only offers. |
| Evidence-backed results | Explain matches using short source excerpts and links to the original PDF page or chair page. Avoid unexplained similarity scores. |
| Explicit unknowns | Show “not specified” when information is absent or uncertain. Let students choose whether unknown values remain in filtered results. |
| More like this | Find related projects using the same profiles and embeddings as semantic search. No account is required. |
| German and English support | Localize tags and summaries. Keep document language separate from working language and language requirements. |

## Foundations required for the MVP

- **Validate extraction on a representative sample.** Include Project Studies and IDPs, PDF and HTML listings, German and English sources, and scanned PDFs. Define fields and measure accuracy and reviewer agreement before exposing each field as a filter.
- **Keep enrichment versioned and separate from crawler data.** Track the listing text, each linked PDF, applicable chair guidance, and extractor version used to produce each profile. Version taxonomy mappings and embeddings independently.
- **Detect source changes.** Recheck stored PDF URLs through `PoliteFetcher`; refresh dependent profiles when content changes. Preserve the last successful profile if re-extraction fails, and make its freshness visible.
- **Preserve corrections.** Keep reviewer overrides when profiles are regenerated. Enrichment must not change listing lifecycle state.
- **Use scoped chair guidance.** Inherit a chair-level condition only when its source establishes that scope. Retain its URL, content hash, and evidence.
- **Protect source and query data.** Link to original public documents rather than mirroring stored PDFs. Treat source text as untrusted input. Avoid logging raw queries alongside user identities.
- **Measure search quality.** Evaluate realistic student queries in both languages. Measure extraction accuracy, reviewer agreement, recall@20 for retrieval, nDCG@10 for final ranking, and violations of explicit exclusion constraints.

## Suggested delivery order

1. Extract a representative sample, define fields, and measure extraction quality.
2. Build versioned profiles and evidence across the catalog, including source-change detection and preserved overrides.
3. Release the small set of filters that passed the accuracy checks, with visible unknown values.
4. Add multilingual keyword and profile-embedding search, then add “more like this.”
5. Compare optional LLM reranking against the measured baseline. Keep it only if relevance gains justify its cost and latency; provide a keyword and embedding fallback.

## Keep for later

| Feature | Why it can wait |
|---|---|
| Compare selected projects in a session | Useful after profiles are consistent, but not required for initial search. |
| More practical filters and planning views | Semester, deadlines, credits, application mode, and programming involvement depend on accurate, well-supported extraction. |
| Persistent shortlists and saved searches | Require durable account storage and additional user flows. |
| Email digests | Require persistent searches, a matcher that runs after ingestion, and real email delivery. |
| LLM reranking | Evaluate after establishing retrieval recall and a baseline for cost and latency. |
| Passage-level retrieval | Add only if evaluation shows that profile-level search misses relevant details. |
| Preference quiz and conversational refinement | Add if students struggle to express their needs through search and filters. |
| Chair profiles and archive search | Broader exploration that can follow support for current offers. |
| CV, career, and advanced team matching | Require more inference, source coverage, and privacy safeguards. |

For strict exclusions, absence of a statement must remain unknown. For example, “purely qualitative study” alone does not establish that no programming is involved. Publish a “no programming” filter only when the source evidence and field definitions support that conclusion.
