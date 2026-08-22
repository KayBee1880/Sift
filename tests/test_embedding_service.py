import math

import pytest

from app.config import get_settings
from app.embedding.service import embed_texts


def _l2_norm(vector: list[float]) -> float:
    return math.sqrt(sum(x * x for x in vector))


def test_empty_input_returns_empty_list():
    assert embed_texts([]) == []


def test_single_text_returns_one_vector_of_expected_dimension():
    vectors = embed_texts(["Payments Service\nSection: Overview\n\nHandles charges."])
    assert len(vectors) == 1
    assert len(vectors[0]) == get_settings().embedding_dimension


def test_multiple_texts_returns_correct_count_and_dimension():
    texts = [
        "Payments Service\nSection: Overview\n\nHandles charges.",
        "Checkout Service\nSection: Overview\n\nOrchestrates purchases.",
        "Authentication Service\nSection: Overview\n\nIssues sessions.",
    ]
    vectors = embed_texts(texts)
    assert len(vectors) == len(texts)
    assert all(len(v) == get_settings().embedding_dimension for v in vectors)


def test_vectors_are_unit_normalized():
    vectors = embed_texts(["Some representative chunk text about a payments incident."])
    norm = _l2_norm(vectors[0])
    assert norm == pytest.approx(1.0, abs=1e-4)


def test_embedding_is_deterministic_for_the_same_input():
    text = "Notifications Service\nSection: Overview\n\nSends email and SMS."
    first = embed_texts([text])[0]
    second = embed_texts([text])[0]
    assert first == pytest.approx(second, abs=1e-6)


def test_empty_string_in_input_raises_value_error():
    with pytest.raises(ValueError, match="empty or whitespace-only"):
        embed_texts(["a valid chunk", ""])


def test_whitespace_only_string_in_input_raises_value_error():
    with pytest.raises(ValueError, match="empty or whitespace-only"):
        embed_texts(["   \n\t  "])
