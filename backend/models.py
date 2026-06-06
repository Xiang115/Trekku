from pydantic import BaseModel
from typing import Optional, List


# ─── SHARED ──────────────────────────────────────────

class Location(BaseModel):
    city: str
    country: str = "Malaysia"
    lat: Optional[float] = None
    lng: Optional[float] = None


# ─── HOTEL ───────────────────────────────────────────

class PricePerNight(BaseModel):
    min: float
    max: float
    currency: str = "MYR"


class Hotel(BaseModel):
    hotel_id: str
    name: str
    location: Location
    price_per_night: PricePerNight
    rating: Optional[float] = None
    amenities: List[str] = []
    category: str                    # "budget" | "mid-range" | "luxury"
    last_updated: str                # ISO timestamp
    ttl_expires: str                 # ISO timestamp
    source: str = "serpapi_hotels"


# ─── ATTRACTION / POI ────────────────────────────────

class Attraction(BaseModel):
    attraction_id: str
    name: str
    location: Location
    category: Optional[str] = None
    opening_hours: Optional[str] = None
    estimated_duration: Optional[str] = None
    popularity_score: float = 0.0
    last_updated: str
    ttl_expires: str
    source: str = "serpapi_attractions"


# ─── FLIGHT ──────────────────────────────────────────

class Flight(BaseModel):
    flight_id: str
    origin_state: str
    origin_iata: str
    airline: str
    flight_number: str
    price: float
    location: Location
    last_updated: str
    ttl_expires: str
    destination: str = "Selangor"
    destination_iata: str = "KUL"
    currency: str = "MYR"
    source: str = "serpapi_flights"
    departure_time: Optional[str] = None
    arrival_time: Optional[str] = None
    duration_minutes: Optional[int] = None


# ─── TRENDING TOPIC ──────────────────────────────────

class TrendingTopic(BaseModel):
    topic_name: str
    search_count: int = 0
    last_reset: str
    last_fetched: Optional[str] = None


# ─── QUOTA TRACKER ───────────────────────────────────

class QuotaTracker(BaseModel):
    key_id: str  # "key_1" to "key_5"
    used: int = 0
    limit: int = 250
    reset_date: str


# ─── SYSTEM FLAG ─────────────────────────────────────

class SystemFlag(BaseModel):
    seeded: bool = False
    seeded_at: Optional[str] = None


# ─── RATING SNAPSHOTS ────────────────────────────────

class RatingSnapshot(BaseModel):
    entity_id: str
    entity_type: str                        # "hotels" | "attractions" | "flights"
    name: str
    city: str
    date: str                               # "YYYY-MM-DD"
    captured_at: str                        # ISO 8601 UTC datetime
    rating: Optional[float] = None
    review_count: Optional[int] = None
    price_min: Optional[float] = None


class TrendPoint(BaseModel):
    date: str                               # "YYYY-MM-DD"
    rating: Optional[float] = None
    review_count: Optional[int] = None
    price_min: Optional[float] = None


class TrendResponse(BaseModel):
    entity_id: str
    entity_type: str
    name: str
    city: str
    from_date: Optional[str] = None
    to_date: Optional[str] = None
    data: List[TrendPoint]


class EntitySummary(BaseModel):
    entity_id: str
    name: str
    city: str
    # Representative price for swap previews: hotel nightly midpoint, flight fare,
    # or None for attractions (which carry no price in the knowledge base).
    price: Optional[float] = None


# ─── AGENT / ITINERARY ───────────────────────────────

class TripParams(BaseModel):
    origin_state: Optional[str] = None
    city: Optional[str] = None
    budget: Optional[float] = None
    days: Optional[int] = None
    travel_date: Optional[str] = None
    travelers: int = 1


class ConversationTurn(BaseModel):
    role: str           # "user" | "assistant"
    content: str
    timestamp: str


class AgentSession(BaseModel):
    session_id: str
    created_at: str
    updated_at: str
    trip_params: TripParams
    conversation: List[ConversationTurn] = []
    last_itinerary_id: Optional[str] = None
    status: str = "active"


class ItineraryDay(BaseModel):
    day: int
    hotel: Optional[dict] = None
    attractions: List[dict] = []
    notes: str = ""


class ItineraryContent(BaseModel):
    days: List[ItineraryDay]
    flight: Optional[dict] = None
    # AI-estimated whole-trip costs the knowledge base can't price deterministically.
    estimated_meals_cost: float = 0.0
    estimated_transport_cost: float = 0.0
    total_estimated_cost: float = 0.0


class GeneratedItinerary(BaseModel):
    itinerary_id: str
    session_id: str
    created_at: str
    city: str
    days: int
    budget: float
    travel_date: Optional[str] = None
    content: ItineraryContent
    raw_llm_response: str = ""
    kb_context_snapshot: str = ""


class TacitFeedback(BaseModel):
    feedback_id: str
    itinerary_id: str
    session_id: str
    created_at: str
    feedback_type: str   # "explicit_rating" | "explicit_text" | "implicit_modification"
    entity_type: Optional[str] = None
    entity_id: Optional[str] = None
    signal: float        # -1.0 to 1.0
    details: dict = {}


# ─── AGENT API REQUEST / RESPONSE ────────────────────

class ChatRequest(BaseModel):
    session_id: Optional[str] = None
    message: str


class ChatResponse(BaseModel):
    session_id: str
    reply: str
    itinerary_id: Optional[str] = None
    params_collected: dict
    itinerary: Optional[dict] = None


class FeedbackRequest(BaseModel):
    itinerary_id: str
    entity_id: Optional[str] = None
    entity_type: Optional[str] = None
    rating: Optional[int] = None   # 1-5 stars, mapped to signal
    comment: Optional[str] = None
    signal: float = 0.0            # direct override if rating not provided


class ModifyRequest(BaseModel):
    itinerary_id: str
    original_entity_id: str
    replacement_entity_id: str
    entity_type: str
