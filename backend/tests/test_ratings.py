import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from main import app
    return TestClient(app)


# ── GET /ratings/cities ───────────────────────────────────────────────────────

def test_get_cities_returns_list_of_strings(client):
    resp = client.get("/ratings/cities")
    assert resp.status_code == 200
    cities = resp.json()
    assert isinstance(cities, list)
    assert len(cities) > 0
    assert all(isinstance(c, str) for c in cities)


def test_get_cities_contains_known_seed_cities(client):
    resp = client.get("/ratings/cities")
    cities = resp.json()
    assert "Kuala Lumpur" in cities
    assert "Shah Alam" in cities


# ── GET /ratings/entities ─────────────────────────────────────────────────────
# /entities reads from the source collections (hotels / attractions / flights)
# filtered server-side by city, NOT from the time-series rating_snapshots
# collection. This keeps reads bounded to a single city's entities instead of
# streaming the entire snapshot history on every request.

def test_get_entities_hotels_read_from_source_collection_by_city(client):
    mock_records = [
        {"hotel_id": "hotel_abc", "name": "Grand Hotel", "location": {"city": "Kuala Lumpur"},
         "price_per_night": {"min": 100, "max": 300, "currency": "MYR"}},
    ]
    with patch("routers.ratings.query_records", return_value=mock_records) as q:
        resp = client.get("/ratings/entities?entity_type=hotels&city=Kuala+Lumpur")
    assert resp.status_code == 200
    assert resp.json() == [
        # price is the midpoint of the {min, max} nightly range.
        {"entity_id": "hotel_abc", "name": "Grand Hotel", "city": "Kuala Lumpur", "price": 200}
    ]
    # Server-side filter on the source collection — no snapshot scan.
    q.assert_called_once_with("hotels", "location.city", "==", "Kuala Lumpur")


def test_get_entities_attraction_price_is_null(client):
    mock_records = [
        {"attraction_id": "attr_1", "name": "Twin Towers", "location": {"city": "Kuala Lumpur"}},
    ]
    with patch("routers.ratings.query_records", return_value=mock_records):
        resp = client.get("/ratings/entities?entity_type=attractions&city=Kuala+Lumpur")
    assert resp.status_code == 200
    assert resp.json()[0]["price"] is None


def test_get_entities_flight_price_is_cheapest_in_bucket(client):
    mock_records = [
        {"flight_id": "f1", "origin_state": "Penang", "airline": "MAS", "price": 320},
        {"flight_id": "f2", "origin_state": "Penang", "airline": "AirAsia", "price": 180},
    ]
    # Flights ignore the destination-city filter (all routes end in Selangor),
    # so the source rows are read with get_all_records, not query_records.
    with patch("routers.ratings.get_all_records", return_value=mock_records):
        resp = client.get("/ratings/entities?entity_type=flights&city=Penang")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["price"] == 180   # cheapest fare across the bucket's airlines


def test_get_entities_attractions_read_from_source_collection_by_city(client):
    mock_records = [
        {"attraction_id": "attr_1", "name": "Twin Towers", "location": {"city": "Kuala Lumpur"}},
    ]
    with patch("routers.ratings.query_records", return_value=mock_records) as q:
        resp = client.get("/ratings/entities?entity_type=attractions&city=Kuala+Lumpur")
    assert resp.status_code == 200
    assert resp.json()[0]["entity_id"] == "attr_1"
    q.assert_called_once_with("attractions", "location.city", "==", "Kuala Lumpur")


def test_get_entities_flights_bucket_by_origin_state(client):
    from knowledge_capture import generate_id
    # Multiple source flight rows for one origin collapse to a single route
    # entity (origin → Selangor), keyed by the same entity_id the snapshot
    # pipeline produces. Sentinel/_flags docs (no origin_state) are skipped.
    mock_records = [
        {"flight_id": "f1", "origin_state": "Penang", "airline": "AirAsia"},
        {"flight_id": "f2", "origin_state": "Penang", "airline": "MAS"},
        {"_ttl_sentinel": True, "ttl_expires": "2026-01-01T00:00:00+00:00"},
        {"seeded": True},
    ]
    with patch("routers.ratings.get_all_records", return_value=mock_records) as q:
        resp = client.get("/ratings/entities?entity_type=flights&city=Penang")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["entity_id"] == generate_id("flight", "Penang", "selangor")
    # Routes render as "<origin> → Selangor"; destination is always Selangor.
    assert data[0]["name"] == "Penang → Selangor"
    assert data[0]["city"] == "Selangor"
    q.assert_called_once_with("flights")


def test_get_entities_returns_400_for_invalid_entity_type(client):
    resp = client.get("/ratings/entities?entity_type=invalid&city=KL")
    assert resp.status_code == 400


def test_get_entities_deduplicates_by_entity_id(client):
    mock_records = [
        {"hotel_id": "hotel_abc", "name": "Grand Hotel", "location": {"city": "Kuala Lumpur"}},
        {"hotel_id": "hotel_abc", "name": "Grand Hotel", "location": {"city": "Kuala Lumpur"}},
    ]
    with patch("routers.ratings.query_records", return_value=mock_records):
        resp = client.get("/ratings/entities?entity_type=hotels&city=Kuala+Lumpur")
    assert resp.status_code == 200
    assert len(resp.json()) == 1


# ── Firestore quota / outage handling ─────────────────────────────────────────

def test_resource_exhausted_returns_503(client):
    from google.api_core.exceptions import ResourceExhausted
    with patch("routers.ratings.query_records", side_effect=ResourceExhausted("Quota exceeded.")):
        resp = client.get("/ratings/entities?entity_type=hotels&city=Kuala+Lumpur")
    assert resp.status_code == 503
    assert "detail" in resp.json()


def test_service_unavailable_returns_503(client):
    from google.api_core.exceptions import ServiceUnavailable
    with patch("routers.ratings.query_records", side_effect=ServiceUnavailable("backend unavailable")):
        resp = client.get("/ratings/entities?entity_type=hotels&city=Kuala+Lumpur")
    assert resp.status_code == 503


# ── GET /ratings/trend ────────────────────────────────────────────────────────

def test_get_trend_returns_data_sorted_by_date(client):
    mock_records = [
        {"entity_id": "hotel_abc", "entity_type": "hotels", "name": "Grand Hotel",
         "city": "KL", "date": "2026-05-17", "rating": 4.5, "review_count": 100},
        {"entity_id": "hotel_abc", "entity_type": "hotels", "name": "Grand Hotel",
         "city": "KL", "date": "2026-05-16", "rating": 4.4, "review_count": 95},
    ]
    with patch("routers.ratings.query_records", return_value=mock_records):
        resp = client.get("/ratings/trend/hotels/hotel_abc")
    assert resp.status_code == 200
    body = resp.json()
    dates = [p["date"] for p in body["data"]]
    assert dates == sorted(dates)


def test_get_trend_respects_from_to_date_filters(client):
    mock_records = [
        {"entity_id": "h1", "entity_type": "hotels", "name": "H", "city": "KL",
         "date": "2026-04-01", "rating": 4.0, "review_count": 50},
        {"entity_id": "h1", "entity_type": "hotels", "name": "H", "city": "KL",
         "date": "2026-05-01", "rating": 4.2, "review_count": 60},
        {"entity_id": "h1", "entity_type": "hotels", "name": "H", "city": "KL",
         "date": "2026-05-17", "rating": 4.5, "review_count": 70},
    ]
    with patch("routers.ratings.query_records", return_value=mock_records):
        resp = client.get("/ratings/trend/hotels/h1?from=2026-05-01&to=2026-05-17")
    assert resp.status_code == 200
    dates = [p["date"] for p in resp.json()["data"]]
    assert "2026-04-01" not in dates
    assert len(dates) == 2


def test_get_trend_returns_404_for_missing_entity(client):
    with patch("routers.ratings.query_records", return_value=[]):
        resp = client.get("/ratings/trend/hotels/nonexistent_id")
    assert resp.status_code == 404


def test_get_trend_returns_400_for_invalid_entity_type(client):
    resp = client.get("/ratings/trend/invalid/some_id")
    assert resp.status_code == 400


def test_get_trend_response_contains_entity_metadata(client):
    mock_records = [
        {"entity_id": "hotel_abc", "entity_type": "hotels", "name": "Grand Hotel",
         "city": "Kuala Lumpur", "date": "2026-05-17", "rating": 4.5, "review_count": 100},
    ]
    with patch("routers.ratings.query_records", return_value=mock_records):
        resp = client.get("/ratings/trend/hotels/hotel_abc")
    body = resp.json()
    assert body["entity_id"] == "hotel_abc"
    assert body["name"] == "Grand Hotel"
    assert body["city"] == "Kuala Lumpur"
    assert len(body["data"]) == 1
    assert body["data"][0]["rating"] == 4.5
