import pytest
from ai_engine import generate_itinerary, rag_query


def test_generate_itinerary_stub():
    result = generate_itinerary("Paris", 1000.0, 3)
    assert result is None


def test_rag_query_stub():
    result = rag_query("best food in Tokyo", [])
    assert result is None
