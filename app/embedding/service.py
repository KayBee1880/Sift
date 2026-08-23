from functools import lru_cache

from sentence_transformers import SentenceTransformer

from app.config import get_settings

# BAAI/bge-small-en-v1.5's documented retrieval convention: queries get this
# instruction prepended, passages never do. Verified against the model's own
# documentation, not assumed. Applying it to passages, or omitting it from queries,
# would silently degrade retrieval quality without raising any error.
QUERY_INSTRUCTION_PREFIX = "Represent this sentence for searching relevant passages: "


@lru_cache
def _model() -> SentenceTransformer:
    model = SentenceTransformer(get_settings().embedding_model_name)
    # Explicit, not strictly required (SentenceTransformer models load in eval mode
    # by default), but stated deliberately: eval mode removes training-time behavior
    # such as dropout, giving stable, repeatable output under our current environment
    # and configuration. Not a claim of bitwise-identical results across all
    # hardware/backends.
    model.eval()
    return model


def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []

    for i, text in enumerate(texts):
        if not text or not text.strip():
            raise ValueError(f"embed_texts: input at index {i} is empty or whitespace-only")

    settings = get_settings()
    embeddings = _model().encode(
        texts,
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=False,
    )

    if embeddings.shape[1] != settings.embedding_dimension:
        raise ValueError(
            f"embed_texts: model produced {embeddings.shape[1]}-dim vectors, "
            f"expected {settings.embedding_dimension} per configured settings"
        )

    return embeddings.tolist()


def embed_query(query: str) -> list[float]:
    """Embed a single search query, not a passage/chunk.

    Kept separate from embed_texts deliberately, not just a thin wrapper around it:
    the query side of BGE's asymmetric retrieval convention applies an instruction
    prefix that must never be applied to passage embeddings, and passage embeddings
    must never skip it either, so the two call sites need to stay visibly distinct in
    the codebase, not merged into one function with a boolean flag that's easy to
    pass incorrectly.
    """
    if not query or not query.strip():
        raise ValueError("embed_query: query is empty or whitespace-only")

    prefixed = f"{QUERY_INSTRUCTION_PREFIX}{query}"
    return embed_texts([prefixed])[0]
