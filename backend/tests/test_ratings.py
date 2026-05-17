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

def test_get_entities_filters_by_city(client):
    mock_records = [
        {"entity_id": "hotel_abc", "entity_type": "hotels", "name": "Grand Hotel", "city": "Kuala Lumpur", "date": "2026-05-17"},
        {"entity_id": "hotel_def", "entity_type": "hotels", "name": "Budget Inn", "city": "Shah Alam", "date": "2026-05-17"},
    ]
    with patch("routers.ratings.query_records", return_value=mock_records):
        resp = client.get("/ratings/entities?entity_type=hotels&city=Kuala+Lumpur")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["entity_id"] == "hotel_abc"


def test_get_entities_returns_400_for_invalid_entity_type(client):
    resp = client.get("/ratings/entities?entity_type=invalid&city=KL")
    assert resp.status_code == 400


def test_get_entities_deduplicates_by_entity_id(client):
    mock_records = [
        {"entity_id": "hotel_abc", "entity_type": "hotels", "name": "Grand Hotel", "city": "Kuala Lumpur", "date": "2026-05-16"},
        {"entity_id": "hotel_abc", "entity_type": "hotels", "name": "Grand Hotel", "city": "Kuala Lumpur", "date": "2026-05-17"},
    ]
    with patch("routers.ratings.query_records", return_value=mock_records):
        resp = client.get("/ratings/entities?entity_type=hotels&city=Kuala+Lumpur")
    assert resp.status_code == 200
    assert len(resp.json()) == 1


def test_get_entities_city_filter_is_case_insensitive(client):
    mock_records = [
        {"entity_id": "hotel_abc", "entity_type": "hotels", "name": "Grand Hotel", "city": "Kuala Lumpur", "date": "2026-05-17"},
    ]
    with patch("routers.ratings.query_records", return_value=mock_records):
        resp = client.get("/ratings/entities?entity_type=hotels&city=kuala+lumpur")
    assert resp.status_code == 200
    assert len(resp.json()) == 1


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
