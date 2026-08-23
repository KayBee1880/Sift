import pytest
from sqlalchemy import func, select

from app.db.models import Chunk
from app.db.session import SessionLocal
from app.retrieval.service import retrieve


@pytest.fixture
def db_session():
    session = SessionLocal()
    yield session
    session.close()


def test_empty_query_raises(db_session):
    with pytest.raises(ValueError, match="empty or whitespace-only"):
        retrieve("", top_k=5, session=db_session)


def test_whitespace_only_query_raises(db_session):
    with pytest.raises(ValueError, match="empty or whitespace-only"):
        retrieve("   \n\t  ", top_k=5, session=db_session)


def test_zero_top_k_raises(db_session):
    with pytest.raises(ValueError, match="top_k must be positive"):
        retrieve("payments gateway timeout", top_k=0, session=db_session)


def test_negative_top_k_raises(db_session):
    with pytest.raises(ValueError, match="top_k must be positive"):
        retrieve("payments gateway timeout", top_k=-1, session=db_session)


def test_returns_requested_number_of_results(db_session):
    results = retrieve("payments gateway timeout connection pool", top_k=5, session=db_session)
    assert len(results) == 5


def test_top_k_larger_than_corpus_returns_all_available_chunks(db_session):
    total_chunks = db_session.execute(select(func.count()).select_from(Chunk)).scalar_one()
    results = retrieve("payments gateway timeout", top_k=total_chunks + 1000, session=db_session)
    assert len(results) == total_chunks


def test_results_ordered_by_increasing_cosine_distance(db_session):
    results = retrieve("session store memory eviction login failures", top_k=10, session=db_session)
    distances = [r.cosine_distance for r in results]
    assert distances == sorted(distances)


def test_cosine_similarity_is_exactly_one_minus_distance(db_session):
    results = retrieve("checkout fraud precheck rejection", top_k=5, session=db_session)
    for r in results:
        assert r.cosine_similarity == pytest.approx(1.0 - r.cosine_distance, abs=1e-9)


def test_provenance_fields_are_populated_and_consistent(db_session):
    results = retrieve("payments gateway timeout connection pool", top_k=3, session=db_session)
    for r in results:
        assert r.chunk_id > 0
        assert r.document_id > 0
        assert "/" in r.document_slug  # e.g. "incidents/..."
        assert r.source_path.endswith(".md")
        assert r.document_title
        assert r.category
        assert r.section_anchor
        assert r.section_index >= 0
        assert r.section_chunk_index >= 0
        assert r.text


def test_repeated_query_returns_identical_order_deterministically(db_session):
    # True floating-point ties between two distinct real embeddings are not
    # practically reproducible to test directly, this instead confirms the
    # secondary sort key (chunk id) makes the full ordering deterministic run to
    # run, which is what actually matters for reproducible evaluation.
    first = retrieve("analytics dashboard stale data", top_k=10, session=db_session)
    second = retrieve("analytics dashboard stale data", top_k=10, session=db_session)
    assert [r.chunk_id for r in first] == [r.chunk_id for r in second]


def test_persisted_corpus_vectors_are_unit_normalized(db_session):
    # Integration-level check that the normalization invariant the baseline's
    # ranking-equivalence reasoning depends on actually holds for the real,
    # persisted embeddings, not just newly generated ones. No database trigger or
    # constraint enforces this, it's verified here instead.
    norms = db_session.execute(select(func.vector_norm(Chunk.embedding))).scalars().all()
    assert len(norms) > 0
    assert all(abs(n - 1.0) < 1e-3 for n in norms)


def test_obviously_relevant_query_surfaces_a_plausible_document(db_session):
    # Broad smoke test only, no specific rank asserted, that's what the golden-set
    # evaluation runner measures precisely and separately. Accepts either the
    # literal service doc or its known acceptable substitute (see q001 in the
    # golden set), a first real run of this exact query showed the retriever
    # correctly finds the substitute and ranks it above the nominal document, a
    # legitimate outcome under the four-tier schema, not a retrieval failure. A
    # test asserting only the literal document would have been the brittle,
    # rank-position-guessing test the retrieval-testing guidance warned against.
    results = retrieve(
        "what channels does the notifications service support for sending messages",
        top_k=5,
        session=db_session,
    )
    plausible_slugs = {"service_docs/notifications", "runbooks/notifications-delivery-failure"}
    assert any(r.document_slug in plausible_slugs for r in results)
