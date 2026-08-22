from pathlib import Path

from app.ingestion.chunker import chunk_document
from app.ingestion.parser import parse_markdown_document

CORPUS_ROOT = Path(__file__).resolve().parent.parent / "corpus"


def _corpus_files():
    return sorted(p for p in CORPUS_ROOT.rglob("*.md") if p.name != "MANIFEST.md")


def test_every_frozen_corpus_document_parses_and_chunks_without_error():
    files = _corpus_files()
    assert len(files) == 29, f"expected 29 corpus documents, found {len(files)}"

    for path in files:
        slug = str(path.relative_to(CORPUS_ROOT).with_suffix("")).replace("\\", "/")
        doc = parse_markdown_document(path)
        assert doc.title, f"{slug}: missing title"
        assert doc.sections, f"{slug}: zero sections found"

        chunks = chunk_document(doc, slug)
        assert chunks, f"{slug}: produced zero chunks"
