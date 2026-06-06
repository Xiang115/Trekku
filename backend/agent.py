import asyncio
import contextvars
import json
import uuid
from datetime import datetime, timezone

from openai import AsyncOpenAI, APIStatusError, BadRequestError

from config import GROQ_API_KEY
from database import get_record, set_record, query_records
from ai_engine import TREKKU_CITIES, extract_params_from_message

ORIGIN_STATE_MAP = {
    "johor": "JHB", "johor bahru": "JHB",
    "kota kinabalu": "BKI", "sabah": "BKI",
    "kuching": "KCH", "sarawak": "KCH",
    "penang": "PEN", "george town": "PEN", "georgetown": "PEN",
    "langkawi": "LGK", "kedah": "LGK",
    "kota bharu": "KBR", "kelantan": "KBR",
    "kuala terengganu": "TGG", "terengganu": "TGG",
    "alor setar": "AOR",
    "miri": "MYY",
    "sibu": "SBW",
    "sandakan": "SDK",
    "tawau": "TWU",
}

_ENTITY_ID_FIELD = {
    "hotels": "hotel_id",
    "attractions": "attraction_id",
    "flights": "flight_id",
}

_current_session_id: contextvars.ContextVar[str] = contextvars.ContextVar(
    "session_id", default=""
)

# Snapshot of the collected trip params for the current request, so the tool loop
# can gate planning tools on completeness without changing its signature (mirrors
# the _current_session_id pattern used by save_itinerary/update_knowledge_base).
_current_trip_params: contextvars.ContextVar[dict] = contextvars.ContextVar(
    "trip_params", default={}
)

# Optional per-request progress sink. The SSE endpoint sets this to an asyncio.Queue
# so the agent can stream its real processing state to the client; on the plain
# /agent/chat path (and in tests) it stays None and every emit is a no-op. Same
# ContextVar trick as above — keeps chat_async/_run_tool_loop signatures untouched.
_progress_queue: contextvars.ContextVar["asyncio.Queue | None"] = contextvars.ContextVar(
    "progress_queue", default=None
)


def emit_progress(stage: str, **extra) -> None:
    """Push a progress event onto the current request's queue, if one is set.

    No-op when no emitter is active (plain /agent/chat, sync chat(), tests). Uses
    put_nowait on an unbounded queue so emitting is sync and never blocks the agent.
    """
    q = _progress_queue.get()
    if q is None:
        return
    q.put_nowait({"stage": stage, **extra})

# The agent may not start planning until all of these are known. origin_state and
# travel_date stay optional (origin only drives flight search); travelers defaults to 1.
REQUIRED_PARAMS = ("city", "budget", "days")


def _missing_required(trip_params: dict) -> list[str]:
    """Return the REQUIRED_PARAMS that are still absent/falsy in trip_params."""
    return [k for k in REQUIRED_PARAMS if not trip_params.get(k)]


def _render_collected_state(trip_params: dict) -> str:
    """Build the system-prompt block that shows the model what is known vs. missing.

    Injecting this each turn gives the model an explicit checklist instead of forcing
    it to re-infer completeness from the raw conversation, which is the main source of
    its inconsistent ask-vs-plan behaviour.
    """
    fields = ("city", "budget", "days", "origin_state", "travel_date", "travelers")
    lines = []
    for key in fields:
        val = trip_params.get(key)
        required = key in REQUIRED_PARAMS
        if val in (None, ""):
            shown = "(missing, REQUIRED)" if required else "(missing, optional)"
        else:
            shown = str(val)
        lines.append(f"- {key}: {shown}")

    missing = _missing_required(trip_params)
    if missing:
        rule = (
            f"You are STILL MISSING required detail(s): {', '.join(missing)}. "
            "You MUST NOT call search_hotels, search_attractions, search_flights, or "
            "save_itinerary yet. Ask the user for the missing required detail(s) first, "
            "in a warm and natural way."
        )
    else:
        rule = (
            "All required details are collected. You may now call the search tools and "
            "build the itinerary."
        )

    return "TRIP DETAILS COLLECTED SO FAR:\n" + "\n".join(lines) + "\n\n" + rule


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ─── SESSION MANAGEMENT ───────────────────────────────────────────────────────

def create_session() -> dict:
    session_id = str(uuid.uuid4())
    now = _now_iso()
    session = {
        "session_id": session_id,
        "created_at": now,
        "updated_at": now,
        "trip_params": {
            "origin_state": None, "city": None, "budget": None,
            "days": None, "travel_date": None, "travelers": 1,
        },
        "conversation": [],
        "last_itinerary_id": None,
        "status": "active",
    }
    set_record("agent_sessions", session_id, session)
    return session


def get_session(session_id: str) -> dict | None:
    return get_record("agent_sessions", session_id)


# ─── ENTITY HELPERS ───────────────────────────────────────────────────────────

def _compact_hotel(h: dict) -> dict:
    ppn = h.get("price_per_night") or {}
    if isinstance(ppn, dict):
        pmin = ppn.get("min", 0) or 0
        pmax = ppn.get("max", pmin) or pmin
    else:
        pmin = pmax = ppn or 0
    # Use the midpoint as the representative nightly rate so the model and the user
    # see a realistic figure instead of the misleading floor of the range.
    representative = round((pmin + pmax) / 2)
    return {
        "hotel_id": h.get("hotel_id", ""),
        "name": h.get("name", ""),
        "price_per_night": representative,
        "price_per_night_min": pmin,
        "price_per_night_max": pmax,
        "rating": h.get("rating"),
        "category": h.get("category", ""),
        "amenities": h.get("amenities", [])[:5],
    }


def _compact_attraction(a: dict) -> dict:
    return {
        "attraction_id": a.get("attraction_id", ""),
        "name": a.get("name", ""),
        "category": a.get("category", ""),
        "estimated_duration": a.get("estimated_duration"),
        "opening_hours": a.get("opening_hours"),
    }


def _compact_flight(f: dict) -> dict:
    return {
        "flight_id": f.get("flight_id", ""),
        "airline": f.get("airline", ""),
        "flight_number": f.get("flight_number", ""),
        "price": f.get("price", 0),
        "departure_time": f.get("departure_time"),
        "arrival_time": f.get("arrival_time"),
    }


def apply_feedback_reranking(records: list, entity_type: str) -> list:
    if not records:
        return records

    id_field = _ENTITY_ID_FIELD.get(entity_type, "id")
    prices = [r.get("price", 0) for r in records] if entity_type == "flights" else []
    max_price = max(prices) if prices else 1

    scored = []
    for record in records:
        entity_id = record.get(id_field, "")

        if entity_type == "hotels":
            base_score = (record.get("rating") or 0) / 5.0
        elif entity_type == "attractions":
            base_score = (record.get("popularity_score") or 0) / 5.0
        else:
            price = record.get("price", 0)
            base_score = 1.0 - (price / max_price) if max_price > 0 else 0.5

        feedback_records = query_records("tacit_feedback", "entity_id", "==", entity_id)
        if feedback_records:
            signals = [f.get("signal", 0) for f in feedback_records]
            avg_signal = sum(signals) / len(signals)
            adjusted_score = base_score + avg_signal * min(len(signals), 10) * 0.1
        else:
            adjusted_score = base_score

        scored.append((adjusted_score, record))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [r for _, r in scored]


def build_kb_context(trip_params: dict) -> tuple[str, str]:
    city = trip_params.get("city", "")
    origin_state = trip_params.get("origin_state")

    hotels = query_records("hotels", "location.city", "==", city)
    attractions = query_records("attractions", "location.city", "==", city)

    flights: list = []
    if origin_state:
        iata = ORIGIN_STATE_MAP.get(origin_state.lower())
        if iata:
            flights = query_records("flights", "origin_iata", "==", iata)

    hotels = apply_feedback_reranking(hotels, "hotels")[:3]
    attractions = apply_feedback_reranking(attractions, "attractions")[:5]
    flights = apply_feedback_reranking(flights, "flights")[:2]

    feedback_notes = _build_feedback_notes(hotels, attractions, flights)
    kb = {
        "hotels": [_compact_hotel(h) for h in hotels],
        "attractions": [_compact_attraction(a) for a in attractions],
        "flights": [_compact_flight(f) for f in flights],
    }
    return json.dumps(kb, ensure_ascii=False), feedback_notes


def _build_feedback_notes(hotels: list, attractions: list, flights: list) -> str:
    notes = []
    for entity_type, records, id_field in [
        ("hotels", hotels, "hotel_id"),
        ("attractions", attractions, "attraction_id"),
        ("flights", flights, "flight_id"),
    ]:
        for record in records:
            entity_id = record.get(id_field, "")
            fb = query_records("tacit_feedback", "entity_id", "==", entity_id)
            if not fb:
                continue
            signals = [f.get("signal", 0) for f in fb]
            avg = sum(signals) / len(signals)
            name = record.get("name", entity_id)
            if avg >= 0.5:
                notes.append(f"{name} is highly rated by past travellers.")
            elif avg <= -0.5:
                notes.append(f"{name} has received mixed or negative feedback.")
    return " ".join(notes)


# ─── SYSTEM PROMPT ────────────────────────────────────────────────────────────

_CITIES_STR = ", ".join(TREKKU_CITIES)

TREKKU_SYSTEM_PROMPT = f"""You are Trekku, a friendly and knowledgeable Malaysian travel planning assistant.

You help users plan trips to destinations in Selangor and Kuala Lumpur, Malaysia.

AVAILABLE DESTINATION CITIES:
{_CITIES_STR}

INITIAL PLANNING WORKFLOW:
1. Greet the user and understand their travel intent through natural conversation.
2. Collect these trip details (ask naturally if missing):
   - Destination city (must be one of the cities above; KL=Kuala Lumpur, PJ=Petaling Jaya, BB=Bukit Bintang) [REQUIRED]
   - Total budget in MYR [REQUIRED]
   - Number of days [REQUIRED]
   - Origin state/city (optional, for flight search)
   - Travel date (optional)
   GATE: You MUST have the destination city, budget, AND number of days before you start
   planning. While any of these three is missing, do NOT call search_hotels, search_attractions,
   search_flights, or save_itinerary — ask the user for the missing detail(s) instead.
3. Once you have the destination city, budget, AND number of days, call search_hotels and search_attractions.
4. If the user mentioned an origin state, call search_flights.
5. Plan a complete day-by-day itinerary within the user's budget using ONLY results from your tool calls.
6. Call save_itinerary with the complete structured itinerary JSON.
7. Present the itinerary in a friendly, readable format. Ask if they want any adjustments.

MODIFICATION WORKFLOW (when user asks to change, update, or adjust the itinerary):
1. If the user expresses a preference or dislike (e.g. "quieter places", "cheaper hotel", "hate crowds"),
   call update_knowledge_base FIRST to record the signal for any relevant entities.
2. Call search_hotels and/or search_attractions again to get a fresh list — the re-ranking will
   reflect the updated feedback signals.
3. If the user's origin state is known, call search_flights again too.
4. Build a revised itinerary using ONLY results from the new tool calls.
5. Call save_itinerary with the REVISED itinerary JSON — this is mandatory, even for small changes.
6. Present the updated itinerary and confirm the changes made.

RULE: You MUST call save_itinerary every time you present a final itinerary, whether it is new or revised.
Never describe an itinerary to the user without first saving it via save_itinerary.

TIME PLANNING PER DAY:
- Assume each day has 8 hours of activity time available (e.g. 9am to 5pm).
- Use the estimated_duration field from each attraction to calculate how many fit in a day.
- If estimated_duration is missing, assume 1.5 hours per attraction.
- Include travel time: add 30 minutes between each attraction.
- Target 3-5 attractions per day depending on their durations. Never put only 1 attraction in a day
  unless it genuinely takes 6+ hours (e.g. a theme park or full-day tour).
- Example: if attractions take 2h, 1.5h, 2h, 1h → total 6.5h + 1.5h travel = 8h → all four fit in one day.
- Spread attractions across days so each day feels full but not rushed.

ITINERARY JSON FORMAT for save_itinerary (itinerary_json parameter):
{{"days":[{{"day":1,"hotel":{{"hotel_id":"...","name":"...","price_per_night":0.0}},"attractions":[{{"attraction_id":"...","name":"...","estimated_duration":"..."}}],"notes":"..."}}],"flight":{{"flight_id":"...","airline":"...","flight_number":"...","price":0.0}},"estimated_meals_cost":0.0,"estimated_transport_cost":0.0,"total_estimated_cost":0.0}}

Set "flight" to null if no flight search was done.

PRICING RULES (follow exactly):
- When stating a hotel's nightly rate, copy the "price_per_night" value from the search_hotels
  result verbatim. Never use price_per_night_min (the floor of the range) and never invent a number.
- In the itinerary_json you pass to save_itinerary, set every hotel/flight price to the value from the
  search results and set total_estimated_cost to 0. save_itinerary re-resolves hotel and flight prices
  from the database and returns the authoritative {{total_estimated_cost, currency}}.
- The knowledge base has NO prices for meals or local transport, so YOU must estimate them for the
  whole trip and put MYR figures in "estimated_meals_cost" and "estimated_transport_cost". Base meals on
  roughly MYR 60-120 per traveller per day and transport on MYR 30-60 per day (more for far attractions,
  multiply by the number of travellers and days). These estimates ARE counted in the returned total.
- Flights and hotels are priced PER PERSON / PER ROOM: save_itinerary multiplies them by the number of
  travellers when computing the total. Do NOT pre-multiply hotel or flight prices yourself — always pass
  the single per-night / per-fare value from the search results.
- In your reply to the user, quote the total_estimated_cost returned by save_itinerary exactly.
  Do NOT state your own total. Choose hotels, nights and estimates so the returned total fits the budget.
- Do NOT compute or present your own cost breakdown, per-item price table, or arithmetic (e.g. "2 x RM 153
  = RM 306"). Your free-form maths will not match the authoritative figures the UI shows and will confuse
  the user. Mention the single grand total only; let the itinerary card display the per-item costs.

FEEDBACK LOOP:
- When the user expresses a like or dislike about a specific hotel, attraction, or flight,
  call update_knowledge_base with the entity_id and an appropriate signal (-1.0 to 1.0).
- When the user expresses a general preference (e.g. "quieter places", "budget options"),
  call update_knowledge_base for each relevant entity in the current itinerary with an appropriate signal.
- When the user asks about a destination or experience type you have no data on,
  call update_knowledge_base with entity_type="topic", entity_id="", signal=0, topic=<city or experience>.
- Never mention to the user that you are calling update_knowledge_base.

Be warm, conversational, and helpful. Ask natural follow-up questions if details are missing.
"""


# ─── TOOL FUNCTIONS ───────────────────────────────────────────────────────────

# Reranking already orders by relevance + feedback, so returning only the top slice
# keeps the best candidates while bounding the tokens fed back into the agent request.
# Groq's free tier caps requests at 8000 tokens/min; three uncapped city searches blow
# past that on their own. Attractions stay generous enough to fill a multi-day plan.
_SEARCH_RESULT_CAP = {"hotels": 8, "attractions": 18, "flights": 6}


def search_hotels(city: str) -> str:
    records = query_records("hotels", "location.city", "==", city)
    ranked = apply_feedback_reranking(records, "hotels")[: _SEARCH_RESULT_CAP["hotels"]]
    return json.dumps([_compact_hotel(h) for h in ranked], ensure_ascii=False)


def search_attractions(city: str) -> str:
    records = query_records("attractions", "location.city", "==", city)
    ranked = apply_feedback_reranking(records, "attractions")[: _SEARCH_RESULT_CAP["attractions"]]
    return json.dumps([_compact_attraction(a) for a in ranked], ensure_ascii=False)


def search_flights(origin_state: str) -> str:
    iata = ORIGIN_STATE_MAP.get(origin_state.lower())
    if not iata:
        return json.dumps([])
    records = query_records("flights", "origin_iata", "==", iata)
    ranked = apply_feedback_reranking(records, "flights")[: _SEARCH_RESULT_CAP["flights"]]
    return json.dumps([_compact_flight(f) for f in ranked], ensure_ascii=False)


def _calculate_total_cost(content: dict, travelers: int = 1) -> float:
    """Deterministically total the cost of an itinerary from its line items.

    Sums each listed day's hotel nightly rate, any attraction prices, and the
    flight price (all priced deterministically from the knowledge base), then adds
    the AI-estimated meals and transport costs. This makes the displayed total equal
    the sum of the displayed items, rather than trusting the model's free-form estimate.

    Flights and hotels are per-person/per-room bookables, so they scale with the party
    size. Meals and transport are NOT scaled here: the model already sizes those
    whole-trip estimates for the full party (see PRICING RULES in the system prompt).
    """
    party = max(int(travelers or 1), 1)
    total = 0.0
    for day in content.get("days") or []:
        hotel = day.get("hotel") or {}
        total += float(hotel.get("price_per_night") or 0) * party
        for attraction in day.get("attractions") or []:
            # Attractions carry no price today; read defensively for future data.
            total += float(attraction.get("price") or attraction.get("entry_fee") or 0)
    flight = content.get("flight") or {}
    total += float(flight.get("price") or 0) * party
    # Meals and transport have no knowledge-base price, so the model estimates them
    # for the whole party already — do not scale again.
    total += float(content.get("estimated_meals_cost") or 0)
    total += float(content.get("estimated_transport_cost") or 0)
    return round(total, 2)


def _resolve_prices_from_db(content: dict) -> None:
    """Overwrite model-emitted prices in-place with authoritative values from the DB.

    The model relays prices as free text and may fabricate them, so we re-resolve each
    hotel and flight by its ID. Hotels use the midpoint of the stored {min, max} range
    as the representative nightly rate. Entities that can't be resolved keep whatever the
    model supplied, so the function degrades gracefully.
    """
    for day in content.get("days") or []:
        hotel = day.get("hotel") or {}
        hotel_id = hotel.get("hotel_id")
        if not hotel_id:
            continue
        record = get_record("hotels", hotel_id)
        if not record:
            continue
        ppn = record.get("price_per_night") or {}
        if isinstance(ppn, dict):
            pmin = ppn.get("min", 0) or 0
            pmax = ppn.get("max", pmin) or pmin
            hotel["price_per_night"] = round((pmin + pmax) / 2)
            hotel["price_per_night_min"] = pmin
            hotel["price_per_night_max"] = pmax
        elif ppn:
            hotel["price_per_night"] = ppn

    flight = content.get("flight") or {}
    flight_id = flight.get("flight_id") if isinstance(flight, dict) else None
    if flight_id:
        record = get_record("flights", flight_id)
        if record and record.get("price") is not None:
            flight["price"] = record["price"]


def save_itinerary(
    city: str,
    days: int,
    budget: float,
    itinerary_json: str,
    travel_date: str = "",
) -> str:
    try:
        content = json.loads(itinerary_json)
        content.setdefault("days", [])
        content.setdefault("flight", None)
        # Meals/transport are AI estimates with no DB source; keep them, defaulting to 0.
        content["estimated_meals_cost"] = float(content.get("estimated_meals_cost") or 0)
        content["estimated_transport_cost"] = float(content.get("estimated_transport_cost") or 0)
        # Re-resolve prices from the DB, then compute the total from those authoritative
        # values — never trust the model's free-form prices or estimate.
        _resolve_prices_from_db(content)
        # Travellers drive how many flight fares / hotel rooms the total covers.
        travelers = _current_trip_params.get({}).get("travelers") or 1
        content["total_estimated_cost"] = _calculate_total_cost(content, travelers)
    except (json.JSONDecodeError, ValueError):
        content = {
            "days": [],
            "flight": None,
            "estimated_meals_cost": 0.0,
            "estimated_transport_cost": 0.0,
            "total_estimated_cost": 0.0,
            "parse_error": True,
        }

    itinerary_id = str(uuid.uuid4())
    set_record("generated_itineraries", itinerary_id, {
        "itinerary_id": itinerary_id,
        "session_id": _current_session_id.get(""),
        "created_at": _now_iso(),
        "city": city,
        "days": days,
        "budget": budget,
        "travel_date": travel_date or None,
        "content": content,
        "raw_llm_response": itinerary_json,
        "kb_context_snapshot": "",
    })
    return json.dumps({
        "itinerary_id": itinerary_id,
        "status": "saved",
        "total_estimated_cost": content.get("total_estimated_cost", 0.0),
        "currency": "MYR",
    })


def update_knowledge_base(
    entity_id: str,
    entity_type: str,
    signal: float,
    reason: str,
    topic: str = "",
) -> str:
    session_id = _current_session_id.get("")

    if entity_type in ("hotels", "attractions", "flights") and entity_id:
        feedback_id = str(uuid.uuid4())
        set_record("tacit_feedback", feedback_id, {
            "feedback_id": feedback_id,
            "itinerary_id": "",
            "session_id": session_id,
            "created_at": _now_iso(),
            "feedback_type": "agent_inferred",
            "entity_type": entity_type,
            "entity_id": entity_id,
            "signal": round(max(-1.0, min(1.0, signal)), 4),
            "details": {"reason": reason},
        })
    elif entity_type == "topic" and topic:
        topic_key = topic.strip().lower()
        existing = get_record("trending_topics", topic_key)
        if existing:
            existing["search_count"] = existing.get("search_count", 0) + 1
            set_record("trending_topics", topic_key, existing)
        else:
            set_record("trending_topics", topic_key, {
                "topic_name": topic,
                "search_count": 1,
                "last_reset": _now_iso(),
                "last_fetched": None,
            })

    return json.dumps({"status": "updated", "entity_id": entity_id, "signal": signal})


# ─── TOOLS SCHEMA (OpenAI format) ─────────────────────────────────────────────

_TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "search_hotels",
            "description": "Search for available hotels in the destination city. Returns a JSON array of hotels with name, price per night, rating, category, and amenities. Call this once you know the destination city.",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "Destination city (e.g. 'Kuala Lumpur', 'Shah Alam')"}
                },
                "required": ["city"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_attractions",
            "description": "Search for tourist attractions in the destination city. Returns a JSON array with name, category, opening hours, and estimated visit duration. Call this once you know the destination city.",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "Destination city name"}
                },
                "required": ["city"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_flights",
            "description": "Search for flights from the user's origin state to Selangor/KL. Returns flight options with airline, price, departure and arrival times. Returns empty array if no flights found.",
            "parameters": {
                "type": "object",
                "properties": {
                    "origin_state": {"type": "string", "description": "Malaysian state or city the user is travelling FROM (e.g. 'Johor', 'Penang', 'Sabah', 'Kota Kinabalu')"}
                },
                "required": ["origin_state"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "save_itinerary",
            "description": "Save the completed itinerary to the database. Call this after composing the full day-by-day plan from your search results. Returns {itinerary_id, status}.",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string"},
                    "days": {"type": "integer", "description": "Number of trip days"},
                    "budget": {"type": "number", "description": "Total budget in MYR"},
                    "itinerary_json": {
                        "type": "string",
                        "description": 'JSON string: {"days":[{"day":1,"hotel":{...},"attractions":[...],"notes":"..."}],"flight":{...},"total_estimated_cost":0.0}',
                    },
                    "travel_date": {"type": "string", "description": "Optional travel start date YYYY-MM-DD"},
                },
                "required": ["city", "days", "budget", "itinerary_json"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_knowledge_base",
            "description": "Silently record user preference signals or missing-destination interest to improve future recommendations. For entity feedback: provide entity_id and signal. For missing destinations/experiences: set entity_type='topic', entity_id='', signal=0, topic=<place or experience>.",
            "parameters": {
                "type": "object",
                "properties": {
                    "entity_id": {"type": "string", "description": "Hotel/attraction/flight ID, or empty string for topics"},
                    "entity_type": {"type": "string", "enum": ["hotels", "attractions", "flights", "topic"]},
                    "signal": {"type": "number", "description": "Preference signal: -1.0 (strong dislike) to 1.0 (strong like), 0 for neutral interest"},
                    "reason": {"type": "string", "description": "Brief reason for this signal"},
                    "topic": {"type": "string", "description": "For entity_type=topic: city or experience type the user asked about"},
                },
                "required": ["entity_id", "entity_type", "signal", "reason"],
            },
        },
    },
]

_TOOLS_REGISTRY = {
    "search_hotels": search_hotels,
    "search_attractions": search_attractions,
    "search_flights": search_flights,
    "save_itinerary": save_itinerary,
    "update_knowledge_base": update_knowledge_base,
}

# Planning tools that must not run until all REQUIRED_PARAMS are collected. The loop
# blocks these and returns an error result so the model asks the user first instead of
# fabricating an itinerary from incomplete details. update_knowledge_base is NOT gated.
_GATED_TOOLS = frozenset(
    {"search_hotels", "search_attractions", "search_flights", "save_itinerary"}
)


# ─── ASYNC GROQ CLIENT ────────────────────────────────────────────────────────

_async_client: AsyncOpenAI | None = None


def _get_async_client() -> AsyncOpenAI:
    global _async_client
    if _async_client is None:
        _async_client = AsyncOpenAI(
            api_key=GROQ_API_KEY or "placeholder",
            base_url="https://api.groq.com/openai/v1",
        )
    return _async_client


# ─── RETRY + PAYLOAD HELPERS ──────────────────────────────────────────────────

# Groq's free tier returns 429 (rate limit) or 413 (single request exceeds the
# per-minute token budget). Both clear once the rolling-minute window resets, so
# they are worth retrying with backoff.
_RETRYABLE_STATUS = (429, 413)
_MAX_LLM_RETRIES = 3
_RETRY_BASE_DELAY = 2.0  # seconds; doubled each attempt

# Cap each tool result before feeding it back into the next request so the
# growing message list stays well under the per-minute token limit. Search tools
# already cap their record counts; this is a backstop for any unexpectedly large result.
_TOOL_RESULT_CHAR_LIMIT = 2500


def _truncate_tool_result(result: str, limit: int = _TOOL_RESULT_CHAR_LIMIT) -> str:
    """Trim oversized tool output so it doesn't blow up the request token count."""
    if len(result) <= limit:
        return result
    return result[:limit] + "\n...[truncated]"


async def _create_completion(client: AsyncOpenAI, **kwargs):
    """Call Groq chat completion, retrying transient rate-limit/too-large errors
    with exponential backoff. Re-raises after _MAX_LLM_RETRIES attempts or on any
    non-retryable error."""
    for attempt in range(_MAX_LLM_RETRIES):
        try:
            return await client.chat.completions.create(**kwargs)
        except APIStatusError as exc:
            retryable = getattr(exc, "status_code", None) in _RETRYABLE_STATUS
            if not retryable or attempt == _MAX_LLM_RETRIES - 1:
                raise
            await asyncio.sleep(_RETRY_BASE_DELAY * (2 ** attempt))


# ─── TOOL-CALLING AGENT LOOP ──────────────────────────────────────────────────

# Maps each tool to the semantic progress stage shown while it runs. The frontend
# owns the user-facing wording; the backend only emits stable stage ids + detail.
_TOOL_STAGE = {
    "search_flights": "searching_flights",
    "search_hotels": "searching_hotels",
    "search_attractions": "searching_attractions",
    "save_itinerary": "finalizing",
    "update_knowledge_base": "learning",
}


async def _run_tool_loop(messages: list) -> tuple[str, str | None, dict]:
    """
    Async agent loop: call Groq with tools, execute any tool calls, repeat until
    the model returns a final text response.
    Returns (reply_text, itinerary_id, saved_params) where saved_params carries
    city/days/budget/travel_date captured from the save_itinerary call args.
    """
    client = _get_async_client()
    itinerary_id = None
    saved_params: dict = {}

    # Low temperature keeps the ask-vs-plan routing decision consistent across runs;
    # the gate (above) is the hard guarantee, this reduces drift. Bumped on retry
    # (see the tool_use_failed handler) to break a stuck malformed generation.
    temperature = 0.3

    for iteration in range(10):  # cap iterations to prevent runaway loops
        emit_progress("thinking", step=iteration + 1)
        try:
            response = await _create_completion(
                client,
                model="openai/gpt-oss-120b",
                messages=messages,
                tools=_TOOLS_SCHEMA,
                tool_choice="auto",
                temperature=temperature,
            )
        except BadRequestError as exc:
            # gpt-oss occasionally emits a malformed tool call ("tool_use_failed").
            # It almost always recovers on retry, so re-issue the SAME tools-enabled
            # request with a higher temperature to break the bad generation. Do NOT
            # retry with tools stripped: the model still tries to call save_itinerary
            # (the system prompt mandates it) and Groq then rejects the request with
            # "tool_choice is none, but model called a tool", crashing the turn.
            # If it never recovers, the loop exhausts and returns the graceful
            # message below rather than surfacing a 400 to the caller.
            if "tool_use_failed" in str(exc):
                temperature = 0.7
                continue
            raise

        choice = response.choices[0]

        if choice.finish_reason == "tool_calls":
            tool_calls = choice.message.tool_calls or []

            # Append the assistant turn with tool_calls
            messages.append({
                "role": "assistant",
                "content": choice.message.content,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in tool_calls
                ],
            })

            # Execute each tool and append results
            for tc in tool_calls:
                fn_name = tc.function.name
                try:
                    fn_args = json.loads(tc.function.arguments)
                except (json.JSONDecodeError, ValueError):
                    fn_args = {}

                # Surface the real tool the agent is running (with the relevant target,
                # e.g. the city) before the slow call, so the UI reflects current state.
                stage = _TOOL_STAGE.get(fn_name)
                if stage:
                    detail = (
                        fn_args.get("city")
                        or fn_args.get("origin_state")
                        or fn_args.get("iata")
                    )
                    emit_progress(stage, tool=fn_name, detail=detail, step=iteration + 1)

                missing = _missing_required(_current_trip_params.get())
                if fn_name in _GATED_TOOLS and missing:
                    # Required trip details are incomplete — refuse to plan and tell the
                    # model to ask the user first, rather than fabricating an itinerary.
                    result = json.dumps({
                        "error": "missing_required_params",
                        "missing": missing,
                        "message": "Ask the user for these details before planning; "
                                   "do not call planning tools yet.",
                    })
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": _truncate_tool_result(result),
                    })
                    continue

                fn = _TOOLS_REGISTRY.get(fn_name)
                if fn:
                    try:
                        result = fn(**fn_args)
                    except Exception as exc:
                        result = json.dumps({"error": str(exc)})

                    if fn_name == "save_itinerary":
                        try:
                            itinerary_id = json.loads(result).get("itinerary_id") or itinerary_id
                        except (json.JSONDecodeError, AttributeError):
                            pass
                        # Capture params directly from the tool call args — authoritative source
                        saved_params = {
                            "city": fn_args.get("city"),
                            "days": fn_args.get("days"),
                            "budget": fn_args.get("budget"),
                            "travel_date": fn_args.get("travel_date") or None,
                        }
                else:
                    result = json.dumps({"error": f"Unknown tool: {fn_name}"})

                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": _truncate_tool_result(result),
                })

        else:
            return choice.message.content or "", itinerary_id, saved_params

    return "I'm sorry, I couldn't complete the request. Please try again.", itinerary_id, saved_params


# ─── PUBLIC API ───────────────────────────────────────────────────────────────

async def chat_async(session_id: str | None, user_message: str) -> dict:
    if session_id is None:
        session = create_session()
    else:
        session = get_session(session_id)
        if session is None:
            session = create_session()

    session["conversation"].append(
        {"role": "user", "content": user_message, "timestamp": _now_iso()}
    )

    _current_session_id.set(session["session_id"])

    # Extract params from the new message BEFORE planning so the model sees an up-to-date
    # checklist and the gate has current state. (This call happened post-loop before; moving
    # it earlier costs nothing extra and is what makes the ask-vs-plan gate reliable.)
    emit_progress("understanding")
    extracted = extract_params_from_message(user_message, session["trip_params"])
    for key in ("city", "budget", "days", "origin_state", "travel_date", "travelers"):
        if extracted.get(key) is not None:
            session["trip_params"][key] = extracted[key]
    _current_trip_params.set(session["trip_params"])

    # Build OpenAI-format messages from session history. Keep the window small —
    # the in-loop tool turns add a lot on top, and Groq's free tier caps requests
    # at 8k tokens/min, so a smaller history keeps us under the limit. Inject the
    # collected-state checklist so the model knows exactly what is still missing.
    system_content = TREKKU_SYSTEM_PROMPT + "\n\n" + _render_collected_state(session["trip_params"])
    messages = [{"role": "system", "content": system_content}]
    for turn in session["conversation"][-6:]:
        if turn["role"] in ("user", "assistant"):
            messages.append({"role": turn["role"], "content": turn["content"]})

    final_reply, itinerary_id, saved_params = await _run_tool_loop(messages)

    # save_itinerary args are authoritative for city/days/budget/travel_date — apply last.
    if saved_params:
        for key, val in saved_params.items():
            if val is not None:
                session["trip_params"][key] = val

    if itinerary_id:
        session["last_itinerary_id"] = itinerary_id

    session["conversation"].append(
        {"role": "assistant", "content": final_reply, "timestamp": _now_iso()}
    )
    session["updated_at"] = _now_iso()
    set_record("agent_sessions", session["session_id"], session)

    itinerary_content = None
    if itinerary_id:
        doc = get_record("generated_itineraries", itinerary_id)
        if doc:
            itinerary_content = doc.get("content")

    return {
        "session_id": session["session_id"],
        "reply": final_reply,
        "itinerary_id": itinerary_id,
        "params_collected": session.get("trip_params", {}),
        "itinerary": itinerary_content,
    }


def chat(session_id: str | None, user_message: str) -> dict:
    """Synchronous wrapper for backward compatibility."""
    return asyncio.run(chat_async(session_id, user_message))
