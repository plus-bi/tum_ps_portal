from sqlalchemy import create_engine, select

import app.db as db
from app.db import Base, PDFAnalysis, PDFArtifact
from app.ingestion import pdf_analysis


def test_read_failure_keeps_pages_extracted_earlier(tmp_path, monkeypatch):
    test_engine = create_engine(f"sqlite:///{tmp_path / 'analysis.db'}")
    monkeypatch.setattr(db, "_engine", test_engine)
    Base.metadata.create_all(test_engine)
    monkeypatch.setattr(pdf_analysis.settings(), "artifact_storage_path", tmp_path)
    (tmp_path / "a.pdf").write_bytes(b"%PDF")
    with db.session_factory()() as session:
        session.add(PDFArtifact(url="https://example.org/a.pdf", content_hash="a" * 64, storage_key="a.pdf"))
        session.add(PDFAnalysis(content_hash="a" * 64, classification="digital_native",
                                classifier_version="old", extracted_markdown_pages=["Earlier page"]))
        session.commit()

    def missing_dependency(data):
        raise ModuleNotFoundError("pymupdf4llm")
    monkeypatch.setattr(pdf_analysis, "read_pdf", missing_dependency)

    assert pdf_analysis.classify_stored_pdfs()["unknown"] == 1
    with db.session_factory()() as session:
        analysis = session.scalar(select(PDFAnalysis))
    assert (analysis.classification, analysis.extracted_markdown_pages) == ("digital_native", ["Earlier page"])
