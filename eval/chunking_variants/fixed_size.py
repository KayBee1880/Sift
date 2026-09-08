"""Fixed-size, overlapping-window chunking: an alternative to app/ingestion/chunker.py's
structure-aware (per-H2-section) strategy A, used only for this eval experiment.

Deliberately not wired into app/ingestion/ or persisted to Postgres: fixed-size chunks
don't align to section boundaries the way the production schema's single
section_anchor-per-chunk field assumes, so supporting this for real would need a schema
change. This experiment stays entirely in-memory instead: parse with the existing
parser, slide a fixed-size token window with overlap across each document's flattened
text, embed those chunks, and hold everything in a plain list scored with numpy cosine
similarity. Same corpus text, same golden set, same embedding model as the baseline;
only the chunk-boundary logic differs.

A chunk "covers" a golden-set required/acceptable (document, section) if the chunk's
token span overlaps that section's original span in the document, not by exact
chunk-to-section identity (which strategy A has and this doesn't).
"""

from dataclasses import dataclass
from pathlib import Path

from app.ingestion.chunker import _tokenizer
from app.ingestion.parser import ParsedDocument, parse_markdown_document

WINDOW_TOKENS = 200
OVERLAP_TOKENS = 100
STEP_TOKENS = WINDOW_TOKENS - OVERLAP_TOKENS


@dataclass
class FixedSizeChunk:
    document_slug: str
    document_title: str
    chunk_index: int
    text: str
    embedding_text: str
    overlapping_sections: list[str]


def _flatten_document(doc: ParsedDocument) -> tuple[str, list[tuple[str, int, int]]]:
    """Concatenates preamble + all section bodies into one string, returning that
    string plus a list of (section_heading, char_start, char_end) spans within it.
    Preamble is folded into the first section's span, matching strategy A's
    convention, for a fair comparison (both strategies treat preamble the same way).
    """
    if not doc.sections:
        return doc.preamble, [("", 0, len(doc.preamble))] if doc.preamble else []

    parts = []
    spans = []
    cursor = 0
    for i, section in enumerate(doc.sections):
        body = section.body
        if i == 0 and doc.preamble.strip():
            body = f"{doc.preamble.strip()}\n\n{body}".strip()
        text = f"{section.heading}\n\n{body}\n\n"
        parts.append(text)
        spans.append((section.heading, cursor, cursor + len(text)))
        cursor += len(text)

    return "".join(parts), spans


def _sections_overlapping(
    char_start: int, char_end: int, spans: list[tuple[str, int, int]]
) -> list[str]:
    return [
        heading
        for heading, span_start, span_end in spans
        if char_start < span_end and char_end > span_start
    ]


def chunk_document_fixed_size(
    doc: ParsedDocument, document_slug: str, document_title: str
) -> list[FixedSizeChunk]:
    flattened, spans = _flatten_document(doc)
    if not flattened.strip():
        return []

    tokenizer = _tokenizer()
    encoding = tokenizer(flattened, return_offsets_mapping=True, add_special_tokens=False)
    offsets = encoding["offset_mapping"]
    if not offsets:
        return []

    chunks = []
    chunk_index = 0
    start_token = 0
    while start_token < len(offsets):
        end_token = min(start_token + WINDOW_TOKENS, len(offsets))
        char_start = offsets[start_token][0]
        char_end = offsets[end_token - 1][1]
        text = flattened[char_start:char_end].strip()

        if text:
            chunks.append(
                FixedSizeChunk(
                    document_slug=document_slug,
                    document_title=document_title,
                    chunk_index=chunk_index,
                    text=text,
                    embedding_text=f"{document_title}\n\n{text}",
                    overlapping_sections=_sections_overlapping(char_start, char_end, spans),
                )
            )
            chunk_index += 1

        if end_token == len(offsets):
            break
        start_token += STEP_TOKENS

    return chunks


def chunk_corpus_fixed_size(corpus_root: Path) -> list[FixedSizeChunk]:
    files = sorted(p for p in corpus_root.rglob("*.md") if p.name != "MANIFEST.md")
    all_chunks = []
    for path in files:
        doc = parse_markdown_document(path)
        slug = str(path.relative_to(corpus_root).with_suffix("")).replace("\\", "/")
        all_chunks.extend(chunk_document_fixed_size(doc, slug, doc.title))
    return all_chunks
