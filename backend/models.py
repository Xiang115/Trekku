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
