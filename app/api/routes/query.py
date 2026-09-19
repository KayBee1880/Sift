import logging
import time
from dataclasses import asdict

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.db.models import User
from app.db.session import get_db
from app.generation.service import generate_answer
from app.retrieval.reranker import rerank
from app.retrieval.service import retrieve
from app.schemas.query import CitationResponse, QueryRequest, QueryResponse

router = APIRouter()
logger = logging.getLogger("sift.query")

# retrieve()'s top-10 reranked, top-5 kept for generation: the adopted retrieval
# configuration verified in the reranking experiment (2026-09-01).
RETRIEVAL_DEPTH = 10
GENERATION_TOP_K = 5


@router.post("/query", response_model=QueryResponse)
def query(
    request: QueryRequest,
    session: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> QueryResponse:
    retrieval_start = time.perf_counter()
    candidates = retrieve(
        request.query,
        top_k=RETRIEVAL_DEPTH,
        session=session,
        allowed_services=current_user.allowed_services,
    )
    reranked = rerank(request.query, candidates, top_k=GENERATION_TOP_K)
    retrieval_seconds = time.perf_counter() - retrieval_start

    generation_start = time.perf_counter()
    result = generate_answer(request.query, reranked)
    generation_seconds = time.perf_counter() - generation_start

    # Deliberately no raw query text here — usernames identify the account
    # (not real PII for this demo system), but the query body could contain
    # anything a caller types, so it's left out of logs on principle, the
    # same restraint already applied to embedding vectors and document bodies
    # elsewhere in this project (see app/ingestion/pipeline.py's walkthrough).
    logger.info(
        "query handled",
        extra={
            "username": current_user.username,
            "abstained": result.abstained,
            "citation_count": len(result.citations),
            "retrieval_seconds": round(retrieval_seconds, 3),
            "generation_seconds": round(generation_seconds, 3),
        },
    )

    return QueryResponse(
        answer=result.answer,
        citations=[CitationResponse(**asdict(c)) for c in result.citations],
        abstained=result.abstained,
    )
