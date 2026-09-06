from pydantic import BaseModel


class QueryRequest(BaseModel):
    query: str


class CitationResponse(BaseModel):
    ref: int
    document_slug: str
    section_anchor: str | None
    document_title: str
    source_path: str


class QueryResponse(BaseModel):
    answer: str
    citations: list[CitationResponse]
    abstained: bool
