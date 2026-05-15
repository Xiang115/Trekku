import hashlib
import os
from datetime import date, datetime, timedelta, timezone

import serpapi

from database import get_record, set_record, update_record, query_records

TREKKU_SEED = {
    "cities": [
        "Shah Alam", "Petaling Jaya", "Klang",
        "Subang Jaya", "Sepang", "Puchong",
        "Kuala Lumpur", "Bukit Bintang", "KLCC"
    ],
    "flight_origins": [
        {"state": "Johor Bahru",       "iata": "JHB"},
        {"state": "Kota Kinabalu",     "iata": "BKI"},
        {"state": "Kuching",           "iata": "KCH"},
        {"state": "Penang",            "iata": "PEN"},
        {"state": "Langkawi",          "iata": "LGK"},
        {"state": "Kota Bharu",        "iata": "KBR"},
        {"state": "Kuala Terengganu",  "iata": "TGG"},
        {"state": "Alor Setar",        "iata": "AOR"},
        {"state": "Miri",              "iata": "MYY"},
        {"state": "Sibu",              "iata": "SBW"},
        {"state": "Sandakan",          "iata": "SDK"},
        {"state": "Tawau",             "iata": "TWU"}
    ]
}

TTL_DAYS = {
    "hotels":      7,
    "attractions": 60,
    "flights":     7
}

MAX_HORIZON_DAYS = {"hotels": 365, "flights": 330}

_conv_cache: dict = {}


def generate_id(entity_type: str, name: str, city: str) -> str:
    key = f"{name.strip().lower()}_{city.strip().lower()}"
    hash_hex = hashlib.md5(key.encode()).hexdigest()
    return f"{entity_type}_{hash_hex[:10]}"


def ttl_checker(entity_id: str, collection: str) -> str:
    record = get_record(collection, entity_id)
    if record is None:
        return "NOT_FOUND"
    ttl_expires = datetime.fromisoformat(record["ttl_expires"])
    if datetime.utcnow() > ttl_expires:
        return "STALE"
    return "FRESH"


def quota_tracker():
    for i in range(1, 6):
        key_id = f"key_{i}"
        record = get_record("quota_tracker", key_id)
        if record and record["used"] < record["limit"]:
            return (os.getenv(f"SERPAPI_KEY_{i}"), key_id)
    return ("FALLBACK", None)


def trend_tracker(topic_name: str, entity_id: str, collection: str) -> str:
    record = get_record("trending_topics", topic_name)
    if record is None:
        set_record("trending_topics", topic_name, {
            "search_count": 1,
            "last_reset": datetime.utcnow().isoformat(),
            "last_fetched": None,
        })
        return "OK"

    new_count = record["search_count"] + 1
    update_record("trending_topics", topic_name, {"search_count": new_count})

    last_reset = datetime.fromisoformat(record["last_reset"])
    within_7_days = (datetime.utcnow() - last_reset) <= timedelta(days=7)

    if new_count >= 10 and within_7_days:
        if ttl_checker(entity_id, collection) in ("STALE", "NOT_FOUND"):
            return "REFETCH"

    return "OK"


def fetch_and_parse(query: str, entity_type: str, api_key: str, iata: str = None, travel_date: str = None):
    try:
        client = serpapi.Client(api_key=api_key)
        if entity_type == "hotels":
            params = {
                "engine": "google_hotels",
                "q": f"{query} hotels",
                "check_in_date": travel_date if travel_date else (datetime.now(timezone.utc) + timedelta(days=1)).strftime("%Y-%m-%d"),
                "check_out_date": (date.fromisoformat(travel_date) + timedelta(days=1)).isoformat() if travel_date else (datetime.now(timezone.utc) + timedelta(days=2)).strftime("%Y-%m-%d"),
                "gl": "my",
            }
            data = client.search(params)

            results = []
            for prop in data.get("properties", []):
                if prop.get("sponsored"):
                    continue
                name = prop.get("name", "")
                price_min = prop.get("rate_per_night", {}).get("extracted_lowest", 0)
                price_max = prop.get("rate_per_night", {}).get("extracted_highest", price_min)
                if price_min < 150:
                    category = "budget"
                elif price_min <= 400:
                    category = "mid-range"
                else:
                    category = "luxury"
                coords = prop.get("gps_coordinates", {})
                results.append({
                    "hotel_id": generate_id("hotel", name, query),
                    "name": name,
                    "location": {
                        "city": query,
                        "country": "Malaysia",
                        "lat": coords.get("latitude"),
                        "lng": coords.get("longitude"),
                    },
                    "price_per_night": {"min": price_min, "max": price_max, "currency": "MYR"},
                    "rating": prop.get("overall_rating"),
                    "amenities": prop.get("amenities", []),
                    "category": category,
                })
            return results or None

        elif entity_type == "attractions":
            params = {
                "engine": "google_maps",
                "q": f"popular tourist places in {query}",
                "type": "search",
                "gl": "my",
                "hl": "en",
            }
            data = client.search(params)

            results = []
            for place in data.get("local_results", []):
                if place.get("sponsored"):
                    continue
                name = place.get("title", "")
                coords = place.get("gps_coordinates", {})
                results.append({
                    "attraction_id": generate_id("attraction", name, query),
                    "name": name,
                    "location": {
                        "city": query,
                        "country": "Malaysia",
                        "lat": coords.get("latitude"),
                        "lng": coords.get("longitude"),
                    },
                    "category": place.get("type"),
                    "opening_hours": place.get("hours"),
                    "estimated_duration": None,
                    "popularity_score": place.get("rating", 0.0),
                })
            return results or None

        elif entity_type == "flights":
            params = {
                "engine": "google_flights",
                "departure_id": iata,
                "arrival_id": "KUL",
                "outbound_date": travel_date if travel_date else (datetime.now(timezone.utc) + timedelta(days=7)).strftime("%Y-%m-%d"),
                "type": "2",
                "currency": "MYR",
                "hl": "en",
            }
            data = client.search(params)

            flight_list = data.get("best_flights") or data.get("other_flights") or []
            results = []
            for flight_option in flight_list:
                segments = flight_option.get("flights", [])
                if not segments:
                    continue
                dep = segments[0].get("departure_airport", {})
                arr = segments[-1].get("arrival_airport", {})
                flight_number = segments[0].get("flight_number", "")
                airline = segments[0].get("airline", "")
                results.append({
                    "flight_id": generate_id("flight", flight_number, iata),
                    "origin_state": query,
                    "origin_iata": iata,
                    "destination": "Selangor",
                    "destination_iata": arr.get("id", "KUL"),
                    "departure_time": dep.get("time"),
                    "arrival_time": arr.get("time"),
                    "duration_minutes": flight_option.get("total_duration"),
                    "airline": airline,
                    "flight_number": flight_number,
                    "price": flight_option.get("price", 0),
                    "currency": "MYR",
                    "location": {
                        "city": query,
                        "country": "Malaysia",
                        "lat": None,
                        "lng": None,
                    },
                })
            return results or None

        return None
    except Exception as e:
        print(f"[fetch_and_parse ERROR] {type(e).__name__}: {e}")
        return None


def store_to_firebase(
    record: dict,
    collection: str,
    entity_type: str,
    id_field: str,
) -> bool:
    try:
        now = datetime.now(timezone.utc)
        record["last_updated"] = now.isoformat()
        record["ttl_expires"] = (now + timedelta(days=TTL_DAYS[entity_type])).isoformat()
        record["source"] = f"serpapi_{entity_type}"

        set_record(collection, record[id_field], record)
        return True
    except Exception:
        return False


def _increment_quota(key_id: str):
    record = get_record("quota_tracker", key_id)
    if record:
        update_record("quota_tracker", key_id, {"used": record["used"] + 1})


def _reset_monthly_quota() -> None:
    for i in range(1, 6):
        key_id = f"key_{i}"
        record = get_record("quota_tracker", key_id)
        if record:
            update_record("quota_tracker", key_id, {"used": 0})
            print(f"[quota] Reset {key_id}")


def _write_ttl_sentinel(collection: str, entity_id: str, entity_type: str):
    now = datetime.now(timezone.utc)
    set_record(collection, entity_id, {
        "ttl_expires": (now + timedelta(days=TTL_DAYS[entity_type])).isoformat(),
        "last_updated": now.isoformat(),
        "_ttl_sentinel": True,
    })


def seed_database():
    for collection in ["hotels", "attractions", "flights"]:
        flags = get_record(collection, "_flags")
        if flags and flags.get("seeded"):
            print(f"{collection} already seeded, skipping.")
            continue

        stored = 0

        if collection == "hotels":
            for city in TREKKU_SEED["cities"]:
                api_key, key_id = quota_tracker()
                if api_key == "FALLBACK":
                    print("WARNING: All API keys exhausted. Stopping seeding.")
                    return
                results = fetch_and_parse(city, "hotels", api_key)
                if results:
                    _increment_quota(key_id)
                    for item in results:
                        store_to_firebase(item, "hotels", "hotels", "hotel_id")
                        stored += 1
                    _write_ttl_sentinel("hotels", generate_id("hotel", city, city), "hotels")
                else:
                    print(f"  hotels: no result for {city}")

        elif collection == "attractions":
            for city in TREKKU_SEED["cities"]:
                api_key, key_id = quota_tracker()
                if api_key == "FALLBACK":
                    print("WARNING: All API keys exhausted. Stopping seeding.")
                    return
                results = fetch_and_parse(city, "attractions", api_key)
                if results:
                    _increment_quota(key_id)
                    for item in results:
                        store_to_firebase(item, "attractions", "attractions", "attraction_id")
                        stored += 1
                    _write_ttl_sentinel("attractions", generate_id("attraction", city, city), "attractions")
                else:
                    print(f"  attractions: no result for {city}")

        elif collection == "flights":
            for origin in TREKKU_SEED["flight_origins"]:
                api_key, key_id = quota_tracker()
                if api_key == "FALLBACK":
                    print("WARNING: All API keys exhausted. Stopping seeding.")
                    return
                results = fetch_and_parse(origin["state"], "flights", api_key, iata=origin["iata"])
                if results:
                    _increment_quota(key_id)
                    for item in results:
                        store_to_firebase(item, "flights", "flights", "flight_id")
                        stored += 1
                    _write_ttl_sentinel("flights", generate_id("flight", origin["state"], "selangor"), "flights")
                else:
                    print(f"  flights: no result for {origin['state']}")

        if stored > 0:
            set_record(collection, "_flags", {
                "seeded": True,
                "seeded_at": datetime.now(timezone.utc).isoformat()
            })
            print(f"{collection}: seeded {stored} records.")
        else:
            print(f"{collection}: 0 records stored, skipping _flags update.")


_ENTITY_PREFIX = {"hotels": "hotel", "attractions": "attraction", "flights": "flight"}
_ID_FIELD = {"hotels": "hotel_id", "attractions": "attraction_id", "flights": "flight_id"}
_IATA_MAP = {o["state"]: o["iata"] for o in TREKKU_SEED["flight_origins"]}
_QUERY_FIELD = {
    "hotels": "location.city",
    "attractions": "location.city",
    "flights": "origin_state",
}


def refresh_all() -> dict:
    summary = {"hotels": 0, "attractions": 0, "flights": 0, "errors": 0}

    if datetime.now(timezone.utc).day == 1:
        _reset_monthly_quota()

    for entity_type in ("hotels", "attractions"):
        for city in TREKKU_SEED["cities"]:
            api_key, key_id = quota_tracker()
            if api_key == "FALLBACK":
                print(f"[refresh_all] Quota exhausted during {entity_type}. Stopping.")
                summary["errors"] += 1
                return summary
            results = fetch_and_parse(city, entity_type, api_key)
            if results:
                _increment_quota(key_id)
                for item in results:
                    store_to_firebase(item, entity_type, entity_type, _ID_FIELD[entity_type])
                _write_ttl_sentinel(
                    entity_type,
                    generate_id(_ENTITY_PREFIX[entity_type], city, city),
                    entity_type,
                )
                summary[entity_type] += len(results)
                print(f"[refresh_all] {entity_type}: {len(results)} records for {city}")
            else:
                summary["errors"] += 1
                print(f"[refresh_all] {entity_type}: no results for {city}")

    for origin in TREKKU_SEED["flight_origins"]:
        api_key, key_id = quota_tracker()
        if api_key == "FALLBACK":
            print("[refresh_all] Quota exhausted during flights. Stopping.")
            summary["errors"] += 1
            return summary
        results = fetch_and_parse(origin["state"], "flights", api_key, iata=origin["iata"])
        if results:
            _increment_quota(key_id)
            for item in results:
                store_to_firebase(item, "flights", "flights", "flight_id")
            _write_ttl_sentinel(
                "flights",
                generate_id("flight", origin["state"], "selangor"),
                "flights",
            )
            summary["flights"] += len(results)
            print(f"[refresh_all] flights: {len(results)} records for {origin['state']}")
        else:
            summary["errors"] += 1
            print(f"[refresh_all] flights: no results for {origin['state']}")

    return summary


def capture(query: str, entity_type: str, city: str = None, travel_date: str = None):
    collection = entity_type

    if travel_date and entity_type in MAX_HORIZON_DAYS:
        if (date.fromisoformat(travel_date) - date.today()).days > MAX_HORIZON_DAYS[entity_type]:
            return None

    cache_key = (entity_type, query, travel_date or "")
    if cache_key in _conv_cache:
        return _conv_cache[cache_key]

    if entity_type == "flights":
        entity_id = generate_id("flight", query, "selangor")
    else:
        entity_id = generate_id(_ENTITY_PREFIX[entity_type], query, city or query)

    trend_tracker(query, entity_id, collection)

    query_value = query if entity_type == "flights" else (city or query)

    if not travel_date:
        freshness = ttl_checker(entity_id, collection)
        if freshness == "FRESH":
            records = query_records(collection, _QUERY_FIELD[entity_type], "==", query_value)
            records = [r for r in records if not r.get("_ttl_sentinel")]
            for r in records:
                r["data_freshness"] = "fresh"
            _conv_cache[cache_key] = records
            return records

    api_key, key_id = quota_tracker()

    if api_key == "FALLBACK":
        if travel_date:
            return None
        records = query_records(collection, _QUERY_FIELD[entity_type], "==", query_value)
        records = [r for r in records if not r.get("_ttl_sentinel")]
        if records:
            for r in records:
                r["data_freshness"] = "stale"
            return records
        return None

    iata = _IATA_MAP.get(query) or (query if query in _IATA_MAP.values() else None)
    if entity_type == "flights" and iata is None:
        return None

    results = fetch_and_parse(query, entity_type, api_key, iata=iata, travel_date=travel_date)
    if not results:
        return None

    _increment_quota(key_id)

    if travel_date:
        for item in results:
            item["data_freshness"] = "fresh"
        _conv_cache[cache_key] = results
        return results

    for item in results:
        store_to_firebase(item, collection, entity_type, _ID_FIELD[entity_type])
    _write_ttl_sentinel(collection, entity_id, entity_type)

    for item in results:
        item["data_freshness"] = "fresh"
    _conv_cache[cache_key] = results
    return results
