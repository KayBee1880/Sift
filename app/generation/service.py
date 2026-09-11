import re
import time
from dataclasses import dataclass

import httpx

from app.config import get_settings
from app.retrieval.reranker import RerankedChunk

GROQ_CHAT_COMPLETIONS_URL = "https://api.groq.com/openai/v1/chat/completions"

# Below this, the strongest retrieved chunk is so dissimilar to the query that
# calling the model is pointless: abstain immediately rather than risk it
# synthesizing an answer from noise, and skip a wasted API call. Not empirically
# tuned against a labeled set of genuinely out-of-corpus queries (the golden set's
# abstain cases are all topically adjacent by design, specifically so this floor
# alone can't catch them, see MODEL_ABSTENTION_SENTINEL below), a conservative
# placeholder pending real out-of-scope query data.
MIN_RETRIEVAL_SIMILARITY = 0.3

# Deterministic, greppable sentinel the model is instructed to emit verbatim when it
# cannot answer from the given context. Detecting this exact prefix is far more
# reliable than fuzzy-matching natural-language phrases like "I don't know" in
# free-form prose, which the model could phrase many different ways.
MODEL_ABSTENTION_SENTINEL = "INSUFFICIENT_EVIDENCE:"

SYSTEM_PROMPT = (
    "You are Sift, an assistant that answers questions using only the numbered "
    "excerpts provided below. Cite every factual claim using ONLY the exact format "
    "[N] (a bare number in square brackets, e.g. [1] or [2]) immediately after the "
    "claim it supports. Do not use any other citation style — no footnote markers, "
    "no source names, no special characters, nothing but [N]. Do not use any "
    "knowledge beyond what the excerpts state.\n\n"
    "This applies just as strictly to recommended actions, remediation steps, or "
    "next steps as it does to factual claims: never infer or suggest a plausible-"
    "sounding action, fix, or step that is not explicitly stated in an excerpt, "
    "even if it seems like a reasonable thing to recommend.\n\n"
    "If a question has multiple parts and the excerpts only cover some of them, "
    "answer the part(s) you have evidence for and explicitly state that the "
    "excerpts do not specify the rest — do not fill the gap with a plausible "
    "guess.\n\n"
    f'If the excerpts do not contain enough information to answer any part of '
    f'the question, respond with exactly "{MODEL_ABSTENTION_SENTINEL}" followed by '
    "a brief, specific explanation of what is missing, and nothing else."
)


@dataclass
class Citation:
    ref: int
    document_slug: str
    section_anchor: str | None
    document_title: str
    source_path: str


@dataclass
class GenerationResult:
    answer: str
    citations: list[Citation]
    abstained: bool
    prompt_tokens: int
    completion_tokens: int


def build_context(chunks: list[RerankedChunk]) -> tuple[str, list[Citation]]:
    """Number each chunk for citation and render it into a single context block.

    Citation numbers are assigned in the given (post-rerank) order, 1-indexed to
    match how the prompt instructs the model to cite them.
    """
    blocks = []
    citations = []
    for ref, rc in enumerate(chunks, start=1):
        chunk = rc.chunk
        blocks.append(
            f"[{ref}] {chunk.document_title} — {chunk.section_anchor}\n{chunk.text}"
        )
        citations.append(
            Citation(
                ref=ref,
                document_slug=chunk.document_slug,
                section_anchor=chunk.section_anchor,
                document_title=chunk.document_title,
                source_path=chunk.source_path,
            )
        )
    return "\n\n".join(blocks), citations


CITATION_REF_PATTERN = re.compile(r"\[(\d+)\]")


def _cited_refs(answer: str) -> set[int]:
    return {int(ref) for ref in CITATION_REF_PATTERN.findall(answer)}


def build_messages(query: str, context: str) -> list[dict]:
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Excerpts:\n\n{context}\n\nQuestion: {query}"},
    ]


GROQ_MAX_RETRIES = 3
GROQ_RETRY_BACKOFF_SECONDS = 5.0


@dataclass
class GroqCallResult:
    content: str
    prompt_tokens: int
    completion_tokens: int


def _call_groq(messages: list[dict]) -> GroqCallResult:
    settings = get_settings()
    for attempt in range(GROQ_MAX_RETRIES):
        response = httpx.post(
            GROQ_CHAT_COMPLETIONS_URL,
            headers={"Authorization": f"Bearer {settings.groq_api_key}"},
            json={
                "model": settings.groq_model_name,
                "messages": messages,
                # Deterministic-leaning, not a bitwise-reproducibility claim: grounded
                # citation generation benefits from low temperature, same convention
                # already recorded for the embedding model's eval() call.
                "temperature": 0.0,
            },
            timeout=30.0,
        )
        # Free-tier rate limits are a real, expected condition here (not a
        # can't-happen case), not just under eval load with many calls back to
        # back but potentially under real traffic too, worth handling once here
        # rather than in every caller.
        if response.status_code == 429 and attempt < GROQ_MAX_RETRIES - 1:
            time.sleep(GROQ_RETRY_BACKOFF_SECONDS * (attempt + 1))
            continue
        response.raise_for_status()
        body = response.json()
        # Groq's chat-completions response is OpenAI-compatible and documents a
        # `usage` field, but this hasn't been confirmed against a real response by
        # this project yet, so default to 0 rather than raising if it's ever
        # missing or shaped differently. Free-tier cost has no dollar amount to
        # track (Groq's free tier is $0), so token counts are the meaningful "cost"
        # proxy against free-tier rate limits, the same constraint the retry logic
        # above already exists to handle.
        usage = body.get("usage") or {}
        return GroqCallResult(
            content=body["choices"][0]["message"]["content"],
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
        )

    raise AssertionError("unreachable: loop always returns or raises")


def _abstention_result() -> GenerationResult:
    return GenerationResult(
        answer="I don't have enough information in the available documentation to answer that.",
        citations=[],
        abstained=True,
        prompt_tokens=0,
        completion_tokens=0,
    )


def generate_answer(query: str, chunks: list[RerankedChunk]) -> GenerationResult:
    if not query or not query.strip():
        raise ValueError("generate_answer: query is empty or whitespace-only")

    if not chunks or max(rc.chunk.cosine_similarity for rc in chunks) < MIN_RETRIEVAL_SIMILARITY:
        return _abstention_result()

    context, citations = build_context(chunks)
    messages = build_messages(query, context)
    groq_result = _call_groq(messages)
    raw_answer = groq_result.content

    if raw_answer.strip().startswith(MODEL_ABSTENTION_SENTINEL):
        explanation = raw_answer.strip().removeprefix(MODEL_ABSTENTION_SENTINEL).strip()
        return GenerationResult(
            answer=explanation or _abstention_result().answer,
            citations=[],
            abstained=True,
            prompt_tokens=groq_result.prompt_tokens,
            completion_tokens=groq_result.completion_tokens,
        )

    # `citations` at this point is every chunk handed to the model as context, not
    # what the model actually cited. Filtering to refs that genuinely appear in the
    # answer text matters beyond eval bookkeeping: an unfiltered list would tell a
    # caller "these 5 sources support this answer" when the model may have only
    # drawn on 2 of them, a real, user-facing correctness gap, not just a cosmetic
    # one.
    used_citations = [c for c in citations if c.ref in _cited_refs(raw_answer)]
    return GenerationResult(
        answer=raw_answer,
        citations=used_citations,
        abstained=False,
        prompt_tokens=groq_result.prompt_tokens,
        completion_tokens=groq_result.completion_tokens,
    )
