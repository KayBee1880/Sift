"""Merge-small-sections chunking: a middle ground between app/ingestion/chunker.py's
strategy A (one chunk per H2 section, always) and the fixed-size sliding-window
variant (section boundaries ignored entirely).

Keeps one-chunk-per-section as the default. Only merges a section with its
neighbor when it falls below a minimum token floor, so a terse "Resolution"
section is folded in with an adjacent narrative section instead of standing
alone, without ever needing to know or guess a specific section *name* the way
the reverted sibling-heading variant did.

Unlike fixed-size chunking, this is compatible with the existing production
schema without a migration: a merged group's section_anchor can be represented
as a plain joined string ("Evidence + Resolution"), and section_index can be the
first section's original index, since merges are always contiguous. Still
measured here entirely in-memory first, per the project's measure-before-adopt
practice, not because the schema can't support it.
"""

from dataclasses import dataclass
from pathlib import Path

from app.ingestion.chunker import SAFE_TOKEN_BUDGET, count_tokens
from app.ingestion.parser import ParsedDocument, ParsedSection, parse_markdown_document

# Below this, a section is considered too terse to stand alone and gets merged
# with a neighbor. Not empirically tuned, chosen as a fraction of the 13-199
# token range observed corpus-wide under strategy A, deliberately on the small
# side so this only triggers for genuinely short sections, not moderate ones.
MIN_CHUNK_TOKENS = 80
MAX_CHUNK_TOKENS = SAFE_TOKEN_BUDGET


@dataclass
class MergedChunk:
    document_slug: str
    document_title: str
    chunk_index: int
    text: str
    embedding_text: str
    overlapping_sections: list[str]


def _section_text(section: ParsedSection, preamble: str) -> str:
    body = section.body
    if section.index == 0 and preamble.strip():
        body = f"{preamble.strip()}\n\n{body}".strip()
    return f"{section.heading}\n\n{body}"


def _group_sections(sections: list[ParsedSection], preamble: str) -> list[list[ParsedSection]]:
    """Greedily merges consecutive sections forward until a group's token count
    reaches MIN_CHUNK_TOKENS or the next section would push it past
    MAX_CHUNK_TOKENS. A trailing group still under the floor is merged backward
    into the previous group instead of being left as an under-sized chunk on
    its own, if it fits within the ceiling.
    """
    texts = [_section_text(s, preamble) for s in sections]
    token_counts = [count_tokens(t) for t in texts]

    groups: list[list[int]] = []
    current: list[int] = []
    current_tokens = 0
    for i, tokens in enumerate(token_counts):
        if current and current_tokens + tokens > MAX_CHUNK_TOKENS:
            groups.append(current)
            current, current_tokens = [], 0
        current.append(i)
        current_tokens += tokens
        if current_tokens >= MIN_CHUNK_TOKENS:
            groups.append(current)
            current, current_tokens = [], 0

    if current:
        if groups:
            prev_tokens = sum(token_counts[i] for i in groups[-1])
            if prev_tokens + current_tokens <= MAX_CHUNK_TOKENS:
                groups[-1].extend(current)
            else:
                groups.append(current)
        else:
            groups.append(current)

    return [[sections[i] for i in group] for group in groups]


def chunk_document_merged(
    doc: ParsedDocument, document_slug: str, document_title: str
) -> list[MergedChunk]:
    if not doc.sections:
        if not doc.preamble.strip():
            return []
        text = doc.preamble.strip()
        return [
            MergedChunk(
                document_slug=document_slug,
                document_title=document_title,
                chunk_index=0,
                text=text,
                embedding_text=f"{document_title}\n\n{text}",
                overlapping_sections=[],
            )
        ]

    groups = _group_sections(doc.sections, doc.preamble)
    chunks = []
    for chunk_index, group in enumerate(groups):
        texts = [_section_text(s, doc.preamble) for s in group]
        combined_text = "\n\n".join(texts)
        headings = [s.heading for s in group]
        chunks.append(
            MergedChunk(
                document_slug=document_slug,
                document_title=document_title,
                chunk_index=chunk_index,
                text=combined_text,
                embedding_text=f"{document_title}\n\n{combined_text}",
                overlapping_sections=headings,
            )
        )
    return chunks


def chunk_corpus_merged(corpus_root: Path) -> list[MergedChunk]:
    files = sorted(p for p in corpus_root.rglob("*.md") if p.name != "MANIFEST.md")
    all_chunks = []
    for path in files:
        doc = parse_markdown_document(path)
        slug = str(path.relative_to(corpus_root).with_suffix("")).replace("\\", "/")
        all_chunks.extend(chunk_document_merged(doc, slug, doc.title))
    return all_chunks
