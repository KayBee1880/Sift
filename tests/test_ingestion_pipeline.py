import pytest
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError

from app.db.models import Document
from app.db.session import SessionLocal
from app.ingestion import pipeline as pipeline_module
from app.ingestion.chunker import chunk_document
from app.ingestion.metadata import DOCUMENT_SERVICE
from app.ingestion.pipeline import ingest_document

NEW_DOC_CONTENT = """# Payments Service

## Overview

Test fixture content for integration testing, new document scenario.

## Details

A second section with more content for the fixture.
"""

IDEMPOTENCY_DOC_CONTENT = """# Checkout Service

## Overview

Test fixture content for the idempotency test.
"""

ORIGINAL_CONTENT = """# Authentication Service

## Overview

Original fixture content, version one.

## Details

Original second section.
"""

CHANGED_CONTENT = """# Authentication Service

## Overview

Changed fixture content, version two, with different wording entirely.

## New Section

A section that did not exist in version one at all.

## Another New Section

A third section, also new.
"""

ROLLBACK_DOC_CONTENT_V1 = """# Notifications Service

## Overview

Rollback test fixture, version one.
"""

ROLLBACK_DOC_CONTENT_V2 = """# Notifications Service

## Overview

Rollback test fixture, version two, changed content.
"""


@pytest.fixture
def db_session():
    session = SessionLocal()
    yield session
    session.rollback()
    session.close()


def _delete_document(session, source_path: str) -> None:
    session.execute(delete(Document).where(Document.source_path == source_path))
    session.commit()


@pytest.fixture
def cleanup_document(db_session):
    paths: list[str] = []
    yield paths
    for source_path in paths:
        _delete_document(db_session, source_path)


def _write_fixture(tmp_path, relative_path: str, content: str):
    full_path = tmp_path / relative_path
    full_path.parent.mkdir(parents=True, exist_ok=True)
    full_path.write_text(content, encoding="utf-8")
    return full_path


def test_new_document_is_created_with_expected_chunks_and_vectors(
    tmp_path, db_session, cleanup_document
):
    source_path = "service_docs/payments.md"
    cleanup_document.append(source_path)
    _delete_document(db_session, source_path)  # defensive: clean slate before the test

    doc_path = _write_fixture(tmp_path, source_path, NEW_DOC_CONTENT)
    result = ingest_document(doc_path, tmp_path, db_session)

    assert result.status == "created"
    assert result.source_path == source_path
    assert result.chunk_count == 2  # Overview, Details

    stored = db_session.execute(
        select(Document).where(Document.source_path == source_path)
    ).scalar_one()
    assert stored.title == "Payments Service"
    assert stored.category == "service_docs"
    assert stored.service == "payments"
    assert len(stored.chunks) == 2
    for chunk in stored.chunks:
        assert len(chunk.embedding) == 384


def test_cross_cutting_document_stores_null_service(tmp_path, db_session, cleanup_document):
    source_path = "architecture/system-overview.md"
    cleanup_document.append(source_path)
    _delete_document(db_session, source_path)

    content = "# System Architecture Overview\n\n## Purpose\n\nCross-cutting fixture content.\n"
    doc_path = _write_fixture(tmp_path, source_path, content)
    result = ingest_document(doc_path, tmp_path, db_session)

    assert result.status == "created"
    stored = db_session.execute(
        select(Document).where(Document.source_path == source_path)
    ).scalar_one()
    assert stored.service is None


def test_unchanged_document_is_skipped_on_second_ingestion(
    tmp_path, db_session, cleanup_document
):
    source_path = "service_docs/checkout.md"
    cleanup_document.append(source_path)
    _delete_document(db_session, source_path)

    doc_path = _write_fixture(tmp_path, source_path, IDEMPOTENCY_DOC_CONTENT)

    first = ingest_document(doc_path, tmp_path, db_session)
    assert first.status == "created"

    second = ingest_document(doc_path, tmp_path, db_session)
    assert second.status == "skipped"
    assert second.chunk_count == first.chunk_count

    documents = (
        db_session.execute(select(Document).where(Document.source_path == source_path))
        .scalars()
        .all()
    )
    assert len(documents) == 1
    assert len(documents[0].chunks) == first.chunk_count  # no duplicate chunk rows


def test_changed_document_replaces_chunks_with_only_new_content(
    tmp_path, db_session, cleanup_document
):
    source_path = "service_docs/authentication.md"
    cleanup_document.append(source_path)
    _delete_document(db_session, source_path)

    doc_path = _write_fixture(tmp_path, source_path, ORIGINAL_CONTENT)
    first = ingest_document(doc_path, tmp_path, db_session)
    assert first.status == "created"
    assert first.chunk_count == 2

    doc_path.write_text(CHANGED_CONTENT, encoding="utf-8")
    second = ingest_document(doc_path, tmp_path, db_session)

    assert second.status == "updated"
    assert second.chunk_count == 3  # Overview, New Section, Another New Section

    stored = db_session.execute(
        select(Document).where(Document.source_path == source_path)
    ).scalar_one()
    anchors = sorted(c.section_anchor for c in stored.chunks)
    assert anchors == ["Another New Section", "New Section", "Overview"]
    for chunk in stored.chunks:
        assert "Original fixture content" not in chunk.text
        assert "Original second section" not in chunk.text


def test_failed_replacement_rolls_back_cleanly(tmp_path, db_session, cleanup_document, monkeypatch):
    source_path = "service_docs/notifications.md"
    cleanup_document.append(source_path)
    _delete_document(db_session, source_path)

    doc_path = _write_fixture(tmp_path, source_path, ROLLBACK_DOC_CONTENT_V1)
    first = ingest_document(doc_path, tmp_path, db_session)
    assert first.status == "created"

    original = db_session.execute(
        select(Document).where(Document.source_path == source_path)
    ).scalar_one()
    original_hash = original.source_content_hash
    original_chunk_texts = sorted(c.text for c in original.chunks)
    original_chunk_count = len(original.chunks)

    doc_path.write_text(ROLLBACK_DOC_CONTENT_V2, encoding="utf-8")

    # Force a real constraint violation (duplicate chunk provenance) so the DB
    # rejects the write partway through, exercising actual rollback against the
    # real database rather than a mocked failure.
    def _broken_chunk_document(parsed_doc, slug):
        chunks = chunk_document(parsed_doc, slug)
        return [*chunks, chunks[0]]

    monkeypatch.setattr(pipeline_module, "chunk_document", _broken_chunk_document)

    with pytest.raises(IntegrityError):
        ingest_document(doc_path, tmp_path, db_session)

    reloaded = db_session.execute(
        select(Document).where(Document.source_path == source_path)
    ).scalar_one()
    assert reloaded.source_content_hash == original_hash
    assert len(reloaded.chunks) == original_chunk_count
    assert sorted(c.text for c in reloaded.chunks) == original_chunk_texts


def test_stale_processing_version_forces_reprocessing_with_unchanged_bytes(
    tmp_path, db_session, cleanup_document
):
    # Same skip-rule conditional also checks embedding_model_name; not tested
    # separately by name since it's the identical code path with a different field.
    source_path = "service_docs/analytics.md"
    cleanup_document.append(source_path)
    _delete_document(db_session, source_path)

    content = "# Analytics Service\n\n## Overview\n\nFixture content for processing-version test.\n"
    doc_path = _write_fixture(tmp_path, source_path, content)

    first = ingest_document(doc_path, tmp_path, db_session)
    assert first.status == "created"

    # Simulate a stale processing_version on the stored row without touching the
    # source file at all, source bytes are unchanged throughout this test.
    stored = db_session.execute(
        select(Document).where(Document.source_path == source_path)
    ).scalar_one()
    stored.processing_version = pipeline_module.CURRENT_PROCESSING_VERSION - 1
    db_session.commit()

    second = ingest_document(doc_path, tmp_path, db_session)
    assert second.status == "updated"

    reloaded = db_session.execute(
        select(Document).where(Document.source_path == source_path)
    ).scalar_one()
    assert reloaded.processing_version == pipeline_module.CURRENT_PROCESSING_VERSION


def test_document_without_declared_service_mapping_fails_loudly(tmp_path, db_session):
    source_path = "unmapped_category/does-not-exist.md"
    assert source_path not in DOCUMENT_SERVICE  # sanity check on the fixture itself

    doc_path = _write_fixture(tmp_path, source_path, "# Some Title\n\n## A Section\n\nbody\n")

    with pytest.raises(KeyError, match="No service mapping declared"):
        ingest_document(doc_path, tmp_path, db_session)

    # nothing should have been written
    stored = db_session.execute(
        select(Document).where(Document.source_path == source_path)
    ).scalar_one_or_none()
    assert stored is None
