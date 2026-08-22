from dataclasses import dataclass
from functools import lru_cache

from transformers import AutoTokenizer

from app.config import get_settings
from app.ingestion.parser import ParsedDocument

# Headroom below bge-small-en-v1.5's 512 token max, not a hard word-count guess.
SAFE_TOKEN_BUDGET = 400


@dataclass
class Chunk:
    document_slug: str
    section_anchor: str | None
    section_index: int
    section_chunk_index: int
    text: str
    embedding_text: str


@lru_cache
def _tokenizer():
    return AutoTokenizer.from_pretrained(get_settings().embedding_model_name)


def count_tokens(text: str) -> int:
    return len(_tokenizer().encode(text, add_special_tokens=True))


def _split_into_subchunks(body: str, token_budget: int) -> list[str]:
    paragraphs = [p.strip() for p in body.split("\n\n") if p.strip()]
    if not paragraphs:
        return [body] if body.strip() else []

    subchunks: list[str] = []
    current: list[str] = []
    current_tokens = 0
    for paragraph in paragraphs:
        paragraph_tokens = count_tokens(paragraph)
        if current and current_tokens + paragraph_tokens > token_budget:
            subchunks.append("\n\n".join(current))
            current = [paragraph]
            current_tokens = paragraph_tokens
        else:
            current.append(paragraph)
            current_tokens += paragraph_tokens
    if current:
        subchunks.append("\n\n".join(current))
    return subchunks


def _build_embedding_header(document_title: str, section_anchor: str | None) -> str:
    if section_anchor is None:
        return f"{document_title}\n\n"
    return f"{document_title}\nSection: {section_anchor}\n\n"


def _chunk_section(
    document_slug: str,
    document_title: str,
    section_anchor: str | None,
    section_index: int,
    body: str,
) -> list[Chunk]:
    header = _build_embedding_header(document_title, section_anchor)
    embedding_text = f"{header}{body}"

    if count_tokens(embedding_text) <= SAFE_TOKEN_BUDGET:
        return [
            Chunk(
                document_slug=document_slug,
                section_anchor=section_anchor,
                section_index=section_index,
                section_chunk_index=0,
                text=body,
                embedding_text=embedding_text,
            )
        ]

    # Oversized: sub-split deterministically on paragraph boundaries, sharing the
    # same section_anchor/section_index across all resulting sub-chunks. Not
    # expected to trigger on corpus v1.0 (see the corpus-wide validation report),
    # this path exists defensively for future, longer documents.
    header_tokens = count_tokens(header)
    body_budget = max(SAFE_TOKEN_BUDGET - header_tokens, 50)
    sub_bodies = _split_into_subchunks(body, body_budget)
    return [
        Chunk(
            document_slug=document_slug,
            section_anchor=section_anchor,
            section_index=section_index,
            section_chunk_index=i,
            text=sub_body,
            embedding_text=f"{header}{sub_body}",
        )
        for i, sub_body in enumerate(sub_bodies)
    ]


def chunk_document(doc: ParsedDocument, document_slug: str) -> list[Chunk]:
    if not doc.sections:
        if not doc.preamble.strip():
            return []
        return _chunk_section(document_slug, doc.title, None, 0, doc.preamble.strip())

    chunks: list[Chunk] = []
    for section in doc.sections:
        body = section.body
        if section.index == 0 and doc.preamble.strip():
            body = f"{doc.preamble.strip()}\n\n{body}".strip()
        if not body.strip():
            continue
        chunks.extend(
            _chunk_section(document_slug, doc.title, section.heading, section.index, body)
        )
    return chunks
