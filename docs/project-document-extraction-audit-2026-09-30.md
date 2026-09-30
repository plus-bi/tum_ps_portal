# Project document and profile extraction audit

**Snapshot:** 30 September 2026, after the pending LLM backfill completed. Scope is the active catalog.

Counts below represent distinct LLM input documents keyed by content hash. A source can be linked to several listings, and one URL can produce separate scoped Markdown documents for separate offers.

| Source type | Documents | Converted to usable Markdown | Successful LLM extraction |
|---|---:|---:|---:|
| PDF | 330 | 326 | 327 |
| HTML detail pages | 43 | 43 | 43 |
| HTML chair or listing text | 24 | 24 | 24 |
| PNG | 4 | 4 | 4 |
| DOCX | 2 | 2 | 2 |
| **Total** | **403** | **399** | **400** |

The extraction run processed all **67 pending documents** successfully: 43 HTML detail documents, 18 HTML chair or listing text documents, 4 PNGs, and 2 DOCX files. There are no pending documents for the current extraction version. Six HTML text documents had already been processed before this run.

The active catalog has 492 project listings. Of those, 488 have at least one linked source and 475 currently show a profile. Four listings have no usable source material. There are four distinct PDF sources whose Markdown text is empty or insufficient and which require OCR. One of those has an older successful LLM result, but its `requires_ocr` and `unverified_citations` review flags keep it hidden. This accounts for 400 successful LLM records versus 399 sources with usable Markdown.

## PDF sources requiring OCR

Serial numbers are the portal reference codes. A source used by multiple listings includes every associated serial.

| Portal serial number(s) linked to this PDF | PDF source |
|---|---|
| `idp-196`, `ps-137`, `ps-076` | [IDP_Commerical_AI_Workflows.pdf](https://www.ie.mgt.tum.de/fileadmin/w00cem/tim/IDP_Commerical_AI_Workflows.pdf) |
| `ps-112`, `ps-173` | [demi_2025-14-11_project_study_PHM_1.pdf](https://www.fa.mgt.tum.de/fileadmin/w00chf/controlling/demi_2025-14-11_project_study_PHM_1.pdf) |
| `ps-116`, `ps-177` | [240327_adon_projectstudy_compressed.pdf](https://www.fa.mgt.tum.de/fileadmin/w00chf/controlling/Lehre/Projektstudien/240327_adon_projectstudy_compressed.pdf) |
| `idp-078` | [SAMA_BET_Optimizer_RL_IDP.pdf](https://www.cit.tum.de/fileadmin/w00byx/cit/Studium/Studiengaenge/Master_Informatik/Interdisziplinaeres_Projekt/SAMA_BET_Optimizer_RL_IDP.pdf) |

The one already-processed OCR source is the file associated with `idp-078`. Its LLM output is stored for audit, but it is not displayed as a profile until OCR makes its citations verifiable.
