"""
Tests for the agent orchestrator and /agent/* endpoints.

Firebase is already mocked at sys.modules level by conftest.py.
These tests additionally patch database functions and call_llm to avoid
any real I/O.
"""
import json
import uuid
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest
from fastapi.testclient import TestClient


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
