from dataclasses import dataclass
from functools import lru_cache

from transformers import AutoTokenizer

from app.config import get_settings
from app.ingestion.parser import ParsedDocument, ParsedSection

# Headroom below bge-small-en-v1.5's 512 token max, not a hard word-count guess.
SAFE_TOKEN_BUDGET = 400

# Below this, a section is considered too terse to stand alone and gets merged with
# an adjacent section, so a narrative neighbor's context carries into the same
# embedding as a section like "Resolution" that reads well as prose but under-ranks
# in isolation (see the within-document section-ranking bias in Baseline Error
# Analysis v1). Not empirically tuned beyond the merge-small-sections experiment
# (decision log, 2026-09-08), chosen as a fraction of the corpus-wide 13-199 token
# range strategy A's original validation observed. Adopted as the new baseline
# chunking strategy (decision log, 2026-09-08) after measuring a real Recall@5 gain
# with no schema change required, since merges are always contiguous sections.
MIN_SECTION_TOKENS = 80


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


def _section_body(section: ParsedSection, preamble: str) -> str:
    body = section.body
    if section.index == 0 and preamble.strip():
        body = f"{preamble.strip()}\n\n{body}".strip()
    return body


def _group_sections(doc: ParsedDocument) -> list[list[int]]:
    """Greedily groups consecutive section indices to merge into one chunk each,
    accumulating forward until MIN_SECTION_TOKENS is reached or the next section
    would push the group past SAFE_TOKEN_BUDGET. A trailing under-floor group
    merges backward into the previous group if it fits, rather than standing
    alone as an under-sized chunk. A single section that alone exceeds
    SAFE_TOKEN_BUDGET still becomes its own one-section group here, the
    oversized-section sub-split fallback in _chunk_group handles it from there,
    unchanged from strategy A's original behavior.
    """
    token_counts = [
        count_tokens(f"{section.heading}\n\n{_section_body(section, doc.preamble)}")
        for section in doc.sections
    ]

    groups: list[list[int]] = []
    current: list[int] = []
    current_tokens = 0
    for i, tokens in enumerate(token_counts):
        if current and current_tokens + tokens > SAFE_TOKEN_BUDGET:
            groups.append(current)
            current, current_tokens = [], 0
        current.append(i)
        current_tokens += tokens
        if current_tokens >= MIN_SECTION_TOKENS:
            groups.append(current)
            current, current_tokens = [], 0

    if current:
        if groups and sum(token_counts[i] for i in groups[-1]) + current_tokens <= SAFE_TOKEN_BUDGET:
            groups[-1].extend(current)
        else:
            groups.append(current)

    return groups


def _chunk_group(
    document_slug: str,
    document_title: str,
    doc: ParsedDocument,
    group: list[int],
) -> list[Chunk]:
    sections = [doc.sections[i] for i in group]
    bodies = [_section_body(s, doc.preamble) for s in sections]
    headings = [s.heading for s in sections]
    section_anchor = " + ".join(headings)
    section_index = sections[0].index

    # Single-section group (the common case, most sections clear MIN_SECTION_TOKENS
    # on their own): text stays plain body, no heading duplicated inside it, since
    # the heading already lives in section_anchor. Matches strategy A's original
    # shape exactly for every section that isn't merged.
    if len(sections) == 1:
        text = bodies[0]
    else:
        # Merged group: headings interleaved directly before their own body, so a
        # citation spanning multiple named sections shows which part is which, and
        # the embedding sees exactly the text arrangement measured in the
        # merge-small-sections experiment, not just a similar-looking one.
        text = "\n\n".join(f"{h}\n\n{b}" for h, b in zip(headings, bodies, strict=True))

    group_content = "\n\n".join(f"{h}\n\n{b}" for h, b in zip(headings, bodies, strict=True))
    embedding_text = f"{document_title}\n\n{group_content}"

    if count_tokens(embedding_text) <= SAFE_TOKEN_BUDGET:
        return [
            Chunk(
                document_slug=document_slug,
                section_anchor=section_anchor,
                section_index=section_index,
                section_chunk_index=0,
                text=text,
                embedding_text=embedding_text,
            )
        ]

    # Oversized: only reachable for a single section that alone exceeds the
    # budget (_group_sections never lets a multi-section group exceed it), sub-
    # split deterministically on paragraph boundaries, sharing the same
    # section_anchor/section_index across all resulting sub-chunks. Not expected
    # to trigger on corpus v1.0 (see the corpus-wide validation report), this
    # path exists defensively for future, longer documents.
    header = f"{document_title}\n\n{headings[0]}\n\n"
    header_tokens = count_tokens(header)
    body_budget = max(SAFE_TOKEN_BUDGET - header_tokens, 50)
    sub_bodies = _split_into_subchunks(bodies[0], body_budget)
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
        body = doc.preamble.strip()
        embedding_text = f"{doc.title}\n\n{body}"

        if count_tokens(embedding_text) <= SAFE_TOKEN_BUDGET:
            return [
                Chunk(
                    document_slug=document_slug,
                    section_anchor=None,
                    section_index=0,
                    section_chunk_index=0,
                    text=body,
                    embedding_text=embedding_text,
                )
            ]

        # Oversized preamble-only document: same deterministic paragraph-boundary
        # sub-split fallback as a normal oversized section, not expected to
        # trigger on corpus v1.0, kept for the same defensive reason.
        header = f"{doc.title}\n\n"
        header_tokens = count_tokens(header)
        body_budget = max(SAFE_TOKEN_BUDGET - header_tokens, 50)
        sub_bodies = _split_into_subchunks(body, body_budget)
        return [
            Chunk(
                document_slug=document_slug,
                section_anchor=None,
                section_index=0,
                section_chunk_index=i,
                text=sub_body,
                embedding_text=f"{header}{sub_body}",
            )
            for i, sub_body in enumerate(sub_bodies)
        ]

    groups = _group_sections(doc)
    chunks: list[Chunk] = []
    for group in groups:
        # A group can include a section with an empty body (e.g. a heading with
        # no content below it before the next heading); drop those from the
        # group rather than embedding an empty section, matching strategy A's
        # original empty-section skip behavior.
        non_empty_group = [
            i for i in group if _section_body(doc.sections[i], doc.preamble).strip()
        ]
        if not non_empty_group:
            continue
        chunks.extend(_chunk_group(document_slug, doc.title, doc, non_empty_group))
    return chunks
