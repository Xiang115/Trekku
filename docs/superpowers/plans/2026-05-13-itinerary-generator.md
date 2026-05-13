# Itinerary Generator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement `generate_itinerary()` in `ai_engine.py` so the Trekku system can produce a structured JSON day-by-day itinerary from Firestore knowledge + Groq LLM generation.

**Architecture:** User input flows through four stages — (1) origin normalisation via Groq classification, (2) three `capture()` calls to pull hotels/attractions/flights from Firestore, (3) document slimming to remove operational metadata before LLM context assembly, (4) Groq structured JSON generation with a plain-text fallback. The REST endpoint in `main.py` is the public entry point.

**Tech Stack:** Python 3.11, FastAPI, Groq SDK (`groq`), Firebase Firestore (`firebase-admin`), Pydantic v2, pytest + unittest.mock

---

## Design Decisions (from group discussion)

These decisions are locked in and must not be revisited during implementation:

| Decision | Agreed Approach |
|---|---|
| Historical data (Jan 2025) | Not achievable — SerpAPI is live/future only. Not implemented. |
| Price history tracking | Out of scope for this prototype. |
| Budget handling | Pass full budget as Groq context — LLM reasons about affordability, no Python-side splitting |
| Origin normalisation | Groq classifies raw user input to exact `_IATA_MAP` key before `capture()` call |
| Document slimming | Strip `ttl_expires`, `last_updated`, `source`, `_ttl_sentinel` before passing to Groq |
| Groq output format | Structured JSON; fallback to `{"raw": "...", ...}` if `json.loads()` fails |
| Firestore indexes | No composite indexes — acceptable at prototype scale (<1,000 docs) |

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `backend/ai_engine.py` | **Modify** | Add `_slim_docs()`, `_normalise_origin()`, implement `generate_itinerary()` |
| `backend/main.py` | **Modify** | Add `ItineraryRequest` model and `POST /itinerary` endpoint |
| `backend/tests/test_ai_engine.py` | **Modify** | Replace stub tests; add tests for all new functions |

---

## Task 1: Document Slimming Helper

**Files:**
- Modify: `backend/ai_engine.py`
- Modify: `backend/tests/test_ai_engine.py`

This is a pure function with no external dependencies — implement and test it first.

- [ ] **Step 1: Replace the stub test file with slimming tests**

Open `backend/tests/test_ai_engine.py` and replace its entire contents with:

```python
import json
import pytest
from unittest.mock import patch, MagicMock


# ─── _slim_docs ───────────────────────────────────────

def test_slim_docs_hotel_keeps_only_required_fields():
    from ai_engine import _slim_docs
    full_doc = {
        "hotel_id": "hotel_abc123",
        "name": "Sunway Hotel",
        "category": "mid-range",
        "price_per_night": {"min": 200, "max": 350, "currency": "MYR"},
        "rating": 4.2,
        "amenities": ["Pool", "WiFi"],
        "location": {"city": "Subang Jaya", "country": "Malaysia"},
        "last_updated": "2026-05-01T00:00:00",
        "ttl_expires": "2026-05-08T00:00:00",
        "source": "serpapi_hotels",
        "_ttl_sentinel": False,
        "data_freshness": "fresh",
    }
    result = _slim_docs([full_doc], "hotels")
    assert len(result) == 1
    assert "name" in result[0]
    assert "category" in result[0]
    assert "price_per_night" in result[0]
    assert "rating" in result[0]
    assert "amenities" in result[0]
    assert "location" in result[0]
    assert "ttl_expires" not in result[0]
    assert "last_updated" not in result[0]
    assert "source" not in result[0]
    assert "_ttl_sentinel" not in result[0]
    assert "hotel_id" not in result[0]


def test_slim_docs_attraction_keeps_only_required_fields():
    from ai_engine import _slim_docs
    full_doc = {
        "attraction_id": "attraction_xyz",
        "name": "Batu Caves",
        "category": "Tourist attraction",
        "popularity_score": 4.6,
        "opening_hours": "Open 24 hours",
        "estimated_duration": None,
        "location": {"city": "Kuala Lumpur", "country": "Malaysia"},
        "last_updated": "2026-04-01T00:00:00",
        "ttl_expires": "2026-06-01T00:00:00",
        "source": "serpapi_attractions",
    }
    result = _slim_docs([full_doc], "attractions")
    assert "name" in result[0]
    assert "category" in result[0]
    assert "popularity_score" in result[0]
    assert "opening_hours" in result[0]
    assert "location" in result[0]
    assert "attraction_id" not in result[0]
    assert "ttl_expires" not in result[0]


def test_slim_docs_flight_keeps_only_required_fields():
    from ai_engine import _slim_docs
    full_doc = {
        "flight_id": "flight_abc",
        "origin_state": "Johor Bahru",
        "origin_iata": "JHB",
        "destination": "Selangor",
        "destination_iata": "KUL",
        "airline": "AirAsia",
        "flight_number": "AK 6121",
        "price": 150.0,
        "duration_minutes": 60,
        "currency": "MYR",
        "last_updated": "2026-05-01T00:00:00",
        "ttl_expires": "2026-05-08T00:00:00",
        "source": "serpapi_flights",
        "data_freshness": "fresh",
    }
    result = _slim_docs([full_doc], "flights")
    assert "airline" in result[0]
    assert "flight_number" in result[0]
    assert "price" in result[0]
    assert "duration_minutes" in result[0]
    assert "origin_state" in result[0]
    assert "flight_id" not in result[0]
    assert "ttl_expires" not in result[0]


def test_slim_docs_empty_list_returns_empty():
    from ai_engine import _slim_docs
    assert _slim_docs([], "hotels") == []
```

- [ ] **Step 2: Run tests to confirm they fail**

```
cd backend
pytest tests/test_ai_engine.py -v
```

Expected: `ImportError` or `AttributeError: module 'ai_engine' has no attribute '_slim_docs'`

- [ ] **Step 3: Implement `_slim_docs()` in `ai_engine.py`**

Replace the entire contents of `backend/ai_engine.py` with:

```python
import json
from groq import Groq
from config import GROQ_API_KEY
from knowledge_capture import capture, _IATA_MAP

_SLIM_FIELDS = {
    "hotels":      ["name", "category", "price_per_night", "rating", "amenities", "location"],
    "attractions": ["name", "category", "popularity_score", "opening_hours", "location"],
    "flights":     ["airline", "flight_number", "price", "duration_minutes", "origin_state", "data_freshness"],
}


def _slim_docs(docs: list, entity_type: str) -> list:
    fields = _SLIM_FIELDS.get(entity_type, [])
    return [{k: v for k, v in doc.items() if k in fields} for doc in docs]


def _normalise_origin(raw_origin: str) -> str | None:
    pass


def generate_itinerary(destination: str, budget: float, days: int, origin: str = None, travel_date: str = None) -> dict:
    pass


def rag_query(query: str, context_docs: list) -> str:
    pass
```

- [ ] **Step 4: Run tests to confirm they pass**

```
cd backend
pytest tests/test_ai_engine.py::test_slim_docs_hotel_keeps_only_required_fields tests/test_ai_engine.py::test_slim_docs_attraction_keeps_only_required_fields tests/test_ai_engine.py::test_slim_docs_flight_keeps_only_required_fields tests/test_ai_engine.py::test_slim_docs_empty_list_returns_empty -v
```

Expected: 4 PASSED

- [ ] **Step 5: Commit**

```bash
git add backend/ai_engine.py backend/tests/test_ai_engine.py
git commit -m "feat: add _slim_docs helper to strip Firestore metadata before LLM context"
```

---

## Task 2: Origin Normalisation Helper

**Files:**
- Modify: `backend/ai_engine.py`
- Modify: `backend/tests/test_ai_engine.py`

`_normalise_origin()` calls Groq with temperature=0 to classify a raw user string ("JB", "johor bahru", "Penang island") to an exact key in `_IATA_MAP`. Returns `None` if no match.

- [ ] **Step 1: Add normalisation tests to `test_ai_engine.py`**

Append these tests to the bottom of `backend/tests/test_ai_engine.py`:

```python
# ─── _normalise_origin ────────────────────────────────

def test_normalise_origin_returns_canonical_state_name():
    from ai_engine import _normalise_origin
    mock_response = MagicMock()
    mock_response.choices[0].message.content = "Johor Bahru"
    with patch("ai_engine.Groq") as MockGroq:
        MockGroq.return_value.chat.completions.create.return_value = mock_response
        result = _normalise_origin("JB")
    assert result == "Johor Bahru"


def test_normalise_origin_returns_none_for_unrecognised_input():
    from ai_engine import _normalise_origin
    mock_response = MagicMock()
    mock_response.choices[0].message.content = "NULL"
    with patch("ai_engine.Groq") as MockGroq:
        MockGroq.return_value.chat.completions.create.return_value = mock_response
        result = _normalise_origin("Singapore")
    assert result is None


def test_normalise_origin_returns_none_when_groq_returns_invalid_state():
    from ai_engine import _normalise_origin
    mock_response = MagicMock()
    mock_response.choices[0].message.content = "Bangkok"
    with patch("ai_engine.Groq") as MockGroq:
        MockGroq.return_value.chat.completions.create.return_value = mock_response
        result = _normalise_origin("Thailand")
    assert result is None
```

- [ ] **Step 2: Run tests to confirm they fail**

```
cd backend
pytest tests/test_ai_engine.py::test_normalise_origin_returns_canonical_state_name -v
```

Expected: FAIL — `_normalise_origin` returns `None` (it's a stub)

- [ ] **Step 3: Implement `_normalise_origin()` in `ai_engine.py`**

Replace the `_normalise_origin` stub in `backend/ai_engine.py` with:

```python
def _normalise_origin(raw_origin: str) -> str | None:
    valid_states = list(_IATA_MAP.keys())
    client = Groq(api_key=GROQ_API_KEY)
    response = client.chat.completions.create(
        model="llama3-8b-8192",
        messages=[{
            "role": "user",
            "content": (
                f"Map this user input to exactly one of these Malaysian state names, "
                f"or reply NULL if none match.\n"
                f"Valid states: {', '.join(valid_states)}\n"
                f"User input: {raw_origin}\n"
                f"Reply with only the exact state name or NULL."
            ),
        }],
        temperature=0,
        max_tokens=20,
    )
    result = response.choices[0].message.content.strip()
    return result if result in valid_states else None
```

- [ ] **Step 4: Run normalisation tests**

```
cd backend
pytest tests/test_ai_engine.py::test_normalise_origin_returns_canonical_state_name tests/test_ai_engine.py::test_normalise_origin_returns_none_for_unrecognised_input tests/test_ai_engine.py::test_normalise_origin_returns_none_when_groq_returns_invalid_state -v
```

Expected: 3 PASSED

- [ ] **Step 5: Commit**

```bash
git add backend/ai_engine.py backend/tests/test_ai_engine.py
git commit -m "feat: add _normalise_origin to map raw user input to IATA_MAP key via Groq"
```

---

## Task 3: Core `generate_itinerary()` Implementation

**Files:**
- Modify: `backend/ai_engine.py`
- Modify: `backend/tests/test_ai_engine.py`

This is the main pipeline: normalise origin → three `capture()` calls → slim docs → build Groq prompt → parse JSON → return structured result.

- [ ] **Step 1: Add `generate_itinerary()` tests to `test_ai_engine.py`**

Append these tests to the bottom of `backend/tests/test_ai_engine.py`:

```python
# ─── generate_itinerary ───────────────────────────────

_MOCK_HOTELS = [{
    "name": "Sunway Hotel", "category": "mid-range",
    "price_per_night": {"min": 200, "max": 350, "currency": "MYR"},
    "rating": 4.2, "amenities": ["Pool", "WiFi"],
    "location": {"city": "Subang Jaya", "country": "Malaysia"},
    "data_freshness": "fresh",
}]
_MOCK_ATTRACTIONS = [{
    "name": "Sunway Lagoon", "category": "entertainment",
    "popularity_score": 4.5, "opening_hours": "10AM-6PM",
    "location": {"city": "Subang Jaya", "country": "Malaysia"},
}]
_MOCK_FLIGHTS = [{
    "airline": "AirAsia", "flight_number": "AK 6121",
    "price": 150.0, "duration_minutes": 60,
    "origin_state": "Johor Bahru", "data_freshness": "fresh",
}]

_MOCK_ITINERARY_JSON = json.dumps({
    "destination": "Subang Jaya",
    "budget_myr": 1000,
    "days": 2,
    "itinerary": [
        {
            "day": 1,
            "hotel": {"name": "Sunway Hotel", "category": "mid-range", "est_price_per_night": 200},
            "attractions": [{"name": "Sunway Lagoon", "category": "entertainment", "opening_hours": "10AM-6PM"}],
            "estimated_daily_cost": 400,
        }
    ],
    "flight": {"airline": "AirAsia", "flight_number": "AK 6121", "price": 150, "origin": "Johor Bahru"},
    "total_estimated_cost": 950,
    "data_freshness_note": None,
})


def test_generate_itinerary_returns_structured_json():
    from ai_engine import generate_itinerary
    mock_groq_response = MagicMock()
    mock_groq_response.choices[0].message.content = _MOCK_ITINERARY_JSON

    with patch("ai_engine.capture") as mock_capture, \
         patch("ai_engine._normalise_origin", return_value="Johor Bahru"), \
         patch("ai_engine.Groq") as MockGroq:

        mock_capture.side_effect = lambda query, entity_type, **kw: (
            _MOCK_HOTELS if entity_type == "hotels" else
            _MOCK_ATTRACTIONS if entity_type == "attractions" else
            _MOCK_FLIGHTS
        )
        MockGroq.return_value.chat.completions.create.return_value = mock_groq_response

        result = generate_itinerary("Subang Jaya", 1000.0, 2, origin="JB")

    assert result["destination"] == "Subang Jaya"
    assert result["budget_myr"] == 1000
    assert result["days"] == 2
    assert len(result["itinerary"]) == 1
    assert result["flight"]["airline"] == "AirAsia"
    assert result["total_estimated_cost"] == 950


def test_generate_itinerary_fallback_when_groq_returns_invalid_json():
    from ai_engine import generate_itinerary
    mock_groq_response = MagicMock()
    mock_groq_response.choices[0].message.content = "Sorry, I cannot generate an itinerary."

    with patch("ai_engine.capture", return_value=[]), \
         patch("ai_engine._normalise_origin", return_value=None), \
         patch("ai_engine.Groq") as MockGroq:

        MockGroq.return_value.chat.completions.create.return_value = mock_groq_response
        result = generate_itinerary("Shah Alam", 500.0, 1)

    assert "raw" in result
    assert result["destination"] == "Shah Alam"
    assert result["budget_myr"] == 500.0
    assert result["days"] == 1


def test_generate_itinerary_no_origin_skips_flight_capture():
    from ai_engine import generate_itinerary
    mock_groq_response = MagicMock()
    mock_groq_response.choices[0].message.content = _MOCK_ITINERARY_JSON

    with patch("ai_engine.capture") as mock_capture, \
         patch("ai_engine.Groq") as MockGroq:

        mock_capture.return_value = []
        MockGroq.return_value.chat.completions.create.return_value = mock_groq_response

        generate_itinerary("Shah Alam", 800.0, 3)

    flight_calls = [c for c in mock_capture.call_args_list if c.args[1] == "flights"]
    assert len(flight_calls) == 0


def test_generate_itinerary_adds_stale_note_when_any_doc_is_stale():
    from ai_engine import generate_itinerary
    stale_hotel = {**_MOCK_HOTELS[0], "data_freshness": "stale"}
    groq_json = json.dumps({
        "destination": "Shah Alam", "budget_myr": 500, "days": 1,
        "itinerary": [], "flight": None, "total_estimated_cost": 0,
        "data_freshness_note": "some prices are estimates and may vary.",
    })
    mock_groq_response = MagicMock()
    mock_groq_response.choices[0].message.content = groq_json

    with patch("ai_engine.capture", return_value=[stale_hotel]), \
         patch("ai_engine.Groq") as MockGroq:

        MockGroq.return_value.chat.completions.create.return_value = mock_groq_response
        result = generate_itinerary("Shah Alam", 500.0, 1)

    assert result.get("data_freshness_note") is not None
```

- [ ] **Step 2: Run tests to confirm they fail**

```
cd backend
pytest tests/test_ai_engine.py::test_generate_itinerary_returns_structured_json -v
```

Expected: FAIL — `generate_itinerary` returns `None` (stub)

- [ ] **Step 3: Implement `generate_itinerary()` in `ai_engine.py`**

Replace the `generate_itinerary` stub in `backend/ai_engine.py` with:

```python
def generate_itinerary(
    destination: str,
    budget: float,
    days: int,
    origin: str = None,
    travel_date: str = None,
) -> dict:
    canonical_origin = _normalise_origin(origin) if origin else None

    hotels = capture(destination, "hotels", city=destination, travel_date=travel_date) or []
    attractions = capture(destination, "attractions", city=destination) or []
    flights = capture(canonical_origin, "flights", travel_date=travel_date) if canonical_origin else []
    flights = flights or []

    slim_hotels = _slim_docs(hotels, "hotels")
    slim_attractions = _slim_docs(attractions, "attractions")
    slim_flights = _slim_docs(flights, "flights")

    all_docs = hotels + attractions + flights
    stale_note = (
        "some prices are estimates and may vary."
        if any(d.get("data_freshness") == "stale" for d in all_docs)
        else None
    )

    prompt = (
        f"You are a travel planning assistant for Malaysia.\n"
        f"Generate a {days}-day itinerary for {destination} with a total budget of MYR {budget}.\n\n"
        f"Hotels available:\n{json.dumps(slim_hotels, indent=2)}\n\n"
        f"Attractions available:\n{json.dumps(slim_attractions, indent=2)}\n\n"
        f"Flights available (origin: {canonical_origin or 'not provided'}):\n"
        f"{json.dumps(slim_flights, indent=2)}\n\n"
        f"Return ONLY valid JSON in this exact schema:\n"
        f'{{\n'
        f'  "destination": "{destination}",\n'
        f'  "budget_myr": {budget},\n'
        f'  "days": {days},\n'
        f'  "itinerary": [\n'
        f'    {{\n'
        f'      "day": 1,\n'
        f'      "hotel": {{"name": "...", "category": "...", "est_price_per_night": 0}},\n'
        f'      "attractions": [{{"name": "...", "category": "...", "opening_hours": "..."}}],\n'
        f'      "estimated_daily_cost": 0\n'
        f'    }}\n'
        f'  ],\n'
        f'  "flight": {{"airline": "...", "flight_number": "...", "price": 0, "origin": "..."}} or null,\n'
        f'  "total_estimated_cost": 0,\n'
        f'  "data_freshness_note": {json.dumps(stale_note)}\n'
        f"}}"
    )

    client = Groq(api_key=GROQ_API_KEY)
    response = client.chat.completions.create(
        model="llama3-8b-8192",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=1500,
    )

    raw = response.choices[0].message.content.strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"raw": raw, "destination": destination, "budget_myr": budget, "days": days}
```

- [ ] **Step 4: Run all `generate_itinerary` tests**

```
cd backend
pytest tests/test_ai_engine.py -v
```

Expected: all tests PASSED (the old stub tests were replaced in Task 1 Step 1)

- [ ] **Step 5: Commit**

```bash
git add backend/ai_engine.py backend/tests/test_ai_engine.py
git commit -m "feat: implement generate_itinerary with Groq structured JSON pipeline"
```

---

## Task 4: REST Endpoint in `main.py`

**Files:**
- Modify: `backend/main.py`

Expose `generate_itinerary()` as a `POST /itinerary` endpoint. The request body carries all user inputs; the response is the structured JSON dict.

- [ ] **Step 1: Write the endpoint test**

Create `backend/tests/test_main.py`:

```python
import json
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch
from main import app

client = TestClient(app)

_MOCK_RESULT = {
    "destination": "Shah Alam",
    "budget_myr": 800.0,
    "days": 2,
    "itinerary": [
        {
            "day": 1,
            "hotel": {"name": "Hotel XYZ", "category": "budget", "est_price_per_night": 100},
            "attractions": [{"name": "Blue Mosque", "category": "cultural", "opening_hours": "9AM-5PM"}],
            "estimated_daily_cost": 200,
        }
    ],
    "flight": None,
    "total_estimated_cost": 400,
    "data_freshness_note": None,
}


def test_itinerary_endpoint_returns_200_with_valid_payload():
    with patch("main.generate_itinerary", return_value=_MOCK_RESULT):
        response = client.post("/itinerary", json={
            "destination": "Shah Alam",
            "budget": 800.0,
            "days": 2,
        })
    assert response.status_code == 200
    body = response.json()
    assert body["destination"] == "Shah Alam"
    assert body["days"] == 2


def test_itinerary_endpoint_passes_optional_origin_and_travel_date():
    with patch("main.generate_itinerary", return_value=_MOCK_RESULT) as mock_fn:
        client.post("/itinerary", json={
            "destination": "Shah Alam",
            "budget": 800.0,
            "days": 2,
            "origin": "Johor Bahru",
            "travel_date": "2026-07-01",
        })
    mock_fn.assert_called_once_with(
        destination="Shah Alam",
        budget=800.0,
        days=2,
        origin="Johor Bahru",
        travel_date="2026-07-01",
    )


def test_itinerary_endpoint_returns_422_for_missing_required_fields():
    response = client.post("/itinerary", json={"destination": "Shah Alam"})
    assert response.status_code == 422


def test_health_endpoint_still_works():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

- [ ] **Step 2: Run tests to confirm they fail**

```
cd backend
pytest tests/test_main.py -v
```

Expected: FAIL — no `/itinerary` route exists yet

- [ ] **Step 3: Add the endpoint to `main.py`**

Replace the entire contents of `backend/main.py` with:

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from ai_engine import generate_itinerary

app = FastAPI(title="Trekku API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ItineraryRequest(BaseModel):
    destination: str
    budget: float
    days: int
    origin: Optional[str] = None
    travel_date: Optional[str] = None


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/itinerary")
def itinerary(request: ItineraryRequest) -> dict:
    return generate_itinerary(
        destination=request.destination,
        budget=request.budget,
        days=request.days,
        origin=request.origin,
        travel_date=request.travel_date,
    )
```

- [ ] **Step 4: Run all endpoint tests**

```
cd backend
pytest tests/test_main.py -v
```

Expected: 4 PASSED

- [ ] **Step 5: Run the full test suite to check for regressions**

```
cd backend
pytest tests/ -v
```

Expected: all tests PASSED

- [ ] **Step 6: Commit**

```bash
git add backend/main.py backend/tests/test_main.py
git commit -m "feat: add POST /itinerary endpoint wired to generate_itinerary"
```

---

## Self-Review

### Spec Coverage Check

| Design Decision | Covered by Task |
|---|---|
| Budget passed whole to Groq | Task 3 — prompt includes `MYR {budget}` without splitting |
| Origin normalisation via Groq | Task 2 — `_normalise_origin()` with temperature=0 classification |
| Document slimming before LLM | Task 1 — `_slim_docs()` strips operational fields |
| Structured JSON output with fallback | Task 3 — `json.loads()` with `{"raw": ...}` fallback |
| `data_freshness_note` when stale | Task 3 — `stale_note` assembled before prompt, passed in JSON schema |
| REST endpoint in `main.py` | Task 4 — `POST /itinerary` with `ItineraryRequest` model |
| `travel_date` passed through to `capture()` | Task 3 — forwarded to hotel and flight `capture()` calls |
| No flight call when origin is `None` | Task 3 — guarded by `if canonical_origin` |

### Placeholder Scan

No TBDs, TODOs, or "handle edge cases" comments. All code blocks are complete. Type signatures are consistent across all tasks.

### Type Consistency Check

- `_slim_docs(docs: list, entity_type: str) -> list` — consistent across Task 1 and Task 3
- `_normalise_origin(raw_origin: str) -> str | None` — consistent across Task 2 and Task 3
- `generate_itinerary(destination, budget, days, origin=None, travel_date=None) -> dict` — consistent across Task 3 and Task 4
- `ItineraryRequest.destination / budget / days / origin / travel_date` — consistent with `generate_itinerary()` call in Task 4
