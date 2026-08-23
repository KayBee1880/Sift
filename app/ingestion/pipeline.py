import hashlib
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import Chunk as ChunkRow
from app.db.models import Document
from app.embedding.service import embed_texts
from app.ingestion.chunker import Chunk, chunk_document
from app.ingestion.metadata import get_category_for_source_path, get_service_for_source_path
from app.ingestion.parser import parse_markdown_document

logger = logging.getLogger(__name__)

# Bump whenever a change requires re-chunking/re-embedding already-ingested documents:
# chunking algorithm changes, embedding-text construction changes, embedding model
# changes, normalization convention changes. Checked as part of the skip rule
# alongside embedding_model_name, which acts as an independent structural backstop
# rather than relying solely on this being bumped by hand every time it should be.
CURRENT_PROCESSING_VERSION = 1

IngestionStatus = Literal["created", "updated", "skipped"]


@dataclass
class IngestionResult:
    source_path: str
    slug: str
    status: IngestionStatus
    chunk_count: int


def compute_source_content_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_path_from_file(path: Path, corpus_root: Path) -> str:
    return str(path.relative_to(corpus_root)).replace("\\", "/")


def slug_from_source_path(source_path: str) -> str:
    return source_path.removesuffix(".md")


def _replace_document_chunks(
    session: Session,
    document: Document,
    chunks: list[Chunk],
    vectors: list[list[float]],
) -> None:
    # Clearing the ORM-managed collection schedules the previously associated rows
    # for deletion via the delete-orphan cascade already configured on the
    # relationship. For a brand-new document this is a no-op (nothing to clear),
    # which is why this same helper works for both the created and updated cases
    # without branching.
    document.chunks.clear()
    session.flush()
    for chunk, vector in zip(chunks, vectors, strict=True):
        session.add(
            ChunkRow(
                document_id=document.id,
                section_anchor=chunk.section_anchor,
                section_index=chunk.section_index,
                section_chunk_index=chunk.section_chunk_index,
                text=chunk.text,
                embedding=vector,
            )
        )


def ingest_document(path: Path, corpus_root: Path, session: Session) -> IngestionResult:
    """Parse, chunk, embed, and persist a single corpus document.

    Assumes a single ingestion writer. No distributed locking or concurrent-worker
    coordination is implemented; concurrent ingestion of the same document from two
    processes is not a supported scenario for this MVP.
    """
    source_path = source_path_from_file(path, corpus_root)
    slug = slug_from_source_path(source_path)
    settings = get_settings()

    source_content_hash = compute_source_content_hash(path)

    existing = session.execute(
        select(Document).where(Document.source_path == source_path)
    ).scalar_one_or_none()

    if (
        existing is not None
        and existing.source_content_hash == source_content_hash
        and existing.processing_version == CURRENT_PROCESSING_VERSION
        and existing.embedding_model_name == settings.embedding_model_name
    ):
        logger.info("ingest skipped: %s (unchanged)", source_path)
        return IngestionResult(
            source_path=source_path, slug=slug, status="skipped", chunk_count=len(existing.chunks)
        )

    # Resolve metadata first, before spending any compute on parsing/embedding, so a
    # missing service mapping fails fast rather than after doing wasted work.
    category = get_category_for_source_path(source_path)
    service = get_service_for_source_path(source_path)

    # Expensive work happens outside any database transaction: parsing and chunking
    # are pure computation, and embedding inference is orders of magnitude slower
    # than the SQL operations that follow. None of this needs a held transaction.
    parsed_doc = parse_markdown_document(path)
    chunks = chunk_document(parsed_doc, slug)
    vectors = embed_texts([c.embedding_text for c in chunks])

    try:
        if existing is None:
            document = Document(
                slug=slug,
                title=parsed_doc.title,
                category=category,
                service=service,
                source_path=source_path,
                source_content_hash=source_content_hash,
                processing_version=CURRENT_PROCESSING_VERSION,
                embedding_model_name=settings.embedding_model_name,
            )
            session.add(document)
            session.flush()
            status: IngestionStatus = "created"
        else:
            document = existing
            document.title = parsed_doc.title
            document.category = category
            document.service = service
            document.source_content_hash = source_content_hash
            document.processing_version = CURRENT_PROCESSING_VERSION
            document.embedding_model_name = settings.embedding_model_name
            status = "updated"

        _replace_document_chunks(session, document, chunks, vectors)
        session.commit()
    except Exception:
        session.rollback()
        logger.exception("ingest failed, rolled back: %s", source_path)
        raise

    logger.info("ingest %s: %s (%d chunks)", status, source_path, len(chunks))
    return IngestionResult(source_path=source_path, slug=slug, status=status, chunk_count=len(chunks))
