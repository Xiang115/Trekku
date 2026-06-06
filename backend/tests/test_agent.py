"""
Tests for the agent orchestrator and /agent/* endpoints.

Firebase is already mocked at sys.modules level by conftest.py.
These tests additionally patch database functions and call_llm to avoid
any real I/O.
"""
import json
import uuid
from unittest.mock import AsyncMock, MagicMock, call, patch

import httpx
import pytest
from fastapi.testclient import TestClient
from openai import APIStatusError, BadRequestError


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def client():
    from main import app
    return TestClient(app)


def _make_session(session_id: str = None, city=None, budget=None, days=None) -> dict:
    sid = session_id or str(uuid.uuid4())
    return {
        "session_id": sid,
        "created_at": "2026-01-01T00:00:00+00:00",
        "updated_at": "2026-01-01T00:00:00+00:00",
        "trip_params": {
            "origin_state": None, "city": city, "budget": budget,
            "days": days, "travel_date": None, "travelers": 1,
        },
        "conversation": [],
        "last_itinerary_id": None,
        "status": "active",
    }


def _make_itinerary(itinerary_id: str = None, session_id: str = None) -> dict:
    return {
        "itinerary_id": itinerary_id or str(uuid.uuid4()),
        "session_id": session_id or str(uuid.uuid4()),
        "created_at": "2026-01-01T00:00:00+00:00",
        "city": "Kuala Lumpur",
        "days": 3,
        "budget": 2000.0,
        "travel_date": None,
        "content": {
            "days": [
                {
                    "day": 1,
                    "hotel": {"hotel_id": "hotel_abc", "name": "Hotel A", "price_per_night": 150},
                    "attractions": [{"attraction_id": "attr_abc", "name": "KLCC Park", "estimated_duration": "2h"}],
                    "notes": "Enjoy the park",
                }
            ],
            "flight": {"flight_id": "flight_abc", "airline": "AirAsia", "flight_number": "AK123", "price": 180},
            "total_estimated_cost": 1830.0,
        },
        "raw_llm_response": "",
        "kb_context_snapshot": "{}",
    }


# ── POST /agent/chat – session creation ───────────────────────────────────────

def test_chat_creates_session_on_first_call(client):
    """A null session_id triggers session creation; response carries a valid UUID."""
    with (
        patch("agent.set_record") as mock_set,
        patch("agent.get_record", return_value=None),
        patch("agent.query_records", return_value=[]),
        patch("agent.extract_params_from_message", return_value={
            "city": None, "budget": None, "days": None,
            "origin_state": None, "travel_date": None, "travelers": 1,
        }),
        patch("agent._run_tool_loop", new_callable=AsyncMock,
              return_value=("Hi! I'm Trekku, your travel assistant. Where would you like to go?", None, {})),
    ):
        resp = client.post("/agent/chat", json={"session_id": None, "message": "Hi"})

    assert resp.status_code == 200
    data = resp.json()
    assert "session_id" in data
    assert isinstance(data["session_id"], str)
    assert len(data["session_id"]) == 36  # UUID format
    assert isinstance(data["reply"], str)
    assert len(data["reply"]) > 0
    mock_set.assert_called()


def test_chat_continues_existing_session(client):
    """Providing an existing session_id continues the conversation."""
    existing_session = _make_session(city="Klang", budget=1000)
    sid = existing_session["session_id"]

    with (
        patch("agent.get_record", side_effect=lambda col, doc_id: existing_session if col == "agent_sessions" else None),
        patch("agent.set_record"),
        patch("agent.query_records", return_value=[]),
        patch("agent.extract_params_from_message", return_value={
            "city": "Klang", "budget": 1000, "days": 2,
            "origin_state": None, "travel_date": None, "travelers": 1,
        }),
        patch("agent._run_tool_loop", new_callable=AsyncMock,
              return_value=("Here's your 2-day itinerary for Klang!", None, {
                  "city": "Klang", "days": 2, "budget": 1000, "travel_date": None,
              })),
    ):
        resp = client.post("/agent/chat", json={"session_id": sid, "message": "2 days"})

    assert resp.status_code == 200
    data = resp.json()
    assert data["session_id"] == sid
    assert data["params_collected"]["days"] == 2


# ── City validation ───────────────────────────────────────────────────────────

def test_chat_rejects_out_of_scope_city(client):
    """When extracted city is not in TREKKU_CITIES, the reply guides the user."""
    with (
        patch("agent.set_record"),
        patch("agent.get_record", return_value=None),
        patch("agent.query_records", return_value=[]),
        patch("agent.extract_params_from_message", return_value={
            "city": None, "budget": None, "days": None,
            "origin_state": None, "travel_date": None, "travelers": 1,
        }),
        patch("agent._run_tool_loop", new_callable=AsyncMock,
              return_value=("Johor Bahru is not supported. Please choose a city in Selangor or KL.", None, {})),
    ):
        resp = client.post("/agent/chat", json={"session_id": None, "message": "I want to go to JB"})

    assert resp.status_code == 200
    data = resp.json()
    assert data["itinerary_id"] is None
    assert data["params_collected"]["city"] is None


# ── Full itinerary generation ─────────────────────────────────────────────────

def test_full_itinerary_generation_on_complete_params(client):
    """When city, budget, and days are all present, an itinerary is generated."""
    import agent as _agent

    existing_session = _make_session(city="Kuala Lumpur", budget=2000, days=3)

    itinerary_content = {
        "days": [
            {"day": 1, "hotel": {"hotel_id": "h1", "name": "Grand Hotel", "price_per_night": 200},
             "attractions": [{"attraction_id": "a1", "name": "KLCC", "estimated_duration": "3h"}],
             "notes": ""},
        ],
        "flight": None,
        "total_estimated_cost": 1800.0,
    }
    itinerary_json_str = json.dumps(itinerary_content)

    store = {}

    def mock_set_record(col, doc_id, data):
        store[(col, doc_id)] = data

    def mock_get_record(col, doc_id):
        if col == "agent_sessions":
            return existing_session
        return store.get((col, doc_id))

    async def mock_tool_loop(messages):
        result_str = _agent.save_itinerary(
            city="Kuala Lumpur", days=3, budget=2000.0,
            itinerary_json=itinerary_json_str,
        )
        itin_id = json.loads(result_str)["itinerary_id"]
        return "Here's your itinerary!", itin_id, {
            "city": "Kuala Lumpur", "days": 3, "budget": 2000, "travel_date": None,
        }

    with (
        patch("agent.get_record", side_effect=mock_get_record),
        patch("agent.set_record", side_effect=mock_set_record) as mock_set,
        patch("agent.query_records", return_value=[]),
        patch("agent.extract_params_from_message", return_value={
            "city": "Kuala Lumpur", "budget": 2000, "days": 3,
            "origin_state": None, "travel_date": None, "travelers": 1,
        }),
        patch("agent._run_tool_loop", mock_tool_loop),
    ):
        resp = client.post("/agent/chat", json={"session_id": existing_session["session_id"], "message": "go"})

    assert resp.status_code == 200
    data = resp.json()
    assert data["itinerary_id"] is not None
    assert data["itinerary"] is not None
    assert len(data["itinerary"]["days"]) == 1

    stored_collections = [c[0][0] for c in mock_set.call_args_list]
    assert "generated_itineraries" in stored_collections


# ── apply_feedback_reranking ──────────────────────────────────────────────────

def test_apply_feedback_reranking_adjusts_order():
    """Hotel with positive feedback score should rank above one with negative feedback."""
    from agent import apply_feedback_reranking

    hotel_a = {"hotel_id": "hotel_good", "name": "Good Hotel", "rating": 3.0}
    hotel_b = {"hotel_id": "hotel_bad", "name": "Bad Hotel", "rating": 4.0}

    def mock_query(collection, field, operator, value):
        if value == "hotel_good":
            return [{"signal": 1.0}, {"signal": 1.0}, {"signal": 0.8}]
        if value == "hotel_bad":
            return [{"signal": -1.0}, {"signal": -0.8}]
        return []

    with patch("agent.query_records", side_effect=mock_query):
        ranked = apply_feedback_reranking([hotel_b, hotel_a], "hotels")

    # hotel_a starts with base 0.6 + feedback boost; hotel_b base 0.8 but penalised
    assert ranked[0]["hotel_id"] == "hotel_good"


def test_apply_feedback_reranking_returns_empty_on_empty_input():
    from agent import apply_feedback_reranking
    assert apply_feedback_reranking([], "hotels") == []


def test_apply_feedback_reranking_no_feedback_uses_base_score():
    from agent import apply_feedback_reranking

    hotels = [
        {"hotel_id": "h1", "name": "A", "rating": 4.5},
        {"hotel_id": "h2", "name": "B", "rating": 2.0},
    ]
    with patch("agent.query_records", return_value=[]):
        ranked = apply_feedback_reranking(hotels, "hotels")
    assert ranked[0]["hotel_id"] == "h1"


# ── Search tools cap their result counts (keeps requests under Groq's TPM limit) ─

def test_search_hotels_caps_result_count():
    """Only the top-ranked hotels are returned so the agent request stays small."""
    import agent as _agent

    many = [{"hotel_id": f"h{i}", "name": f"Hotel {i}",
             "price_per_night": {"min": 100, "max": 200}, "rating": 4.0} for i in range(40)]
    with (
        patch("agent.query_records", return_value=many),
        patch("agent.apply_feedback_reranking", side_effect=lambda recs, _t: recs),
    ):
        result = json.loads(_agent.search_hotels("Kuala Lumpur"))
    assert len(result) == _agent._SEARCH_RESULT_CAP["hotels"]
    assert len(result) < len(many)


def test_search_attractions_caps_result_count():
    import agent as _agent

    many = [{"attraction_id": f"a{i}", "name": f"Attraction {i}"} for i in range(40)]
    with (
        patch("agent.query_records", return_value=many),
        patch("agent.apply_feedback_reranking", side_effect=lambda recs, _t: recs),
    ):
        result = json.loads(_agent.search_attractions("Kuala Lumpur"))
    assert len(result) == _agent._SEARCH_RESULT_CAP["attractions"]


# ── GET /agent/session ────────────────────────────────────────────────────────

def test_get_session_returns_404_for_unknown(client):
    with patch("agent.get_record", return_value=None):
        resp = client.get("/agent/session/nonexistent-uuid")
    assert resp.status_code == 404


def test_get_session_returns_session_doc(client):
    session = _make_session()
    with patch("agent.get_record", return_value=session):
        resp = client.get(f"/agent/session/{session['session_id']}")
    assert resp.status_code == 200
    assert resp.json()["session_id"] == session["session_id"]


# ── POST /agent/feedback ──────────────────────────────────────────────────────

def test_feedback_stores_tacit_record_with_correct_signal(client):
    itin = _make_itinerary()
    with (
        patch("routers.agent.get_record", return_value=itin),
        patch("routers.agent.set_record") as mock_set,
    ):
        resp = client.post("/agent/feedback", json={
            "itinerary_id": itin["itinerary_id"],
            "entity_id": "hotel_abc",
            "entity_type": "hotels",
            "rating": 5,
            "signal": 0.0,
        })

    assert resp.status_code == 200
    assert "feedback_id" in resp.json()

    stored_data = mock_set.call_args[0][2]
    assert stored_data["signal"] == 1.0   # (5 - 3) / 2
    assert stored_data["entity_id"] == "hotel_abc"


def test_feedback_returns_404_for_unknown_itinerary(client):
    with patch("routers.agent.get_record", return_value=None):
        resp = client.post("/agent/feedback", json={
            "itinerary_id": "nonexistent",
            "signal": 0.5,
        })
    assert resp.status_code == 404


# ── POST /agent/modify ────────────────────────────────────────────────────────

def test_modify_stores_two_feedback_records(client):
    itin = _make_itinerary()
    stored = []

    def capture_set(collection, doc_id, data):
        stored.append(data)

    with (
        patch("routers.agent.get_record", return_value=itin),
        patch("routers.agent.set_record", side_effect=capture_set),
    ):
        resp = client.post("/agent/modify", json={
            "itinerary_id": itin["itinerary_id"],
            "original_entity_id": "hotel_old",
            "replacement_entity_id": "hotel_new",
            "entity_type": "hotels",
        })

    assert resp.status_code == 200
    assert len(resp.json()["feedback_ids"]) == 2
    assert len(stored) == 2

    signals = sorted(r["signal"] for r in stored)
    assert signals == [-0.8, 0.8]

    entity_ids = {r["entity_id"] for r in stored}
    assert entity_ids == {"hotel_old", "hotel_new"}


def test_modify_returns_404_for_unknown_itinerary(client):
    with patch("routers.agent.get_record", return_value=None):
        resp = client.post("/agent/modify", json={
            "itinerary_id": "bad",
            "original_entity_id": "x",
            "replacement_entity_id": "y",
            "entity_type": "hotels",
        })
    assert resp.status_code == 404


# ── GET /agent/itinerary ──────────────────────────────────────────────────────

def test_get_itinerary_returns_stored_content(client):
    itin = _make_itinerary()
    with patch("routers.agent.get_record", return_value=itin):
        resp = client.get(f"/agent/itinerary/{itin['itinerary_id']}")
    assert resp.status_code == 200
    assert resp.json()["city"] == "Kuala Lumpur"


def test_get_itinerary_returns_404_for_unknown(client):
    with patch("routers.agent.get_record", return_value=None):
        resp = client.get("/agent/itinerary/missing-id")
    assert resp.status_code == 404


# ── Retry on Groq rate-limit / request-too-large ──────────────────────────────

def _api_status_error(status_code: int) -> APIStatusError:
    """Build a real openai.APIStatusError with the given HTTP status code."""
    request = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
    response = httpx.Response(status_code, request=request)
    return APIStatusError("rate limit exceeded", response=response, body=None)


def test_create_completion_retries_then_succeeds():
    """A transient 429 should be retried with backoff and then succeed."""
    import asyncio
    import agent as _agent

    sentinel_response = object()
    client = MagicMock()
    client.chat.completions.create = AsyncMock(
        side_effect=[_api_status_error(429), sentinel_response]
    )

    with patch("agent.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        result = asyncio.run(_agent._create_completion(client, model="m", messages=[]))

    assert result is sentinel_response
    assert client.chat.completions.create.await_count == 2
    mock_sleep.assert_awaited_once()


def test_create_completion_retries_on_413():
    """The observed 413 (TPM request too large) is treated as retryable."""
    import asyncio
    import agent as _agent

    sentinel_response = object()
    client = MagicMock()
    client.chat.completions.create = AsyncMock(
        side_effect=[_api_status_error(413), sentinel_response]
    )

    with patch("agent.asyncio.sleep", new_callable=AsyncMock):
        result = asyncio.run(_agent._create_completion(client, model="m", messages=[]))

    assert result is sentinel_response
    assert client.chat.completions.create.await_count == 2


def test_create_completion_reraises_after_max_retries():
    """When the rate limit never clears, the error is re-raised after max attempts."""
    import asyncio
    import agent as _agent

    client = MagicMock()
    client.chat.completions.create = AsyncMock(side_effect=_api_status_error(429))

    with patch("agent.asyncio.sleep", new_callable=AsyncMock):
        with pytest.raises(APIStatusError):
            asyncio.run(_agent._create_completion(client, model="m", messages=[]))

    assert client.chat.completions.create.await_count == _agent._MAX_LLM_RETRIES


def test_create_completion_does_not_retry_non_retryable_status():
    """A non rate-limit error (e.g. 500) is raised immediately without retry."""
    import asyncio
    import agent as _agent

    client = MagicMock()
    client.chat.completions.create = AsyncMock(side_effect=_api_status_error(500))

    with patch("agent.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        with pytest.raises(APIStatusError):
            asyncio.run(_agent._create_completion(client, model="m", messages=[]))

    assert client.chat.completions.create.await_count == 1
    mock_sleep.assert_not_awaited()


# ── Tool-result truncation (payload reduction) ────────────────────────────────

def test_truncate_tool_result_caps_long_payload():
    from agent import _truncate_tool_result, _TOOL_RESULT_CHAR_LIMIT

    long_result = "x" * (_TOOL_RESULT_CHAR_LIMIT + 500)
    truncated = _truncate_tool_result(long_result)

    assert len(truncated) <= _TOOL_RESULT_CHAR_LIMIT + len("\n...[truncated]")
    assert truncated.endswith("[truncated]")


def test_truncate_tool_result_leaves_short_payload_unchanged():
    from agent import _truncate_tool_result

    short_result = json.dumps({"status": "ok"})
    assert _truncate_tool_result(short_result) == short_result


# ── Hotel price representation ─────────────────────────────────────────────────

def test_compact_hotel_uses_midpoint_and_exposes_range():
    """A {min, max} price range must surface as a realistic midpoint plus both bounds,
    not be collapsed to the misleading minimum."""
    from agent import _compact_hotel

    hotel = {
        "hotel_id": "h1", "name": "Range Hotel",
        "price_per_night": {"min": 50, "max": 250},
        "rating": 4.0, "category": "mid-range", "amenities": [],
    }
    compact = _compact_hotel(hotel)

    assert compact["price_per_night_min"] == 50
    assert compact["price_per_night_max"] == 250
    assert compact["price_per_night"] == 150   # midpoint, not the 50 floor


def test_compact_hotel_handles_flat_numeric_price():
    """A hotel whose price is already a flat number should pass through unchanged."""
    from agent import _compact_hotel

    hotel = {"hotel_id": "h2", "name": "Flat", "price_per_night": 120}
    compact = _compact_hotel(hotel)

    assert compact["price_per_night"] == 120
    assert compact["price_per_night_min"] == 120
    assert compact["price_per_night_max"] == 120


# ── Deterministic total cost calculation ──────────────────────────────────────

def test_calculate_total_cost_sums_line_items():
    """Total is the sum of each listed night's hotel plus the flight price."""
    from agent import _calculate_total_cost

    content = {
        "days": [
            {"day": 1, "hotel": {"hotel_id": "h1", "name": "A", "price_per_night": 150}, "attractions": []},
            {"day": 2, "hotel": {"hotel_id": "h1", "name": "A", "price_per_night": 150}, "attractions": []},
        ],
        "flight": {"flight_id": "f1", "price": 180},
        "total_estimated_cost": 9999.0,   # bogus model figure, must be ignored
    }
    assert _calculate_total_cost(content) == 480.0   # 150 + 150 + 180


def test_calculate_total_cost_handles_missing_and_null_prices():
    """Missing hotel price, null flight, and absent fields contribute zero, not errors."""
    from agent import _calculate_total_cost

    content = {"days": [{"day": 1, "hotel": {}, "attractions": []}], "flight": None}
    assert _calculate_total_cost(content) == 0.0


def test_calculate_total_cost_includes_attraction_prices_when_present():
    """If attraction price data ever exists, it is counted toward the total."""
    from agent import _calculate_total_cost

    content = {
        "days": [
            {"day": 1, "hotel": {"price_per_night": 100},
             "attractions": [{"attraction_id": "a1", "name": "X", "price": 30}]},
        ],
        "flight": None,
    }
    assert _calculate_total_cost(content) == 130.0   # 100 + 30


def test_calculate_total_cost_includes_meals_and_transport_estimates():
    """AI-estimated meals and transport are added to the deterministic line items."""
    from agent import _calculate_total_cost

    content = {
        "days": [
            {"day": 1, "hotel": {"hotel_id": "h1", "price_per_night": 150}, "attractions": []},
        ],
        "flight": {"flight_id": "f1", "price": 180},
        "estimated_meals_cost": 200,
        "estimated_transport_cost": 90,
    }
    assert _calculate_total_cost(content) == 620.0   # 150 + 180 + 200 + 90


def test_calculate_total_cost_treats_missing_estimates_as_zero():
    """Itineraries without meal/transport estimates still total cleanly."""
    from agent import _calculate_total_cost

    content = {
        "days": [{"day": 1, "hotel": {"price_per_night": 100}, "attractions": []}],
        "flight": None,
    }
    assert _calculate_total_cost(content) == 100.0


def test_calculate_total_cost_scales_flight_and_hotel_by_travelers():
    """Flights and hotels are per-person/per-room bookables, so they scale with the
    number of travellers. Meals and transport are already whole-trip estimates the
    model sized for the party, so they are NOT scaled again."""
    from agent import _calculate_total_cost

    content = {
        "days": [
            {"day": 1, "hotel": {"hotel_id": "h1", "price_per_night": 100}, "attractions": []},
        ],
        "flight": {"flight_id": "f1", "price": 180},
        "estimated_meals_cost": 200,
        "estimated_transport_cost": 90,
    }
    # 100*2 (hotel) + 180*2 (flight) + 200 (meals) + 90 (transport)
    assert _calculate_total_cost(content, travelers=2) == 850.0


def test_calculate_total_cost_defaults_to_single_traveler():
    """Omitting travelers prices the trip for one person (no scaling)."""
    from agent import _calculate_total_cost

    content = {
        "days": [{"day": 1, "hotel": {"price_per_night": 100}, "attractions": []}],
        "flight": {"flight_id": "f1", "price": 180},
    }
    assert _calculate_total_cost(content) == 280.0   # 100 + 180


def test_save_itinerary_scales_bookable_costs_by_party_size():
    """save_itinerary reads travellers from the request context and scales the
    bookable line items accordingly when computing the authoritative total."""
    import agent as _agent

    captured = {}

    def capture_set(col, doc_id, data):
        captured["data"] = data

    itinerary = {
        "days": [
            {"day": 1, "hotel": {"hotel_id": "h1", "name": "A", "price_per_night": 100}, "attractions": []},
        ],
        "flight": {"flight_id": "f1", "price": 200},
        "estimated_meals_cost": 0,
        "estimated_transport_cost": 0,
        "total_estimated_cost": 0.0,
    }

    token = _agent._current_trip_params.set({"travelers": 2})
    try:
        # get_record returns None → prices fall back to the values in the itinerary JSON.
        with (
            patch("agent.set_record", side_effect=capture_set),
            patch("agent.get_record", return_value=None),
        ):
            _agent.save_itinerary("Kuala Lumpur", 1, 2000.0, json.dumps(itinerary))
    finally:
        _agent._current_trip_params.reset(token)

    # 100*2 (hotel) + 200*2 (flight)
    assert captured["data"]["content"]["total_estimated_cost"] == 600.0


def test_save_itinerary_overwrites_model_supplied_total():
    """save_itinerary must store the computed total, never the model's hallucinated one."""
    import agent as _agent

    captured = {}

    def capture_set(col, doc_id, data):
        captured["data"] = data

    itinerary = {
        "days": [
            {"day": 1, "hotel": {"hotel_id": "h1", "name": "A", "price_per_night": 100}, "attractions": []},
            {"day": 2, "hotel": {"hotel_id": "h1", "name": "A", "price_per_night": 100}, "attractions": []},
        ],
        "flight": {"flight_id": "f1", "price": 200},
        "total_estimated_cost": 9999.0,   # bogus
    }

    # get_record returns None → prices fall back to the values in the itinerary JSON.
    with (
        patch("agent.set_record", side_effect=capture_set),
        patch("agent.get_record", return_value=None),
    ):
        _agent.save_itinerary("Kuala Lumpur", 3, 2000.0, json.dumps(itinerary))

    stored_total = captured["data"]["content"]["total_estimated_cost"]
    assert stored_total == 400.0   # 100 + 100 + 200, not 9999


def test_save_itinerary_resolves_hotel_price_from_db():
    """A model-emitted nightly price must be overwritten with the authoritative DB rate
    (midpoint of the stored {min, max} range), regardless of what the model wrote."""
    import agent as _agent

    captured = {}

    def capture_set(col, doc_id, data):
        captured["data"] = data

    def fake_get_record(col, doc_id):
        if col == "hotels" and doc_id == "h1":
            return {"hotel_id": "h1", "name": "Real Hotel",
                    "price_per_night": {"min": 100, "max": 300, "currency": "MYR"}}
        return None

    itinerary = {
        "days": [
            {"day": 1, "hotel": {"hotel_id": "h1", "name": "Real Hotel", "price_per_night": 25}, "attractions": []},
        ],
        "flight": None,
        "total_estimated_cost": 0.0,
    }

    with (
        patch("agent.set_record", side_effect=capture_set),
        patch("agent.get_record", side_effect=fake_get_record),
    ):
        _agent.save_itinerary("Kuala Lumpur", 1, 2000.0, json.dumps(itinerary))

    stored_hotel = captured["data"]["content"]["days"][0]["hotel"]
    assert stored_hotel["price_per_night"] == 200   # midpoint of 100–300, not the model's 25
    assert captured["data"]["content"]["total_estimated_cost"] == 200.0


def test_save_itinerary_resolves_flight_price_from_db():
    """The flight price must come from the DB record, not the model's number."""
    import agent as _agent

    captured = {}

    def capture_set(col, doc_id, data):
        captured["data"] = data

    def fake_get_record(col, doc_id):
        if col == "flights" and doc_id == "f1":
            return {"flight_id": "f1", "price": 320}
        return None

    itinerary = {
        "days": [{"day": 1, "hotel": {}, "attractions": []}],
        "flight": {"flight_id": "f1", "airline": "AirAsia", "price": 5},
        "total_estimated_cost": 0.0,
    }

    with (
        patch("agent.set_record", side_effect=capture_set),
        patch("agent.get_record", side_effect=fake_get_record),
    ):
        _agent.save_itinerary("Kuala Lumpur", 1, 2000.0, json.dumps(itinerary))

    assert captured["data"]["content"]["flight"]["price"] == 320
    assert captured["data"]["content"]["total_estimated_cost"] == 320.0


def test_save_itinerary_returns_computed_total_to_caller():
    """The tool result must carry the computed total so the model can quote it in its reply."""
    import agent as _agent

    itinerary = {
        "days": [{"day": 1, "hotel": {"hotel_id": "h1", "price_per_night": 150}, "attractions": []}],
        "flight": None,
        "total_estimated_cost": 0.0,
    }

    with (
        patch("agent.set_record"),
        patch("agent.get_record", return_value=None),
    ):
        result = _agent.save_itinerary("Kuala Lumpur", 1, 2000.0, json.dumps(itinerary))

    payload = json.loads(result)
    assert payload["total_estimated_cost"] == 150.0
    assert payload["currency"] == "MYR"


# ── Graceful JSON parse failure ───────────────────────────────────────────────

def test_groq_json_parse_failure_returns_plain_text_not_500(client):
    """When LLM returns unparseable JSON, the agent should NOT raise a 500."""
    import agent as _agent

    existing_session = _make_session(city="Petaling Jaya", budget=1500, days=2)
    bad_itinerary = "Sorry, I cannot generate that right now."

    store = {}

    def mock_set_record(col, doc_id, data):
        store[(col, doc_id)] = data

    def mock_get_record(col, doc_id):
        if col == "agent_sessions":
            return existing_session
        return store.get((col, doc_id))

    async def mock_tool_loop(messages):
        # Simulate model calling save_itinerary with unparseable JSON
        result_str = _agent.save_itinerary(
            city="Petaling Jaya", days=2, budget=1500.0,
            itinerary_json=bad_itinerary,
        )
        itin_id = json.loads(result_str)["itinerary_id"]
        return bad_itinerary, itin_id, {
            "city": "Petaling Jaya", "days": 2, "budget": 1500, "travel_date": None,
        }

    with (
        patch("agent.get_record", side_effect=mock_get_record),
        patch("agent.set_record", side_effect=mock_set_record),
        patch("agent.query_records", return_value=[]),
        patch("agent.extract_params_from_message", return_value={
            "city": "Petaling Jaya", "budget": 1500, "days": 2,
            "origin_state": None, "travel_date": None, "travelers": 1,
        }),
        patch("agent._run_tool_loop", mock_tool_loop),
    ):
        resp = client.post("/agent/chat", json={
            "session_id": existing_session["session_id"],
            "message": "go ahead",
        })

    assert resp.status_code == 200
    data = resp.json()
    assert data["itinerary_id"] is not None   # itinerary doc was stored despite bad JSON
    assert isinstance(data["reply"], str)


# ── Required-param gate: collect info before planning ─────────────────────────

def _tool_call_response(name: str, arguments: str) -> MagicMock:
    """Build a fake Groq completion whose single choice is a tool call."""
    tc = MagicMock()
    tc.id = "call_1"
    tc.function.name = name
    tc.function.arguments = arguments
    choice = MagicMock()
    choice.finish_reason = "tool_calls"
    choice.message.content = None
    choice.message.tool_calls = [tc]
    response = MagicMock()
    response.choices = [choice]
    return response


def _text_response(text: str) -> MagicMock:
    """Build a fake Groq completion whose single choice is a plain text reply."""
    choice = MagicMock()
    choice.finish_reason = "stop"
    choice.message.content = text
    choice.message.tool_calls = None
    response = MagicMock()
    response.choices = [choice]
    return response


def test_missing_required_lists_absent_fields():
    from agent import _missing_required

    assert _missing_required({}) == ["city", "budget", "days"]
    assert _missing_required({"city": "Kuala Lumpur"}) == ["budget", "days"]
    assert _missing_required({"city": "Kuala Lumpur", "budget": 2000, "days": 3}) == []
    # A falsy zero budget still counts as missing.
    assert "budget" in _missing_required({"city": "Kuala Lumpur", "budget": 0, "days": 3})


def test_collected_state_block_lists_missing_and_rule():
    from agent import _render_collected_state

    block = _render_collected_state({"city": "Kuala Lumpur", "budget": None, "days": None})
    assert "Kuala Lumpur" in block
    assert "budget" in block and "days" in block
    assert "MUST NOT" in block   # hard gate rule is present when fields are missing

    complete = _render_collected_state({"city": "Kuala Lumpur", "budget": 2000, "days": 3})
    assert "All required details are collected" in complete


def test_gate_blocks_save_itinerary_when_params_incomplete():
    """With budget/days missing, a save_itinerary tool call is refused and never executed."""
    import asyncio
    import agent as _agent

    client = MagicMock()
    client.chat.completions.create = AsyncMock(side_effect=[
        _tool_call_response("save_itinerary", json.dumps({
            "city": "Kuala Lumpur", "days": 3, "budget": 2000, "itinerary_json": "{}",
        })),
        _text_response("What's your budget and how many days?"),
    ])

    set_calls = []
    token = _agent._current_trip_params.set({"city": "Kuala Lumpur", "budget": None, "days": None})
    try:
        with (
            patch("agent._get_async_client", return_value=client),
            patch("agent.set_record", side_effect=lambda *a, **k: set_calls.append(a)),
        ):
            messages = [{"role": "system", "content": "sys"}]
            reply, itin_id, saved = asyncio.run(_agent._run_tool_loop(messages))
    finally:
        _agent._current_trip_params.reset(token)

    assert itin_id is None
    assert saved == {}
    # save_itinerary never wrote an itinerary document
    assert not any(call_args and call_args[0] == "generated_itineraries" for call_args in set_calls)
    # the gate's refusal was fed back to the model as a tool result
    tool_msgs = [m for m in messages if m.get("role") == "tool"]
    assert any("missing_required_params" in m["content"] for m in tool_msgs)
    assert reply  # the model still produced a clarifying reply


def test_gate_allows_planning_when_params_complete():
    """With all required params present, the save_itinerary tool runs normally."""
    import asyncio
    import agent as _agent

    itinerary_json = json.dumps({"days": [], "flight": None})
    client = MagicMock()
    client.chat.completions.create = AsyncMock(side_effect=[
        _tool_call_response("save_itinerary", json.dumps({
            "city": "Kuala Lumpur", "days": 3, "budget": 2000, "itinerary_json": itinerary_json,
        })),
        _text_response("Here's your itinerary!"),
    ])

    set_collections = []
    token = _agent._current_trip_params.set({"city": "Kuala Lumpur", "budget": 2000, "days": 3})
    try:
        with (
            patch("agent._get_async_client", return_value=client),
            patch("agent.set_record", side_effect=lambda col, doc_id, data: set_collections.append(col)),
            patch("agent.get_record", return_value=None),
        ):
            messages = [{"role": "system", "content": "sys"}]
            reply, itin_id, saved = asyncio.run(_agent._run_tool_loop(messages))
    finally:
        _agent._current_trip_params.reset(token)

    assert itin_id is not None
    assert "generated_itineraries" in set_collections
    assert saved["city"] == "Kuala Lumpur"
    assert reply == "Here's your itinerary!"


# ── tool_use_failed recovery ──────────────────────────────────────────────────

def _tool_use_failed_error() -> BadRequestError:
    """Build the Groq 400 raised when gpt-oss emits a malformed tool call."""
    req = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
    resp = httpx.Response(400, request=req)
    return BadRequestError(
        "Error code: 400 - tool_use_failed: Failed to call a function.",
        response=resp,
        body={"error": {"code": "tool_use_failed"}},
    )


def test_tool_use_failed_retries_with_tools_and_recovers():
    """A transient `tool_use_failed` must be recovered by RETRYING the same
    tools-enabled request — never by re-calling with tools stripped (which makes
    Groq reject the model's tool call with "tool_choice is none" and crash)."""
    import asyncio
    import agent as _agent

    itinerary_json = json.dumps({"days": [], "flight": None})
    client = MagicMock()
    client.chat.completions.create = AsyncMock(side_effect=[
        _tool_use_failed_error(),  # main call glitches on a malformed tool call
        _tool_call_response("save_itinerary", json.dumps({  # retry recovers
            "city": "Kuala Lumpur", "days": 3, "budget": 2000, "itinerary_json": itinerary_json,
        })),
        _text_response("Here's your itinerary!"),
    ])

    set_collections = []
    token = _agent._current_trip_params.set({"city": "Kuala Lumpur", "budget": 2000, "days": 3})
    try:
        with (
            patch("agent._get_async_client", return_value=client),
            patch("agent.set_record", side_effect=lambda col, doc_id, data: set_collections.append(col)),
            patch("agent.get_record", return_value=None),
        ):
            messages = [{"role": "system", "content": "sys"}]
            reply, itin_id, saved = asyncio.run(_agent._run_tool_loop(messages))
    finally:
        _agent._current_trip_params.reset(token)

    # The loop recovered: itinerary was saved and the final reply came through.
    assert itin_id is not None
    assert "generated_itineraries" in set_collections
    assert reply == "Here's your itinerary!"
    # Every model call kept tools enabled — no tools-stripped fallback that would
    # trip Groq's "tool_choice is none, but model called a tool" rejection.
    for c in client.chat.completions.create.call_args_list:
        assert "tools" in c.kwargs, "a model call was made without tools (broken fallback)"


def test_tool_use_failed_degrades_gracefully_when_never_recovers():
    """If the model keeps emitting malformed tool calls, the loop must exhaust its
    retries and return a graceful message — not raise the 400 to the caller."""
    import asyncio
    import agent as _agent

    client = MagicMock()
    client.chat.completions.create = AsyncMock(side_effect=_tool_use_failed_error())

    token = _agent._current_trip_params.set({"city": "Kuala Lumpur", "budget": 2000, "days": 3})
    try:
        with (
            patch("agent._get_async_client", return_value=client),
            patch("agent.set_record"),
            patch("agent.get_record", return_value=None),
        ):
            messages = [{"role": "system", "content": "sys"}]
            reply, itin_id, saved = asyncio.run(_agent._run_tool_loop(messages))
    finally:
        _agent._current_trip_params.reset(token)

    assert itin_id is None
    assert isinstance(reply, str) and reply  # a non-empty graceful message, no crash


# ── Progress streaming (emit_progress + /agent/chat/stream) ────────────────────

def test_emit_progress_is_noop_without_emitter():
    """emit_progress must be safe (and silent) when no queue is set — this is the
    plain /agent/chat and sync chat() path. It should never raise or do anything."""
    import agent as _agent

    # No _progress_queue set in this context → default None.
    assert _agent._progress_queue.get() is None
    _agent.emit_progress("thinking", step=1)  # must not raise


def _parse_sse(body: str) -> list[tuple[str, dict]]:
    """Parse a raw SSE response body into a list of (event, data-dict) tuples."""
    events = []
    for frame in body.split("\n\n"):
        frame = frame.strip()
        if not frame:
            continue
        event = "message"
        data_lines = []
        for line in frame.split("\n"):
            if line.startswith("event:"):
                event = line[len("event:"):].strip()
            elif line.startswith("data:"):
                data_lines.append(line[len("data:"):].strip())
        events.append((event, json.loads("\n".join(data_lines))))
    return events


def test_chat_stream_emits_status_then_result(client):
    """/agent/chat/stream emits a status frame per emit_progress call, then a
    terminal result frame carrying the full chat_async payload."""
    import agent as _agent

    canned = {
        "session_id": "sess-123",
        "reply": "Here's your trip!",
        "itinerary_id": "itin-123",
        "params_collected": {"city": "Penang"},
        "itinerary": None,
    }

    async def fake_chat_async(session_id, message):
        _agent.emit_progress("understanding")
        _agent.emit_progress("searching_flights", tool="search_flights", detail="PEN", step=2)
        _agent.emit_progress("finalizing", tool="save_itinerary", detail="Penang", step=3)
        return canned

    with patch("agent.chat_async", new=AsyncMock(side_effect=fake_chat_async)):
        resp = client.post("/agent/chat/stream", json={"session_id": None, "message": "Penang trip"})

    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")
    events = _parse_sse(resp.text)

    statuses = [data["stage"] for ev, data in events if ev == "status"]
    assert statuses == ["understanding", "searching_flights", "finalizing"]
    # detail/step are carried through
    flight_evt = next(data for ev, data in events if ev == "status" and data["stage"] == "searching_flights")
    assert flight_evt["detail"] == "PEN" and flight_evt["step"] == 2

    results = [data for ev, data in events if ev == "result"]
    assert len(results) == 1
    assert results[0] == canned


def test_chat_stream_emits_error_frame_on_failure(client):
    """If chat_async raises, the stream emits an error frame and terminates cleanly."""
    with patch("agent.chat_async", new=AsyncMock(side_effect=RuntimeError("boom"))):
        resp = client.post("/agent/chat/stream", json={"session_id": None, "message": "x"})

    assert resp.status_code == 200
    events = _parse_sse(resp.text)
    errors = [data for ev, data in events if ev == "error"]
    assert len(errors) == 1
    assert "boom" in errors[0]["message"]
    assert not any(ev == "result" for ev, _ in events)
