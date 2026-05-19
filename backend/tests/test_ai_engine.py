import json
from unittest.mock import MagicMock, patch

import pytest

from ai_engine import (
    TREKKU_CITIES,
    build_itinerary_system_prompt,
    extract_params_from_message,
    generate_itinerary,
    parse_itinerary_json,
    rag_query,
)


# ── call_llm helpers ─────────────────────────────────────────────────────────

def _mock_llm(return_value: str):
    """Return a patch context manager that makes call_llm return return_value."""
    return patch("ai_engine.call_llm", return_value=return_value)


# ── extract_params_from_message ───────────────────────────────────────────────

def test_extract_params_returns_known_city():
    payload = json.dumps({"city": "Kuala Lumpur", "budget": 2000, "days": 3,
                           "origin_state": None, "travel_date": None, "travelers": 1})
    with _mock_llm(payload):
        result = extract_params_from_message("3 days KL budget 2000", {})
    assert result["city"] == "Kuala Lumpur"
    assert result["budget"] == 2000
    assert result["days"] == 3


def test_extract_params_normalises_kl_abbreviation():
    payload = json.dumps({"city": "Kuala Lumpur", "budget": None, "days": None,
                           "origin_state": None, "travel_date": None, "travelers": 1})
    with _mock_llm(payload):
        result = extract_params_from_message("I want to visit KL", {})
    assert result["city"] == "Kuala Lumpur"


def test_extract_params_rejects_invalid_city():
    payload = json.dumps({"city": "Johor Bahru", "budget": None, "days": None,
                           "origin_state": None, "travel_date": None, "travelers": 1})
    with _mock_llm(payload):
        result = extract_params_from_message("take me to Johor", {})
    assert result["city"] is None


def test_extract_params_preserves_existing_values():
    existing = {"city": "Klang", "budget": 1500, "days": None,
                "origin_state": None, "travel_date": None, "travelers": 1}
    payload = json.dumps({"city": None, "budget": None, "days": 4,
                           "origin_state": None, "travel_date": None, "travelers": 1})
    with _mock_llm(payload):
        result = extract_params_from_message("4 days", existing)
    assert result["city"] == "Klang"
    assert result["budget"] == 1500
    assert result["days"] == 4


def test_extract_params_handles_malformed_llm_json():
    with _mock_llm("This is not JSON at all."):
        existing = {"city": "Sepang", "budget": 500, "days": 2,
                    "origin_state": None, "travel_date": None, "travelers": 1}
        result = extract_params_from_message("whatever", existing)
    assert result == existing


def test_extract_params_handles_json_in_code_fence():
    payload = "```json\n" + json.dumps({"city": "KLCC", "budget": 800, "days": 2,
                                         "origin_state": "Penang", "travel_date": None,
                                         "travelers": 1}) + "\n```"
    with _mock_llm(payload):
        result = extract_params_from_message("trip to KLCC from Penang", {})
    assert result["city"] == "KLCC"
    assert result["origin_state"] == "Penang"


# ── build_itinerary_system_prompt ─────────────────────────────────────────────

def test_build_itinerary_system_prompt_contains_city_and_budget():
    prompt = build_itinerary_system_prompt(
        {"city": "Shah Alam", "budget": 1000, "days": 2, "origin_state": None},
        '{"hotels": [], "attractions": [], "flights": []}',
        "",
    )
    assert "Shah Alam" in prompt
    assert "1000" in prompt
    assert "2" in prompt


def test_build_itinerary_system_prompt_contains_kb_context():
    kb = '{"hotels": [{"name": "Test Hotel"}]}'
    prompt = build_itinerary_system_prompt(
        {"city": "Klang", "budget": 500, "days": 1, "origin_state": None},
        kb,
        "",
    )
    assert "Test Hotel" in prompt


def test_build_itinerary_system_prompt_includes_origin():
    prompt = build_itinerary_system_prompt(
        {"city": "Puchong", "budget": 2000, "days": 3, "origin_state": "Penang"},
        "{}",
        "",
    )
    assert "Penang" in prompt


def test_build_itinerary_system_prompt_includes_feedback_notes():
    prompt = build_itinerary_system_prompt(
        {"city": "Sepang", "budget": 1500, "days": 2, "origin_state": None},
        "{}",
        "Hotel X is highly rated.",
    )
    assert "Hotel X is highly rated." in prompt


# ── parse_itinerary_json ──────────────────────────────────────────────────────

def test_parse_itinerary_json_plain_json():
    raw = '{"days": [], "flight": null, "total_estimated_cost": 0}'
    result = parse_itinerary_json(raw)
    assert result["days"] == []
    assert result["total_estimated_cost"] == 0


def test_parse_itinerary_json_strips_code_fences():
    raw = "```json\n{\"days\": [{\"day\": 1}], \"flight\": null, \"total_estimated_cost\": 100}\n```"
    result = parse_itinerary_json(raw)
    assert result["days"][0]["day"] == 1


def test_parse_itinerary_json_raises_on_no_json():
    with pytest.raises(ValueError):
        parse_itinerary_json("No JSON here at all.")


# ── generate_itinerary (backward compat) ──────────────────────────────────────

def test_generate_itinerary_returns_list():
    payload = '[{"day": 1, "activities": ["Sightseeing"], "notes": ""}]'
    with _mock_llm(payload):
        result = generate_itinerary("Kuala Lumpur", 1000, 1)
    assert isinstance(result, list)


def test_generate_itinerary_returns_empty_list_on_bad_json():
    with _mock_llm("not parseable"):
        result = generate_itinerary("Klang", 500, 2)
    assert result == []


# ── rag_query ─────────────────────────────────────────────────────────────────

def test_rag_query_returns_string():
    with _mock_llm("Here are the best hotels."):
        result = rag_query("best hotels in KL", [{"name": "Hotel A"}])
    assert isinstance(result, str)
    assert len(result) > 0


# ── TREKKU_CITIES sanity check ────────────────────────────────────────────────

def test_trekku_cities_contains_expected_entries():
    assert "Kuala Lumpur" in TREKKU_CITIES
    assert "Bukit Bintang" in TREKKU_CITIES
    assert len(TREKKU_CITIES) == 9
