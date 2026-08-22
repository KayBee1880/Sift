from functools import lru_cache

from sentence_transformers import SentenceTransformer

from app.config import get_settings


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
