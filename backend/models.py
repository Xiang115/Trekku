from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

# ─── HOTEL ───────────────────────────────────────────

class Location(BaseModel):
    city: str
    country: str = "Malaysia"
    lat: Optional[float] = None
    lng: Optional[float] = None

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
    category: str                    # "nature" | "cultural" | "entertainment"
    opening_hours: Optional[str] = None
    estimated_duration: Optional[str] = None   # e.g. "2-3 hours"
    popularity_score: float = 0.0   # seeded from Google review rating
    last_updated: str
    ttl_expires: str
    source: str = "serpapi_places"

# ─── FLIGHT ──────────────────────────────────────────

class FlightPriceRange(BaseModel):
    min: float
    max: float
    currency: str = "MYR"

class Flight(BaseModel):
    flight_id: str
    origin_state: str               # e.g. "Penang"
    origin_iata: str                # e.g. "PEN"
    destination: str = "Selangor"
    destination_iata: str = "KUL"
    price_range: FlightPriceRange
    duration: Optional[str] = None  # e.g. "1h 10m"
    last_updated: str
    ttl_expires: str
    source: str = "serpapi_flights"

# ─── TRENDING TOPIC ──────────────────────────────────

class TrendingTopic(BaseModel):
    topic_name: str
    search_count: int = 0
    last_reset: str                  # ISO timestamp
    last_fetched: Optional[str] = None

# ─── QUOTA TRACKER ───────────────────────────────────

class QuotaTracker(BaseModel):
    key_id: str                      # "key_1" to "key_5"
    used: int = 0
    limit: int = 100
    reset_date: str                  # e.g. "2026-06-01"

# ─── SYSTEM FLAG ─────────────────────────────────────

class SystemFlag(BaseModel):
    seeded: bool = False
    seeded_at: Optional[str] = None  # null until seed_database() completes