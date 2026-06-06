import os
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock

from knowledge_capture import (
    generate_id,
    ttl_checker,
    quota_tracker,
    trend_tracker,
    fetch_and_parse,
    store_to_firebase,
    seed_database,
    capture,
    TREKKU_SEED,
    _write_ttl_sentinel,
    _reset_monthly_quota,
    refresh_all,
)


@pytest.fixture(autouse=True)
def clear_conv_cache():
    from knowledge_capture import _conv_cache
    _conv_cache.clear()
    yield
    _conv_cache.clear()


# ── generate_id ───────────────────────────────────────────────────────────────

def test_generate_id_is_deterministic():
    assert generate_id("hotel", "Test Hotel", "KL") == generate_id("hotel", "Test Hotel", "KL")


def test_generate_id_prefix_matches_entity_type():
    assert generate_id("hotel", "Place", "KL").startswith("hotel_")
    assert generate_id("attraction", "Place", "KL").startswith("attraction_")


def test_generate_id_different_types_produce_different_ids():
    assert generate_id("hotel", "Place", "KL") != generate_id("attraction", "Place", "KL")


# ── ttl_checker ───────────────────────────────────────────────────────────────

def test_ttl_checker_returns_fresh_for_future_expiry():
    future = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    with patch("knowledge_capture.get_record", return_value={"ttl_expires": future}):
        assert ttl_checker("some_id", "hotels") == "FRESH"


def test_ttl_checker_returns_stale_for_past_expiry():
    past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    with patch("knowledge_capture.get_record", return_value={"ttl_expires": past}):
        assert ttl_checker("some_id", "hotels") == "STALE"


def test_ttl_checker_returns_not_found_when_no_record():
    with patch("knowledge_capture.get_record", return_value=None):
        assert ttl_checker("missing_id", "hotels") == "NOT_FOUND"


# ── quota_tracker ─────────────────────────────────────────────────────────────

def test_quota_tracker_returns_key1_when_available():
    with patch("knowledge_capture.get_record", return_value={"used": 0, "limit": 100}):
        with patch.dict(os.environ, {"SERPAPI_KEY_1": "test_key_1"}):
            api_key, key_id = quota_tracker()
    assert api_key == "test_key_1"
    assert key_id == "key_1"


def test_quota_tracker_skips_exhausted_key1_and_returns_key2():
    def get_record_side(collection, doc_id):
        if doc_id == "key_1":
            return {"used": 100, "limit": 100}
        if doc_id == "key_2":
            return {"used": 0, "limit": 100}
        return {"used": 100, "limit": 100}

    with patch("knowledge_capture.get_record", side_effect=get_record_side):
        with patch.dict(os.environ, {"SERPAPI_KEY_1": "test_key_1", "SERPAPI_KEY_2": "test_key_2"}):
            api_key, key_id = quota_tracker()
    assert api_key == "test_key_2"
    assert key_id == "key_2"


def test_quota_tracker_returns_fallback_when_all_keys_exhausted():
    with patch("knowledge_capture.get_record", return_value={"used": 100, "limit": 100}):
        with patch.dict(os.environ, {"SERPAPI_KEY_1": "test_key_1"}):
            api_key, key_id = quota_tracker()
    assert api_key == "FALLBACK"
    assert key_id is None


def test_quota_tracker_skips_key_with_empty_env_var():
    """Stale Firestore record exists for a key whose GitHub secret was removed."""
    def get_record_side(collection, doc_id):
        if doc_id == "key_2":
            return {"used": 0, "limit": 250}
        return None

    with patch("knowledge_capture.get_record", side_effect=get_record_side), \
         patch("knowledge_capture.set_record"):
        with patch.dict(os.environ, {"SERPAPI_KEY_1": "", "SERPAPI_KEY_2": "real_key_2"}):
            api_key, key_id = quota_tracker()
    assert api_key == "real_key_2"
    assert key_id == "key_2"


def test_quota_tracker_auto_initialises_missing_record():
    """If a key has a valid env var but no Firestore record, it creates one and returns the key."""
    with patch("knowledge_capture.get_record", return_value=None) as mock_get, \
         patch("knowledge_capture.set_record") as mock_set:
        with patch.dict(os.environ, {"SERPAPI_KEY_1": "auto_key"}):
            api_key, key_id = quota_tracker()

    assert api_key == "auto_key"
    assert key_id == "key_1"
    mock_set.assert_called_once()
    created = mock_set.call_args.args[2]
    assert created["used"] == 0
    assert created["limit"] == 250
    assert created["reset_date"].endswith("-01")


# ── trend_tracker ─────────────────────────────────────────────────────────────

def test_trend_tracker_returns_ok_when_count_below_threshold():
    recent = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
    record = {"search_count": 5, "last_reset": recent, "last_fetched": None}
    with patch("knowledge_capture.get_record", return_value=record):
        with patch("knowledge_capture.update_record"):
            assert trend_tracker("Petronas", "some_id", "attractions") == "OK"


def test_trend_tracker_returns_refetch_when_count_high_and_ttl_stale():
    recent = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
    past_ttl = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    topic_record = {"search_count": 9, "last_reset": recent, "last_fetched": None}
    entity_record = {"ttl_expires": past_ttl}

    def get_record_side(collection, doc_id):
        if collection == "trending_topics":
            return topic_record
        return entity_record

    with patch("knowledge_capture.get_record", side_effect=get_record_side):
        with patch("knowledge_capture.update_record"):
            assert trend_tracker("Petronas", "some_id", "attractions") == "REFETCH"


def test_trend_tracker_returns_ok_when_count_high_but_ttl_fresh():
    recent = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
    future_ttl = (datetime.now(timezone.utc) + timedelta(days=10)).isoformat()
    topic_record = {"search_count": 9, "last_reset": recent, "last_fetched": None}
    entity_record = {"ttl_expires": future_ttl}

    def get_record_side(collection, doc_id):
        if collection == "trending_topics":
            return topic_record
        return entity_record

    with patch("knowledge_capture.get_record", side_effect=get_record_side):
        with patch("knowledge_capture.update_record"):
            assert trend_tracker("Petronas", "some_id", "attractions") == "OK"


def test_trend_tracker_creates_new_document_when_topic_not_found():
    with patch("knowledge_capture.get_record", return_value=None):
        with patch("knowledge_capture.set_record") as mock_set:
            result = trend_tracker("NewPlace", "some_id", "hotels")
    assert result == "OK"
    mock_set.assert_called_once()
    call_data = mock_set.call_args[0][2]
    assert call_data["search_count"] == 1
    assert call_data["last_fetched"] is None


# ── fetch_and_parse ───────────────────────────────────────────────────────────

def test_fetch_and_parse_hotel_returns_list_with_correct_schema():
    mock_client = MagicMock()
    mock_client.search.return_value = {
        "properties": [
            {
                "name": "Grand Hotel",
                "rate_per_night": {"extracted_lowest": 200, "extracted_highest": 350},
                "gps_coordinates": {"latitude": 3.1, "longitude": 101.7},
                "overall_rating": 4.5,
                "amenities": ["WiFi"],
            },
            {
                "name": "Budget Inn",
                "rate_per_night": {"extracted_lowest": 80, "extracted_highest": 120},
                "gps_coordinates": {},
                "overall_rating": 3.8,
                "amenities": [],
            },
        ]
    }
    with patch("knowledge_capture.serpapi.Client", return_value=mock_client):
        results = fetch_and_parse("Kuala Lumpur", "hotels", "fake_key")
    assert isinstance(results, list)
    assert len(results) == 2
    assert set(results[0].keys()) == {"hotel_id", "name", "location", "price_per_night", "rating", "review_count", "amenities", "category"}
    assert results[0]["name"] == "Grand Hotel"
    assert results[0]["category"] == "mid-range"
    assert results[1]["category"] == "budget"


def test_fetch_and_parse_excludes_sponsored_hotel():
    mock_client = MagicMock()
    mock_client.search.return_value = {
        "properties": [
            {"name": "Ads Hotel", "sponsored": True},
            {
                "name": "Real Hotel",
                "rate_per_night": {"extracted_lowest": 100, "extracted_highest": 150},
                "gps_coordinates": {},
                "overall_rating": 4.0,
                "amenities": [],
            }
        ]
    }
    with patch("knowledge_capture.serpapi.Client", return_value=mock_client):
        results = fetch_and_parse("KL", "hotels", "fake_key")
    assert results is not None
    assert len(results) == 1
    assert results[0]["name"] == "Real Hotel"


def test_fetch_and_parse_returns_none_when_response_is_empty():
    mock_client = MagicMock()
    mock_client.search.return_value = {"properties": []}
    with patch("knowledge_capture.serpapi.Client", return_value=mock_client):
        result = fetch_and_parse("KL", "hotels", "fake_key")
    assert result is None


def test_fetch_and_parse_returns_none_on_request_exception():
    with patch("knowledge_capture.serpapi.Client", side_effect=Exception("timeout")):
        result = fetch_and_parse("KL", "hotels", "fake_key")
    assert result is None


def test_fetch_and_parse_flight_returns_per_flight_records():
    mock_client = MagicMock()
    mock_client.search.return_value = {
        "best_flights": [
            {
                "flights": [
                    {
                        "departure_airport": {"name": "Senai Int'l", "id": "JHB", "time": "2026-05-19 07:00"},
                        "arrival_airport": {"name": "KLIA2", "id": "KUL", "time": "2026-05-19 08:05"},
                        "airline": "AirAsia",
                        "flight_number": "AK 111",
                    }
                ],
                "total_duration": 65,
                "price": 89,
            },
            {
                "flights": [
                    {
                        "departure_airport": {"name": "Senai Int'l", "id": "JHB", "time": "2026-05-19 12:00"},
                        "arrival_airport": {"name": "KLIA2", "id": "KUL", "time": "2026-05-19 13:10"},
                        "airline": "MAS",
                        "flight_number": "MH 222",
                    }
                ],
                "total_duration": 70,
                "price": 150,
            },
        ]
    }
    with patch("knowledge_capture.serpapi.Client", return_value=mock_client):
        results = fetch_and_parse("Johor Bahru", "flights", "fake_key", iata="JHB")

    assert isinstance(results, list)
    assert len(results) == 2
    first = results[0]
    assert first["departure_time"] == "2026-05-19 07:00"
    assert first["arrival_time"] == "2026-05-19 08:05"
    assert first["airline"] == "AirAsia"
    assert first["flight_number"] == "AK 111"
    assert first["duration_minutes"] == 65
    assert first["price"] == 89
    assert first["currency"] == "MYR"
    assert first["origin_iata"] == "JHB"
    assert first["destination_iata"] == "KUL"
    assert "price_range" not in first


# ── store_to_firebase ─────────────────────────────────────────────────────────

def test_store_to_firebase_record_contains_last_updated():
    record = {"hotel_id": "hotel_abc", "name": "Test"}
    with patch("knowledge_capture.set_record"):
        with patch("knowledge_capture.get_record", return_value={"used": 5, "limit": 100}):
            with patch("knowledge_capture.update_record"):
                store_to_firebase(record, "hotels", "hotels", "hotel_id")
    assert "last_updated" in record


def test_store_to_firebase_record_contains_ttl_expires():
    record = {"hotel_id": "hotel_abc", "name": "Test"}
    with patch("knowledge_capture.set_record"):
        with patch("knowledge_capture.get_record", return_value={"used": 5, "limit": 100}):
            with patch("knowledge_capture.update_record"):
                store_to_firebase(record, "hotels", "hotels", "hotel_id")
    assert "ttl_expires" in record


def test_store_to_firebase_second_call_uses_set_record_not_create():
    record = {"hotel_id": "hotel_abc", "name": "Test"}
    with patch("knowledge_capture.set_record") as mock_set:
        with patch("knowledge_capture.get_record", return_value={"used": 5, "limit": 100}):
            with patch("knowledge_capture.update_record"):
                store_to_firebase(dict(record), "hotels", "hotels", "hotel_id")
                store_to_firebase(dict(record), "hotels", "hotels", "hotel_id")
    assert mock_set.call_count == 2


def test_store_to_firebase_returns_false_on_write_failure():
    record = {"hotel_id": "hotel_abc", "name": "Test"}
    with patch("knowledge_capture.set_record", side_effect=Exception("Firebase error")):
        result = store_to_firebase(record, "hotels", "hotels", "hotel_id")
    assert result is False


# ── seed_database ─────────────────────────────────────────────────────────────

def test_seed_database_skips_already_seeded_collection():
    with patch("knowledge_capture.get_record", return_value={"seeded": True, "ttl_expires": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()}):
        with patch("knowledge_capture.fetch_and_parse") as mock_fetch:
            seed_database()
    mock_fetch.assert_not_called()


def test_seed_database_stops_when_quota_returns_fallback():
    def get_record_side(collection, doc_id):
        if collection == "quota_tracker":
            return {"used": 100, "limit": 100}
        if doc_id == "_flags":
            return None
        return None

    with patch("knowledge_capture.get_record", side_effect=get_record_side):
        with patch("knowledge_capture.fetch_and_parse") as mock_fetch:
            with patch("knowledge_capture.set_record") as mock_set:
                seed_database()

    mock_fetch.assert_not_called()
    flag_calls = [c for c in mock_set.call_args_list if c[0][1] == "_flags"]
    assert len(flag_calls) == 0


def test_seed_database_sets_seeded_flag_after_each_collection():
    set_calls = []
    fake_item = {"hotel_id": "h1", "attraction_id": "a1", "flight_id": "f1"}

    def get_record_side(collection, doc_id):
        if collection == "quota_tracker" and doc_id == "key_1":
            return {"used": 0, "limit": 100}
        if collection == "quota_tracker":
            return {"used": 100, "limit": 100}
        if doc_id == "_flags":
            return None
        return None

    with patch("knowledge_capture.get_record", side_effect=get_record_side):
        with patch("knowledge_capture.set_record", side_effect=lambda c, d, data: set_calls.append((c, d, data))):
            with patch("knowledge_capture.update_record"):
                with patch("knowledge_capture.fetch_and_parse", return_value=[fake_item]):
                    with patch.dict(os.environ, {"SERPAPI_KEY_1": "key"}):
                        seed_database()

    flag_calls = [(c, d, data) for c, d, data in set_calls if d == "_flags"]
    assert len(flag_calls) == 3
    for _, _, data in flag_calls:
        assert data["seeded"] is True


def test_seed_database_seeds_attractions_by_city():
    fetched = []

    def get_record_side(collection, doc_id):
        if collection == "quota_tracker" and doc_id == "key_1":
            return {"used": 0, "limit": 100}
        if collection == "quota_tracker":
            return {"used": 100, "limit": 100}
        if doc_id == "_flags":
            if collection in ("hotels", "flights"):
                return {"seeded": True, "ttl_expires": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()}
            return None
        return None

    def fetch_side(query, entity_type, api_key, iata=None):
        if entity_type == "attractions":
            fetched.append(query)
        return None

    with patch("knowledge_capture.get_record", side_effect=get_record_side):
        with patch("knowledge_capture.set_record"):
            with patch("knowledge_capture.update_record"):
                with patch("knowledge_capture.fetch_and_parse", side_effect=fetch_side):
                    with patch.dict(os.environ, {"SERPAPI_KEY_1": "key"}):
                        seed_database()

    assert fetched == TREKKU_SEED["cities"]


# ── capture ───────────────────────────────────────────────────────────────────

def test_capture_returns_fresh_list_with_data_freshness_flag():
    future_ttl = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    sentinel = {"ttl_expires": future_ttl, "_ttl_sentinel": True}
    hotel_records = [
        {"hotel_id": "hotel_abc", "name": "Hotel A", "location": {"city": "KL"}},
        {"hotel_id": "hotel_def", "name": "Hotel B", "location": {"city": "KL"}},
    ]

    def get_record_side(collection, doc_id):
        if collection == "trending_topics":
            return None
        return sentinel

    with patch("knowledge_capture.get_record", side_effect=get_record_side):
        with patch("knowledge_capture.set_record"):
            with patch("knowledge_capture.query_records", return_value=hotel_records + [sentinel]):
                results = capture("KL", "hotels", city="KL")

    assert isinstance(results, list)
    assert len(results) == 2
    assert all(r["data_freshness"] == "fresh" for r in results)


def test_capture_returns_stale_list_when_quota_fallback():
    past_ttl = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    sentinel = {"ttl_expires": past_ttl, "_ttl_sentinel": True}
    stale_records = [{"hotel_id": "hotel_abc", "name": "Test Hotel", "location": {"city": "KL"}}]

    def get_record_side(collection, doc_id):
        if collection == "trending_topics":
            return None
        if collection == "quota_tracker":
            return {"used": 100, "limit": 100}
        return sentinel

    with patch("knowledge_capture.get_record", side_effect=get_record_side):
        with patch("knowledge_capture.set_record"):
            with patch("knowledge_capture.query_records", return_value=stale_records):
                results = capture("KL", "hotels", city="KL")

    assert results is not None
    assert all(r["data_freshness"] == "stale" for r in results)


def test_capture_returns_none_when_fallback_and_no_firebase_record():
    past_ttl = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    sentinel = {"ttl_expires": past_ttl, "_ttl_sentinel": True}

    def get_record_side(collection, doc_id):
        if collection == "trending_topics":
            return None
        if collection == "quota_tracker":
            return {"used": 100, "limit": 100}
        return sentinel

    with patch("knowledge_capture.get_record", side_effect=get_record_side):
        with patch("knowledge_capture.set_record"):
            with patch("knowledge_capture.query_records", return_value=[]):
                result = capture("Unknown", "hotels", city="Unknown")

    assert result is None


def test_capture_calls_fetch_and_parse_when_ttl_is_stale():
    past_ttl = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    sentinel = {"ttl_expires": past_ttl, "_ttl_sentinel": True}

    def get_record_side(collection, doc_id):
        if collection == "trending_topics":
            return None
        if collection == "quota_tracker" and doc_id == "key_1":
            return {"used": 0, "limit": 100}
        if collection == "quota_tracker":
            return {"used": 100, "limit": 100}
        return sentinel

    with patch("knowledge_capture.get_record", side_effect=get_record_side):
        with patch("knowledge_capture.set_record"):
            with patch("knowledge_capture.update_record"):
                with patch("knowledge_capture.fetch_and_parse", return_value=None) as mock_fetch:
                    with patch.dict(os.environ, {"SERPAPI_KEY_1": "test_key"}):
                        capture("KL", "hotels", city="KL")

    mock_fetch.assert_called_once()


# ── _reset_monthly_quota ──────────────────────────────────────────────────────

def test_reset_monthly_quota_zeroes_used_for_all_active_keys():
    def get_record_side(collection, doc_id):
        if collection == "quota_tracker":
            return {"key_id": doc_id, "used": 80, "limit": 250, "reset_date": "2026-06-01"}
        return None

    with patch("knowledge_capture.get_record", side_effect=get_record_side), \
         patch("knowledge_capture.update_record") as mock_update:
        _reset_monthly_quota()

    assert mock_update.call_count == 5
    for call in mock_update.call_args_list:
        update_fields = call.args[2]
        assert update_fields["used"] == 0
        assert update_fields["reset_date"].endswith("-01")  # always first of the month


def test_reset_monthly_quota_skips_keys_with_no_record():
    def get_record_side(collection, doc_id):
        if doc_id == "key_1":
            return {"key_id": "key_1", "used": 50, "limit": 250, "reset_date": "2026-06-01"}
        return None

    with patch("knowledge_capture.get_record", side_effect=get_record_side), \
         patch("knowledge_capture.update_record") as mock_update:
        _reset_monthly_quota()

    assert mock_update.call_count == 1
    assert mock_update.call_args.args[1] == "key_1"
    update_fields = mock_update.call_args.args[2]
    assert update_fields["used"] == 0
    assert update_fields["reset_date"].endswith("-01")


# ── refresh_all ───────────────────────────────────────────────────────────────

def test_refresh_all_calls_fetch_for_every_seed_entry():
    def fake_fetch(query, entity_type, api_key, iata=None, travel_date=None):
        if entity_type == "hotels":
            return [{"hotel_id": f"hotel_{query}", "name": f"Hotel {query}"}]
        if entity_type == "attractions":
            return [{"attraction_id": f"attr_{query}", "name": f"Place {query}"}]
        if entity_type == "flights":
            return [{"flight_id": f"flight_{query}", "airline": "AirAsia"}]
        return None

    mock_dt = MagicMock()
    mock_dt.now.return_value.day = 15

    with patch("knowledge_capture.quota_tracker", return_value=("fake_key", "key_1")), \
         patch("knowledge_capture.fetch_and_parse", side_effect=fake_fetch) as mock_fetch, \
         patch("knowledge_capture.store_to_firebase", return_value=True), \
         patch("knowledge_capture._increment_quota"), \
         patch("knowledge_capture._write_ttl_sentinel") as mock_sentinel, \
         patch("knowledge_capture.capture_rating_snapshot", return_value=0), \
         patch("knowledge_capture.datetime", mock_dt):
        summary = refresh_all()

    hotel_calls = [c for c in mock_fetch.call_args_list if c.args[1] == "hotels"]
    attraction_calls = [c for c in mock_fetch.call_args_list if c.args[1] == "attractions"]
    flight_calls = [c for c in mock_fetch.call_args_list if c.args[1] == "flights"]

    assert len(hotel_calls) == len(TREKKU_SEED["cities"])
    assert len(attraction_calls) == len(TREKKU_SEED["cities"])
    assert len(flight_calls) == len(TREKKU_SEED["flight_origins"])
    assert summary["errors"] == 0

    flight_sentinel_ids = {
        c.args[1] for c in mock_sentinel.call_args_list if c.args[0] == "flights"
    }
    assert len(flight_sentinel_ids) == len(TREKKU_SEED["flight_origins"])


def test_refresh_all_counts_empty_results_as_empty_not_errors():
    """An empty fetch (no third-party results) is benign and must NOT fail the job."""
    mock_dt = MagicMock()
    mock_dt.now.return_value.day = 15

    with patch("knowledge_capture.quota_tracker", return_value=("fake_key", "key_1")), \
         patch("knowledge_capture.fetch_and_parse", return_value=None), \
         patch("knowledge_capture._increment_quota"), \
         patch("knowledge_capture._write_ttl_sentinel"), \
         patch("knowledge_capture.capture_rating_snapshot", return_value=0), \
         patch("knowledge_capture.datetime", mock_dt):
        summary = refresh_all()

    total_seed_entries = len(TREKKU_SEED["cities"]) * 2 + len(TREKKU_SEED["flight_origins"])
    assert summary["errors"] == 0
    assert summary["empty"] == total_seed_entries
    assert summary["hotels"] == 0
    assert summary["attractions"] == 0
    assert summary["flights"] == 0


def test_refresh_all_counts_store_failure_as_error():
    """A genuine Firebase write failure IS an error and must fail the job."""
    mock_dt = MagicMock()
    mock_dt.now.return_value.day = 15

    def fake_fetch(query, entity_type, api_key, iata=None, travel_date=None):
        return [{"hotel_id": "h1", "attraction_id": "a1", "flight_id": "f1", "name": query}]

    with patch("knowledge_capture.quota_tracker", return_value=("fake_key", "key_1")), \
         patch("knowledge_capture.fetch_and_parse", side_effect=fake_fetch), \
         patch("knowledge_capture.store_to_firebase", return_value=False), \
         patch("knowledge_capture._increment_quota"), \
         patch("knowledge_capture._write_ttl_sentinel"), \
         patch("knowledge_capture.capture_rating_snapshot", return_value=0), \
         patch("knowledge_capture.datetime", mock_dt):
        summary = refresh_all()

    assert summary["errors"] > 0
    assert summary["empty"] == 0


def test_refresh_all_stops_on_quota_fallback_without_calling_fetch():
    mock_dt = MagicMock()
    mock_dt.now.return_value.day = 15

    with patch("knowledge_capture.quota_tracker", return_value=("FALLBACK", None)), \
         patch("knowledge_capture.fetch_and_parse") as mock_fetch, \
         patch("knowledge_capture.capture_rating_snapshot", return_value=0), \
         patch("knowledge_capture.datetime", mock_dt):
        summary = refresh_all()

    mock_fetch.assert_not_called()
    assert summary["errors"] > 0


def test_refresh_all_calls_reset_on_first_of_month():
    mock_dt = MagicMock()
    mock_dt.now.return_value.day = 1

    with patch("knowledge_capture.quota_tracker", return_value=("fake_key", "key_1")), \
         patch("knowledge_capture.fetch_and_parse", return_value=None), \
         patch("knowledge_capture._increment_quota"), \
         patch("knowledge_capture._write_ttl_sentinel"), \
         patch("knowledge_capture._reset_monthly_quota") as mock_reset, \
         patch("knowledge_capture.capture_rating_snapshot", return_value=0), \
         patch("knowledge_capture.datetime", mock_dt):
        refresh_all()

    mock_reset.assert_called_once()


def test_refresh_all_does_not_reset_quota_mid_month():
    mock_dt = MagicMock()
    mock_dt.now.return_value.day = 15

    with patch("knowledge_capture.quota_tracker", return_value=("fake_key", "key_1")), \
         patch("knowledge_capture.fetch_and_parse", return_value=None), \
         patch("knowledge_capture._increment_quota"), \
         patch("knowledge_capture._write_ttl_sentinel"), \
         patch("knowledge_capture._reset_monthly_quota") as mock_reset, \
         patch("knowledge_capture.capture_rating_snapshot", return_value=0), \
         patch("knowledge_capture.datetime", mock_dt):
        refresh_all()

    mock_reset.assert_not_called()


# ── capture_rating_snapshot ───────────────────────────────────────────────────

def test_capture_rating_snapshot_hotel_writes_correct_fields():
    hotel_records = [{
        "hotel_id": "hotel_abc123",
        "name": "Grand Hotel",
        "location": {"city": "Kuala Lumpur"},
        "rating": 4.5,
        "review_count": 200,
    }]
    with patch("knowledge_capture.set_record") as mock_set:
        from knowledge_capture import capture_rating_snapshot
        count = capture_rating_snapshot(hotel_records, "hotels", "2026-05-17")
    assert count == 1
    call_args = mock_set.call_args
    assert call_args[0][0] == "rating_snapshots"
    assert call_args[0][1] == "hotel_abc123_2026-05-17"
    doc = call_args[0][2]
    assert doc["rating"] == 4.5
    assert doc["review_count"] == 200
    assert doc["date"] == "2026-05-17"
    assert doc["entity_type"] == "hotels"


def test_capture_rating_snapshot_attraction_maps_popularity_score():
    records = [{
        "attraction_id": "attraction_xyz",
        "name": "KLCC",
        "location": {"city": "KLCC"},
        "popularity_score": 4.8,
        "review_count": 5000,
    }]
    with patch("knowledge_capture.set_record") as mock_set:
        from knowledge_capture import capture_rating_snapshot
        capture_rating_snapshot(records, "attractions", "2026-05-17")
    doc = mock_set.call_args[0][2]
    assert doc["rating"] == 4.8
    assert doc["entity_type"] == "attractions"


def test_capture_rating_snapshot_flight_takes_min_price():
    records = [
        {"flight_id": "f1", "origin_state": "Johor Bahru", "flight_number": "AK 111", "price": 89},
        {"flight_id": "f2", "origin_state": "Johor Bahru", "flight_number": "MH 222", "price": 150},
    ]
    with patch("knowledge_capture.set_record") as mock_set:
        from knowledge_capture import capture_rating_snapshot
        count = capture_rating_snapshot(records, "flights", "2026-05-17")
    assert count == 1
    doc = mock_set.call_args[0][2]
    assert doc["price_min"] == 89
    assert doc["entity_type"] == "flights"


def test_capture_rating_snapshot_returns_zero_for_empty_input():
    with patch("knowledge_capture.set_record") as mock_set:
        from knowledge_capture import capture_rating_snapshot
        count = capture_rating_snapshot([], "hotels", "2026-05-17")
    assert count == 0
    mock_set.assert_not_called()


def test_capture_rating_snapshot_uses_idempotent_document_id():
    records = [{"hotel_id": "h1", "name": "H", "location": {"city": "KL"}, "rating": 4.0, "review_count": 10}]
    with patch("knowledge_capture.set_record") as mock_set:
        from knowledge_capture import capture_rating_snapshot
        capture_rating_snapshot(records, "hotels", "2026-05-17")
        capture_rating_snapshot(records, "hotels", "2026-05-17")
    assert mock_set.call_count == 2
    ids = [c[0][1] for c in mock_set.call_args_list]
    assert ids[0] == ids[1] == "h1_2026-05-17"
