import json
import re

from openai import OpenAI

from config import GROQ_API_KEY, HUGGINGFACE_API_KEY, OPENROUTER_API_KEY

MODEL = "llama-3.3-70b-versatile"

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(
            api_key=GROQ_API_KEY or "placeholder",
            base_url="https://api.groq.com/openai/v1",
        )
    return _client

TREKKU_CITIES = [
    "Shah Alam", "Petaling Jaya", "Klang", "Subang Jaya",
    "Sepang", "Puchong", "Kuala Lumpur", "Bukit Bintang", "KLCC",
]

_CITIES_LOWER = {c.lower(): c for c in TREKKU_CITIES}


def call_llm(system_prompt: str, history: list, user_message: str) -> str:
    """Call OpenRouter LLM. `history` is a list of {"role", "content"} dicts."""
    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(history)
    messages.append({"role": "user", "content": user_message})

    response = _get_client().chat.completions.create(
        model=MODEL,
        messages=messages,
        temperature=0.7,
    )
    return response.choices[0].message.content or ""


def extract_params_from_message(user_message: str, current_params: dict) -> dict:
    """
    Extract trip parameters from user message, merged with current_params.
    Returns dict with keys: city, budget, days, origin_state, travel_date, travelers.
    City is validated and normalised against TREKKU_CITIES.
    """
    cities_str = ", ".join(TREKKU_CITIES)
    system = (
        "You are a parameter extractor for a Malaysian trip planning assistant. "
        "Extract trip parameters from the user message and merge with existing params. "
        f"Valid destination cities (must use exact spelling): {cities_str}. "
        "Common abbreviations: 'KL' = 'Kuala Lumpur', 'PJ' = 'Petaling Jaya', "
        "'Shah Alam' = 'Shah Alam', 'BB' = 'Bukit Bintang'. "
        "Return ONLY valid JSON with these exact keys: "
        "\"city\" (string matching one of the valid cities, or null), "
        "\"budget\" (float total trip budget in MYR, or null), "
        "\"days\" (integer number of days, or null), "
        "\"origin_state\" (Malaysian state or city the user is flying FROM, or null), "
        "\"travel_date\" (string YYYY-MM-DD or null), "
        "\"travelers\" (integer, default 1). "
        "Preserve existing non-null values from current_params if not overridden. "
        "Return null for unknown fields. Output JSON only, no explanation."
    )
    context = f"current_params: {json.dumps(current_params)}\nuser_message: {user_message}"

    raw = call_llm(system, [], context)

    try:
        cleaned = re.sub(r"```(?:json)?|```", "", raw).strip()
        extracted = json.loads(cleaned)
    except (json.JSONDecodeError, ValueError):
        return dict(current_params)

    merged = dict(current_params)
    for key in ["city", "budget", "days", "origin_state", "travel_date", "travelers"]:
        val = extracted.get(key)
        if val is not None:
            merged[key] = val

    # Normalise and validate city
    if merged.get("city"):
        normalised = _CITIES_LOWER.get(merged["city"].lower())
        if normalised:
            merged["city"] = normalised
        else:
            merged["city"] = None

    return merged


def build_itinerary_system_prompt(trip_params: dict, kb_context: str, feedback_notes: str) -> str:
    """Return the system prompt for structured itinerary generation."""
    city = trip_params.get("city", "")
    budget = trip_params.get("budget", 0)
    days = trip_params.get("days", 1)
    origin = trip_params.get("origin_state", "")

    prompt = (
        f"You are Trekku, a Malaysian travel planning assistant. "
        f"Generate a {days}-day trip itinerary for {city} with a total budget of MYR {budget}. "
        + (f"The traveller is flying from {origin} to {city}. " if origin else "")
        + "Use ONLY hotels, attractions, and flights from the knowledge base provided below. "
        "Distribute attractions across days naturally. "
        "Ensure the total_estimated_cost fits within the budget. "
        "Return ONLY valid JSON with this exact structure:\n"
        "{\n"
        '  "days": [\n'
        '    {\n'
        '      "day": 1,\n'
        '      "hotel": {"hotel_id": "...", "name": "...", "price_per_night": 0.0},\n'
        '      "attractions": [{"attraction_id": "...", "name": "...", "estimated_duration": "..."}],\n'
        '      "notes": "..."\n'
        "    }\n"
        "  ],\n"
        '  "flight": {"flight_id": "...", "airline": "...", "flight_number": "...", "price": 0.0} or null,\n'
        '  "total_estimated_cost": 0.0\n'
        "}\n\n"
        f"Knowledge base:\n{kb_context}\n\n"
        + (f"Community feedback notes:\n{feedback_notes}\n" if feedback_notes else "")
        + "Output JSON only, no explanation."
    )
    return prompt


def parse_itinerary_json(raw_response: str) -> dict:
    """Extract and parse the JSON object from an LLM response string."""
    cleaned = re.sub(r"```(?:json)?|```", "", raw_response).strip()
    start = cleaned.find("{")
    end = cleaned.rfind("}") + 1
    if start == -1 or end == 0:
        raise ValueError("No JSON object found in LLM response")
    return json.loads(cleaned[start:end])


def generate_itinerary(destination: str, budget: float, days: int) -> list:
    """Backward-compatible stub. Calls the LLM with minimal context."""
    system = (
        "You are a travel assistant. Generate a day-by-day itinerary. "
        "Return a JSON array of day objects with keys: day, activities, notes."
    )
    user = f"Destination: {destination}, Budget: MYR {budget}, Days: {days}"
    raw = call_llm(system, [], user)
    try:
        cleaned = re.sub(r"```(?:json)?|```", "", raw).strip()
        result = json.loads(cleaned)
        return result if isinstance(result, list) else []
    except (json.JSONDecodeError, ValueError):
        return []


def rag_query(query: str, context_docs: list) -> str:
    """Answer a query using the provided context documents as grounding."""
    context_json = json.dumps(context_docs, ensure_ascii=False)
    system = (
        "You are a travel assistant. Answer the user's question based solely on "
        "the knowledge base documents provided. Be concise and helpful."
    )
    user = f"Knowledge base:\n{context_json}\n\nQuestion: {query}"
    return call_llm(system, [], user)
