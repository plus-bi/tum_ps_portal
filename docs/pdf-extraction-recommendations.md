# PDF extraction and enrichment approach

Use a hybrid, layout-aware pipeline rather than treating plain text as the only representation.

1. Retain the original PDF as the source of truth.
2. Extract native text with page numbers and bounding boxes when available.
3. Render pages to images so tables, diagrams, columns, and visual hierarchy are preserved.
4. Apply OCR with layout detection to scanned pages.
5. For LLM enrichment, provide both the page image and extracted text for the relevant page, and require page-level evidence in the output.

For project opportunities, extract structured fields such as title, company, topics, requirements, location, dates, contacts, and application links. Preserve the source page number and evidence excerpt for every extracted field.

Recommended components:

- Native PDFs: PyMuPDF or pdfplumber for text, links, and coordinates.
- Scanned PDFs: OCRmyPDF or Tesseract, followed by page rendering.
- Complex layouts and tables: Docling or Unstructured, with page-image fallback.
- LLM enrichment: multimodal, page-by-page structured extraction with schema validation and evidence citations.

The stored original file, its checksum, and fetch metadata remain the durable record; derived text and LLM outputs should be versioned separately.
