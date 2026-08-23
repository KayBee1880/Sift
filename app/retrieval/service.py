from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Chunk, Document
from app.embedding.service import embed_query


@dataclass
class RetrievedChunk:
    chunk_id: int
    document_id: int
    document_slug: str
    source_path: str
    document_title: str
    service: str | None
    category: str
    section_anchor: str
    section_index: int
    section_chunk_index: int
    text: str
    # cosine_distance is canonical: it's exactly what pgvector's <=> operator
    # computed and what results are ordered by. cosine_similarity (1 - distance)
    # is a derived convenience field for readability in reports, not recomputed
    # independently, so the two can never disagree.
    cosine_distance: float
    cosine_similarity: float


def retrieve(query: str, top_k: int, session: Session) -> list[RetrievedChunk]:
    """Exact cosine-distance nearest-neighbor search over all persisted chunks.

    Baseline strategy: exact search (no ANN index), appropriate at 171 chunks where
    computing distance to every row is trivial and an approximation would only add
    a confound to retrieval-quality measurement without solving any real latency
    problem. See the retrieval-mechanics discussion in the decision log for the full
    reasoning.

    top_k larger than the number of stored chunks returns all available chunks
    rather than raising, SQL LIMIT naturally does this without special-casing.
    """
    if top_k <= 0:
        raise ValueError(f"retrieve: top_k must be positive, got {top_k}")

    query_vector = embed_query(query)  # raises ValueError for empty/whitespace query

    distance = Chunk.embedding.cosine_distance(query_vector)

    stmt = (
        select(
            Chunk.id.label("chunk_id"),
            Chunk.document_id,
            Chunk.section_anchor,
            Chunk.section_index,
            Chunk.section_chunk_index,
            Chunk.text,
            distance.label("cosine_distance"),
            Document.slug.label("document_slug"),
            Document.source_path,
            Document.title.label("document_title"),
            Document.service,
            Document.category,
        )
        .join(Document, Chunk.document_id == Document.id)
        # Deterministic tie-breaking: ascending distance first (best match first),
        # then chunk id as a stable secondary key so two chunks at identical
        # distance always come back in the same order across runs, rather than
        # relying on unspecified database row order.
        .order_by(distance.asc(), Chunk.id.asc())
        .limit(top_k)
    )

    rows = session.execute(stmt).all()

    return [
        RetrievedChunk(
            chunk_id=row.chunk_id,
            document_id=row.document_id,
            document_slug=row.document_slug,
            source_path=row.source_path,
            document_title=row.document_title,
            service=row.service,
            category=row.category,
            section_anchor=row.section_anchor,
            section_index=row.section_index,
            section_chunk_index=row.section_chunk_index,
            text=row.text,
            cosine_distance=row.cosine_distance,
            cosine_similarity=1.0 - row.cosine_distance,
        )
        for row in rows
    ]
