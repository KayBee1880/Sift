from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.sql import func

# Must match Settings.embedding_dimension in app/config.py (currently BAAI/bge-small-en-v1.5,
# 384 dims). Hardcoded rather than read from settings at import time because changing the
# embedding model is itself a migration-worthy event, not a runtime config toggle.
EMBEDDING_DIMENSION = 384


class Base(DeclarativeBase):
    pass


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    service: Mapped[str | None] = mapped_column(String(50), nullable=True)
    source_path: Mapped[str] = mapped_column(String(500), unique=True, nullable=False, index=True)
    source_content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    processing_version: Mapped[int] = mapped_column(Integer, nullable=False)
    embedding_model_name: Mapped[str] = mapped_column(String(255), nullable=False)
    extra_metadata: Mapped[dict] = mapped_column(
        "metadata", JSONB, nullable=False, default=dict
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )

    chunks: Mapped[list["Chunk"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )


class Chunk(Base):
    __tablename__ = "chunks"

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # The dominant section only (largest overlap_fraction in overlapping_sections
    # below) — what citations actually display (app/generation/service.py reads
    # this directly), kept honest for chunking strategies where a chunk's content
    # isn't evenly split across every section it happens to touch.
    section_anchor: Mapped[str] = mapped_column(String(255), nullable=False)
    section_index: Mapped[int] = mapped_column(Integer, nullable=False)
    section_chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    # Full per-section overlap detail: [{"section": str, "overlap_fraction": float}, ...],
    # sorted descending by overlap_fraction. Nullable — not every chunking strategy
    # needs to populate it (strategy A and merge-small-sections chunks never touch
    # more than one section-group, so section_anchor alone is already complete for
    # them). Used only by evaluation scoring (eval/run_baseline.py's _chunk_covers)
    # to credit retrieval for genuine partial coverage a citation shouldn't overstate
    # — coverage-for-scoring and citation-for-display are deliberately different
    # consumers of this same underlying data, see the fixed-size chunking decision
    # log entry (2026-09-16).
    overlapping_sections: Mapped[list[dict] | None] = mapped_column(JSONB, nullable=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIMENSION), nullable=False)

    document: Mapped["Document"] = relationship(back_populates="chunks")

    __table_args__ = (
        UniqueConstraint(
            "document_id", "section_index", "section_chunk_index", name="uq_chunk_provenance"
        ),
    )


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    # None (SQL NULL) means unrestricted access to every service, deliberately
    # mirroring the same NULL-means-universal convention already used for
    # Document.service (a NULL service there means "cross-cutting, visible
    # regardless of team"). A non-null list restricts retrieval to only those
    # service values — see app/retrieval/service.py's allowed_services filter.
    allowed_services: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )
