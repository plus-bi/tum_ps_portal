# Student project discovery

The portal can help students find projects around three needs: topics they care about, the kind of work they want to do, and whether a project fits their skills and practical constraints. Semantic search can connect a student's description to the PDF contents; structured filters can make results easier to narrow and compare.

The current [catalog search](../frontend/app/[locale]/CatalogClient.tsx) matches text in titles, summaries, and chair metadata. The repository also stores project PDFs and has a [PDF extraction recommendation](pdf-extraction-recommendations.md) that calls for structured fields with page-level evidence.

## Discovery experiences

| Approach | Example student interaction | What it should match |
|---|---|---|
| Describe an ideal project | “I want to use data to reduce food waste.” | Relevant concepts even when a PDF uses terms such as demand forecasting, inventory optimization, or perishable supply chains. |
| Explore interests through filters | Select sustainability → mobility → electric vehicles. | A consistent topic taxonomy across chairs, with multiple topics per project. This helps students who do not know what to search for. |
| Choose the actual work | “I want to build a prototype” or “I prefer interviews and market research.” | Proposed activities and deliverables: coding, experiments, interviews, modeling, literature reviews, and strategy development. |
| Match skills and learning goals | “I know Python and want to learn optimization.” | Existing prerequisites separately from skills the student would develop during the project. |
| Find similar projects | Open a promising project and select “More like this.” | Similarity by topic, method, or industry. Let students choose which aspect they liked. |
| Match a team | “We are three students: two with business backgrounds and one programmer.” | Team size, disciplinary requirements, and complementary responsibilities where the source states them. |
| Refine conversationally | “More practical,” “less programming,” or “only projects with industry partners.” | Adjust the current results and show the resulting preferences as editable filters. |
| Discover through career interests | “I want experience relevant to product management.” | Activities such as customer discovery, prioritization, prototyping, and product evaluation. Mark career relevance as a suggestion when the PDF does not state it explicitly. |

Filtering by the work students will actually do may be especially valuable. Two projects about AI could involve very different experiences: implementing a model, interviewing managers about adoption, or developing a business strategy. Topic matching alone would make them look similar.

## Information to extract from each project

| Dimension | Example values |
|---|---|
| Subject | Generative AI, sustainability, entrepreneurship, healthcare |
| Application area | Manufacturing, finance, mobility, food, public services |
| Activities and methods | Interviews, surveys, programming, optimization, experiments |
| Deliverables | Prototype, dashboard, business plan, research report |
| Prerequisites | Python required, statistics recommended, German required |
| Learning opportunities | Practice user research, develop forecasting models |
| Practical fit | Project Study/IDP, team size, working language, location, dates, duration |

Keep the vocabulary manageable and allow multiple labels. A project could be about sustainability, applied to logistics, use optimization, and produce a software prototype. That combination is more useful than one broad category.

## Requirements and missing information

Distinguish requirements from preferences. For example, in “An IDP about sustainability where I can use Python, conducted in English,” IDP and working language may be requirements, while sustainability and Python may guide ranking. Show the interpretation as editable chips so students can correct it. Keep document language separate from working language.

Missing information needs its own state. If a PDF says nothing about German requirements, show “Language requirements not specified.” A search for “no programming” cannot be handled reliably by semantic similarity alone; it needs evidence about the actual tasks and requirements. Let students choose whether to include projects with unknown information.

## Explain each match

Every result should explain why it matched. For example:

> **Why this matches:** Applies forecasting to food waste reduction.  
> **Relevant work:** Data analysis and predictive modeling.  
> **Requirements:** Python recommended; working language unspecified.  
> **Evidence:** Project objectives, PDF page 2.

Link evidence back to the original PDF. Brief, supported explanations help students judge relevance more than an unexplained “92% match.”

## Search design

Use two complementary capabilities:

- **Structured extraction** reads each PDF and produces the dimensions above, with supporting passages and page numbers. It powers filters, comparisons, and requirement checks.
- **Semantic retrieval** searches passages by meaning. Combine it with keyword search so exact tools, company names, and project reference codes remain easy to find.

Index project objectives, tasks, and prerequisites separately from general company descriptions and chair boilerplate. This reduces matches driven by incidental mentions, such as a company mentioning AI even when the project is unrelated. Preserve the relationship between each passage and its project, especially when a PDF contains multiple offers.

The existing PostgreSQL setup could support an initial implementation using full-text search and an extension such as `pgvector`. Extract and index documents when their contents change, then reuse that index for searches. The current PDF classification records text availability; it does not provide a semantic search index. Include relevant chair-page content for projects whose details are outside PDFs.

## Suggested rollout

For the first release, prioritize natural-language search, filters for topic/activity/prerequisites, and evidence-backed match explanations. Then add “more like this,” shortlist comparisons, and saved searches that notify students about newly matching projects. A guided conversation can follow once the underlying matching works well.

Before choosing a model, collect 30–50 realistic student searches and manually identify good matches in the PDFs. Include German and English searches, vague interests, exact technical terms, and exclusions. This gives you a way to judge whether the system helps students find suitable projects and which discovery features deserve further investment.
