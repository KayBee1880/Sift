from dataclasses import dataclass
from functools import lru_cache

from transformers import AutoTokenizer

from app.config import get_settings
from app.ingestion.parser import ParsedDocument

# Headroom below bge-small-en-v1.5's 512 token max. Kept here for
# eval/chunking_variants/merge_small_sections.py, which still imports this
# constant (and count_tokens below) directly to reproduce that no-longer-adopted
# experiment if ever re-run. The current production strategy below doesn't need
# it as a constraint of its own: each fixed-size window is bounded by
# construction (see WINDOW_TOKENS), never needs a sub-split fallback the way
# merge-small-sections' variable-size groups sometimes did.
SAFE_TOKEN_BUDGET = 400

# Sliding-window size and step, matching exactly what
# eval/chunking_variants/fixed_size.py measured (experiment log, 2026-09-07/08):
# 200-token windows, 100-token (50%) overlap between consecutive windows.
# Adopted for production (decision log, 2026-09-16), replacing merge-small-
# sections entirely, the same way merge-small-sections replaced strategy A.
WINDOW_TOKENS = 200
OVERLAP_TOKENS = 100
STEP_TOKENS = WINDOW_TOKENS - OVERLAP_TOKENS


@dataclass
class Chunk:
    document_slug: str
    # The dominant section only (largest overlap_fraction in overlapping_sections
    # below) — see app/db/models.py's Chunk.section_anchor comment for why this
    # is deliberately not a join of every section the chunk touches.
    section_anchor: str
    section_index: int
    section_chunk_index: int
    overlapping_sections: list[dict]
    text: str
    embedding_text: str


@lru_cache
def _tokenizer():
    return AutoTokenizer.from_pretrained(get_settings().embedding_model_name)


def count_tokens(text: str) -> int:
    return len(_tokenizer().encode(text, add_special_tokens=True))


def _flatten_document(doc: ParsedDocument) -> tuple[str, list[tuple[str, int, int, int]]]:
    """Concatenates preamble + all section bodies into one string, returning that
    string plus a list of (heading, char_start, char_end, original_section_index)
    spans within it, contiguous and gap-free so every character in the flattened
    text belongs to exactly one span. Preamble folds into the first section's
    span (or, for a document with no H2 sections at all, becomes its own single
    ""-headed span) — the exact convention already measured in
    eval/chunking_variants/fixed_size.py, not an approximation of it.
    """
    if not doc.sections:
        text = doc.preamble.strip()
        if not text:
            return "", []
        return text, [("", 0, len(text), 0)]

    parts = []
    spans = []
    cursor = 0
    for section in doc.sections:
        body = section.body
        if section.index == 0 and doc.preamble.strip():
            body = f"{doc.preamble.strip()}\n\n{body}".strip()
        text = f"{section.heading}\n\n{body}\n\n"
        parts.append(text)
        spans.append((section.heading, cursor, cursor + len(text), section.index))
        cursor += len(text)

    return "".join(parts), spans


def _overlaps(
    char_start: int, char_end: int, spans: list[tuple[str, int, int, int]]
) -> list[tuple[str, int, float]]:
    """Every span this [char_start, char_end) window touches, as
    (heading, original_section_index, overlap_fraction) triples, where
    overlap_fraction is that touch's share of the *window's* own length (not the
    section's), sorted descending. A tie keeps document order (Python's sort is
    stable), the same first-wins convention already used elsewhere in this
    project's chunking strategies (e.g. merge-small-sections' section_index).
    """
    window_len = char_end - char_start
    overlaps = []
    for heading, span_start, span_end, section_index in spans:
        overlap_start = max(char_start, span_start)
        overlap_end = min(char_end, span_end)
        overlap_len = overlap_end - overlap_start
        if overlap_len > 0:
            overlaps.append((heading, section_index, round(overlap_len / window_len, 4)))
    overlaps.sort(key=lambda entry: -entry[2])
    return overlaps


def chunk_document(doc: ParsedDocument, document_slug: str) -> list[Chunk]:
    flattened, spans = _flatten_document(doc)
    if not flattened.strip():
        return []

    tokenizer = _tokenizer()
    encoding = tokenizer(flattened, return_offsets_mapping=True, add_special_tokens=False)
    offsets = encoding["offset_mapping"]
    if not offsets:
        return []

    chunks: list[Chunk] = []
    chunk_index = 0
    start_token = 0
    while start_token < len(offsets):
        end_token = min(start_token + WINDOW_TOKENS, len(offsets))
        char_start = offsets[start_token][0]
        char_end = offsets[end_token - 1][1]
        text = flattened[char_start:char_end].strip()

        if text:
            overlaps = _overlaps(char_start, char_end, spans)
            # Unreachable in practice: spans are contiguous and gap-free over the
            # entire flattened text, so a window derived from real tokenizer
            # offsets within it always overlaps at least one span. Kept as an
            # explicit fallback rather than an assumption, same defensive spirit
            # as other "should never happen" branches already in this codebase.
            dominant_heading, dominant_index = (
                (overlaps[0][0], overlaps[0][1]) if overlaps else ("", 0)
            )
            chunks.append(
                Chunk(
                    document_slug=document_slug,
                    section_anchor=dominant_heading,
                    section_index=dominant_index,
                    section_chunk_index=chunk_index,
                    overlapping_sections=[
                        {"section": heading, "overlap_fraction": fraction}
                        for heading, _section_index, fraction in overlaps
                    ],
                    text=text,
                    embedding_text=f"{doc.title}\n\n{text}",
                )
            )
            chunk_index += 1

        if end_token == len(offsets):
            break
        start_token += STEP_TOKENS

    return chunks
