from itertools import pairwise
from pathlib import Path

from app.ingestion.chunker import (
    OVERLAP_TOKENS,
    STEP_TOKENS,
    WINDOW_TOKENS,
    chunk_document,
    count_tokens,
)
from app.ingestion.parser import parse_markdown_document, parse_markdown_text

CORPUS_ROOT = Path(__file__).resolve().parent.parent / "corpus"


def test_window_step_and_overlap_are_consistent():
    assert WINDOW_TOKENS == 200
    assert OVERLAP_TOKENS == 100
    assert STEP_TOKENS == WINDOW_TOKENS - OVERLAP_TOKENS


def test_short_single_section_document_produces_one_fully_overlapping_chunk():
    text = "# Title\n\n## Only Section\n\nA short body that fits in a single window.\n"
    doc = parse_markdown_text(text)
    chunks = chunk_document(doc, "test-doc")

    assert len(chunks) == 1
    # The whole document fits in one window, and there's only one section, so that
    # section covers 100% of the window, not merely "most" of it.
    assert chunks[0].overlapping_sections == [
        {"section": "Only Section", "overlap_fraction": 1.0}
    ]
    assert chunks[0].section_anchor == "Only Section"
    assert chunks[0].section_index == 0
    assert chunks[0].section_chunk_index == 0


def test_embedding_text_is_title_plus_window_text():
    text = "# My Title\n\n## A Section\n\nSome body text.\n"
    doc = parse_markdown_text(text)
    chunks = chunk_document(doc, "test-doc")
    assert chunks[0].embedding_text == f"My Title\n\n{chunks[0].text}"


def test_preamble_folds_into_first_sections_window():
    text = "# Title\n\n**Severity:** SEV2\n\n## Summary\n\nShort body.\n"
    doc = parse_markdown_text(text)
    chunks = chunk_document(doc, "test-doc")

    assert len(chunks) == 1
    assert "Severity" in chunks[0].text
    # A single section still fully dominates its own window even with preamble text
    # folded in ahead of it, since there's nothing else in the document to compete
    # with for the window's character span.
    assert chunks[0].overlapping_sections == [{"section": "Summary", "overlap_fraction": 1.0}]


def test_document_with_no_sections_but_preamble_becomes_one_chunk():
    text = "# Title\n\nJust prose, no headings.\n"
    doc = parse_markdown_text(text)
    chunks = chunk_document(doc, "test-doc")

    assert len(chunks) == 1
    # "" (empty string), not None: satisfies the DB column's NOT NULL constraint
    # (app/db/models.py's Chunk.section_anchor) and matches the exact convention
    # already measured in eval/chunking_variants/fixed_size.py's own preamble-only
    # handling, not an approximation of it.
    assert chunks[0].section_anchor == ""
    assert chunks[0].section_index == 0
    assert chunks[0].overlapping_sections == [{"section": "", "overlap_fraction": 1.0}]
    assert chunks[0].text == "Just prose, no headings."


def test_document_with_no_sections_and_no_preamble_produces_no_chunks():
    text = "# Title\n"
    doc = parse_markdown_text(text)
    assert chunk_document(doc, "test-doc") == []


def test_a_window_spanning_two_sections_reports_both_with_fractions_summing_to_one():
    # Two short sections, together still well under WINDOW_TOKENS, so one window
    # covers both, split proportionally to each section's own character length,
    # not evenly 50/50 (the two bodies here are different lengths on purpose).
    text = "# Title\n\n## First\n\nShort.\n\n## Second\n\nA noticeably longer second body.\n"
    doc = parse_markdown_text(text)
    chunks = chunk_document(doc, "test-doc")

    assert len(chunks) == 1
    overlaps = chunks[0].overlapping_sections
    assert {e["section"] for e in overlaps} == {"First", "Second"}
    # Sorted descending by overlap_fraction, largest first — the longer section
    # ("Second") legitimately dominates, and dominance is what section_anchor uses.
    assert overlaps[0]["overlap_fraction"] >= overlaps[1]["overlap_fraction"]
    assert chunks[0].section_anchor == overlaps[0]["section"]
    assert sum(e["overlap_fraction"] for e in overlaps) == 1.0


def test_long_single_section_produces_multiple_overlapping_chunks():
    padding_sentence = "This is a padding sentence with a handful of extra words in it. "
    long_body = padding_sentence * 80  # well over WINDOW_TOKENS on its own
    text = f"# Title\n\n## Only Section\n\n{long_body}\n"
    doc = parse_markdown_text(text)
    chunks = chunk_document(doc, "test-doc")

    assert len(chunks) > 1
    # Every chunk stays under WINDOW_TOKENS (plus a small margin for the title/
    # section-heading text folded into embedding_text, not counted against the
    # window itself, which is measured on the flattened body text alone).
    for chunk in chunks[:-1]:
        assert count_tokens(chunk.text) <= WINDOW_TOKENS + 5
    # A single section spanning the whole document dominates every window
    # entirely — there's nothing else for it to share overlap with.
    assert all(c.section_anchor == "Only Section" for c in chunks)
    expected_overlaps = [{"section": "Only Section", "overlap_fraction": 1.0}]
    assert all(c.overlapping_sections == expected_overlaps for c in chunks)
    # Sequential, gapless chunk indices, the provenance-uniqueness key alongside
    # section_index (app/db/models.py's uq_chunk_provenance).
    assert [c.section_chunk_index for c in chunks] == list(range(len(chunks)))

    # Consecutive windows genuinely overlap (step < window), not just abut: the
    # tail of one chunk's text should reappear near the head of the next.
    for earlier, later in pairwise(chunks):
        assert earlier.text[-30:] in later.text or earlier.text[-60:-30] in later.text


def test_representative_incident_postmortem_chunking_from_frozen_corpus():
    path = CORPUS_ROOT / "incidents" / "payments-gateway-timeout-connection-pool.md"
    doc = parse_markdown_document(path)
    chunks = chunk_document(doc, "incidents/payments-gateway-timeout-connection-pool")

    # Verified directly against the real, frozen corpus document, not predicted
    # from reading the windowing algorithm on paper (decision log, 2026-09-16).
    assert len(chunks) == 5
    assert [c.section_anchor for c in chunks] == [
        "Timeline",
        "Root Cause",
        "Root Cause",
        "Evidence",
        "Follow-up Actions",
    ]
    assert [c.section_chunk_index for c in chunks] == [0, 1, 2, 3, 4]
    for chunk in chunks:
        fractions = [e["overlap_fraction"] for e in chunk.overlapping_sections]
        assert chunk.section_anchor == chunk.overlapping_sections[0]["section"]
        assert fractions == sorted(fractions, reverse=True)
        assert abs(sum(fractions) - 1.0) < 0.001


def test_representative_runbook_chunking_from_frozen_corpus():
    path = CORPUS_ROOT / "runbooks" / "payments-gateway-timeout-troubleshooting.md"
    doc = parse_markdown_document(path)
    chunks = chunk_document(doc, "runbooks/payments-gateway-timeout-troubleshooting")

    assert len(chunks) == 3
    assert [c.section_anchor for c in chunks] == [
        "Diagnostic Steps",
        "Diagnostic Steps",
        "Common Causes",
    ]
    assert "Severity" not in chunks[0].text  # no preamble in this document type
