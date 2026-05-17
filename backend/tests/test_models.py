import pytest


def test_flight_model_accepts_individual_price_fields():
    from models import Flight, Location
    flight = Flight(
        flight_id="flight_abc123",
        origin_state="Johor Bahru",
        origin_iata="JHB",
        airline="AirAsia",
        flight_number="AK 6121",
        price=150.0,
        location=Location(city="Johor Bahru", country="Malaysia"),
        last_updated="2026-05-15T10:00:00+00:00",
        ttl_expires="2026-05-22T10:00:00+00:00",
    )
    assert flight.price == 150.0
    assert flight.airline == "AirAsia"
    assert flight.flight_number == "AK 6121"
    assert flight.duration_minutes is None


def test_flight_model_accepts_optional_time_fields():
    from models import Flight, Location
    flight = Flight(
        flight_id="flight_abc123",
        origin_state="Penang",
        origin_iata="PEN",
        airline="MAS",
        flight_number="MH 1234",
        price=200.0,
        departure_time="07:30 AM",
        arrival_time="08:40 AM",
        duration_minutes=70,
        location=Location(city="Penang", country="Malaysia"),
        last_updated="2026-05-15T10:00:00+00:00",
        ttl_expires="2026-05-22T10:00:00+00:00",
    )
    assert flight.departure_time == "07:30 AM"
    assert flight.duration_minutes == 70


def test_attraction_source_default_is_serpapi_attractions():
    from models import Attraction, Location
    attr = Attraction(
        attraction_id="attraction_xyz",
        name="Batu Caves",
        location=Location(city="Kuala Lumpur", country="Malaysia"),
        popularity_score=4.6,
        last_updated="2026-05-15T10:00:00+00:00",
        ttl_expires="2026-07-14T10:00:00+00:00",
    )
    assert attr.source == "serpapi_attractions"


def test_quota_tracker_default_limit_is_250():
    from models import QuotaTracker
    qt = QuotaTracker(key_id="key_1", reset_date="2026-06-01")
    assert qt.limit == 250


def test_flight_model_rejects_old_price_range_shape():
    from pydantic import ValidationError
    from models import Flight, Location
    with pytest.raises(ValidationError):
        Flight(
            flight_id="flight_abc",
            origin_state="Johor Bahru",
            origin_iata="JHB",
            price_range={"min": 100, "max": 200, "currency": "MYR"},
            location=Location(city="Johor Bahru", country="Malaysia"),
            last_updated="2026-05-15T10:00:00+00:00",
            ttl_expires="2026-05-22T10:00:00+00:00",
        )
