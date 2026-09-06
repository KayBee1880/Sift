from dataclasses import asdict

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.generation.service import generate_answer
from app.retrieval.reranker import rerank
from app.retrieval.service import retrieve
from app.schemas.query import CitationResponse, QueryRequest, QueryResponse

router = APIRouter()

# retrieve()'s top-10 reranked, top-5 kept for generation: the adopted retrieval
# configuration verified in the reranking experiment (2026-09-01).
RETRIEVAL_DEPTH = 10
GENERATION_TOP_K = 5


@router.post("/query", response_model=QueryResponse)
def query(request: QueryRequest, session: Session = Depends(get_db)) -> QueryResponse:
    candidates = retrieve(request.query, top_k=RETRIEVAL_DEPTH, session=session)
    reranked = rerank(request.query, candidates, top_k=GENERATION_TOP_K)
    result = generate_answer(request.query, reranked)

    return QueryResponse(
        answer=result.answer,
        citations=[CitationResponse(**asdict(c)) for c in result.citations],
        abstained=result.abstained,
    )
