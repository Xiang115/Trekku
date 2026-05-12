# Failure Analysis: Attractions & Flights Collections Not Seeding

**Date:** 2026-05-13  
**File under investigation:** `backend/knowledge_capture.py`  
**Symptom:** Only the `hotels` collection populates in Firestore after running `python run_seed.py`. Both `attractions` and `flights` print `0 records stored` and never write `_flags.seeded = True`.

---

## 1. Confirmed Working

- `hotels` collection seeds correctly with multiple documents per city
- `quota_tracker` initialisation in `run_seed.py` is correct
- `store_to_firebase`, `_write_ttl_sentinel`, `_flags` guard logic all pass unit tests

---

## 2. Critical Code Issue Affecting All Diagnosis

`fetch_and_parse` has a bare except that silently discards every failure:

```python
# knowledge_capture.py lines 216-217
    except Exception:
        return None
```

This means HTTP 401 (bad API key), HTTP 429 (quota exceeded), JSON key errors, wrong response shape, and network timeouts ALL look identical — the function returns `None` and `seed_database` prints `no result for {city}`. **There is currently no way to tell what is actually failing without removing this catch.**

---

## 3. Attractions — Failure Hypotheses

### Hypothesis A (HIGH): Wrong response key for Google Maps engine

The code reads `data.get("local_results", [])`. The Google Maps SerpAPI engine may return results under a different key depending on the query type and whether a location pin is resolved.

Observed keys in Google Maps responses (varies by query):
- `"local_results"` — standard nearby search
- `"place_results"` — single place lookup
- `"organic_results"` — fallback when no map pins found

**Query used:** `"popular tourist places in Petaling Jaya"` with `"type": "search"`  
**Risk:** If the query resolves to a broad text search rather than a map pin search, SerpAPI may return `"organic_results"` instead of `"local_results"`, so `data.get("local_results", [])` returns `[]` and `fetch_and_parse` returns `None`.

### Hypothesis B (MEDIUM): `"type": "search"` is not the correct value

SerpAPI Google Maps `type` parameter accepted values: `"search"`, `"place"`. Using `"search"` is correct for multi-result queries but the engine may still not return `local_results` for abstract queries like "popular tourist places in …".

### Hypothesis C (MEDIUM): API key does not have Google Maps access

SerpAPI plans have per-engine access. A key with Google Hotels access does not automatically have Google Maps access. The 401/403 response would be swallowed by the bare `except`.

### Hypothesis D (LOW): `"gl": "my"` conflicts with the text query

The geo-targeting parameter may conflict with the city name already in the query string for Google Maps (it is designed for Google Search/Hotels, not Maps). May need to use `"ll"` (lat/lng) or `"location"` parameter for Maps engine instead.

---

## 4. Flights — Failure Hypotheses

### Hypothesis A (HIGH): `"type": "2"` (one-way) returns no `best_flights` for domestic Malaysian routes

Google Flights SerpAPI docs:
- `type=1` = Round trip (requires `return_date`)
- `type=2` = One-way

Some Malaysian domestic routes may not appear in one-way results via the SerpAPI Google Flights engine. The response may contain neither `"best_flights"` nor `"other_flights"`, so `flight_list` is `[]` and `fetch_and_parse` returns `None`.

### Hypothesis B (HIGH): `"arrival_id": "KUL"` is wrong for AirAsia routes

Malaysia has two main Kuala Lumpur airports:
- `KUL` = KLIA (Kuala Lumpur International Airport) — used by Malaysia Airlines, Batik Air
- `KUL` is also the SerpAPI arrival code for KLIA2 in some contexts, but IATA officially `KUL2` does not exist — SerpAPI may use `"KUL"` for both or may distinguish them

AirAsia (the dominant Malaysian domestic carrier) flies into KLIA2. If SerpAPI treats KLIA and KLIA2 as separate and the code only queries `"KUL"`, AirAsia flights will not appear, leaving many routes with zero results.

### Hypothesis C (MEDIUM): Outbound date 7 days out has no available inventory for some routes

`outbound_date` is computed as `datetime.now() + timedelta(days=7)`. Domestic Malaysian routes with low frequency (e.g., Sibu → KUL, Tawau → KUL) may have no flight inventory 7 days out, particularly on weekdays.

### Hypothesis D (MEDIUM): API key plan does not include Google Flights engine

Same as Attractions Hypothesis C — SerpAPI plan access is per-engine. The bare `except` hides the 401/403.

### Hypothesis E (LOW): `"currency": "MYR"` is invalid for some routes

If the route is priced in a different currency by default and `"MYR"` is not supported for that search, the response may return an error or empty result.

---

## 5. Code Paths to Inspect

### Path 1: What does `fetch_and_parse` actually receive back from SerpAPI?

The fastest diagnosis is to temporarily replace the bare `except` with exception printing and add a raw response dump. Add this to a scratch script:

```python
# backend/debug_fetch.py
import os
import requests
from dotenv import load_dotenv
load_dotenv()

SERPAPI_URL = "https://serpapi.com/search"
api_key = os.getenv("SERPAPI_KEY_1")

# Test attractions
resp = requests.get(SERPAPI_URL, params={
    "engine": "google_maps",
    "q": "popular tourist places in Petaling Jaya",
    "type": "search",
    "gl": "my",
    "hl": "en",
    "api_key": api_key,
}, timeout=10)
data = resp.json()
print("=== ATTRACTIONS ===")
print("Status:", resp.status_code)
print("Top-level keys:", list(data.keys()))
print("local_results count:", len(data.get("local_results", [])))
print("organic_results count:", len(data.get("organic_results", [])))
print()

# Test flights
from datetime import datetime, timedelta, timezone
outbound = (datetime.now(timezone.utc) + timedelta(days=7)).strftime("%Y-%m-%d")
resp2 = requests.get(SERPAPI_URL, params={
    "engine": "google_flights",
    "departure_id": "JHB",
    "arrival_id": "KUL",
    "outbound_date": outbound,
    "type": "2",
    "currency": "MYR",
    "hl": "en",
    "api_key": api_key,
}, timeout=10)
data2 = resp2.json()
print("=== FLIGHTS (JHB → KUL, one-way) ===")
print("Status:", resp2.status_code)
print("Top-level keys:", list(data2.keys()))
print("best_flights count:", len(data2.get("best_flights", [])))
print("other_flights count:", len(data2.get("other_flights", [])))
print("error:", data2.get("error"))
```

Run: `cd backend && python debug_fetch.py`

### Path 2: Verify the `except Exception` is not hiding errors

Temporarily change line 216 in `knowledge_capture.py`:
```python
# BEFORE (masks all errors)
    except Exception:
        return None

# AFTER (for diagnosis only)
    except Exception as e:
        print(f"[fetch_and_parse ERROR] {type(e).__name__}: {e}")
        return None
```

Then re-run `python run_seed.py` and observe the error messages.

---

## 6. Specific Questions for Investigation

1. What are the top-level keys in the SerpAPI Google Maps response for `"popular tourist places in Petaling Jaya"`? Is `local_results` present?

2. What does the SerpAPI Google Flights response look like for `departure_id=JHB, arrival_id=KUL, type=2`? Does `best_flights` or `other_flights` exist? Is there an `"error"` key?

3. Does the SerpAPI key in `.env` have both `google_maps` and `google_flights` engine access, or only `google_hotels`?

4. For flights: does changing `arrival_id` from `"KUL"` to `"KUL"` with `type=1` and adding a `return_date` return results? If yes, the issue is the one-way (`type=2`) parameter.

5. For flights: does querying `departure_id=PEN` (Penang, higher-frequency route) return results? If Penang works but Sibu/Tawau do not, the issue is route availability for low-frequency origins.

---

## 7. Files Changed During Investigation History

| Date | Change | Result |
|---|---|---|
| Prior session | Added `check_in_date`/`check_out_date` to hotels | Hotels now seed correctly |
| Prior session | Added `"type": "2"`, `"currency": "MYR"`, `outbound_date` to flights | Flights still return 0 |
| Prior session | Changed attractions from named-attraction queries to city queries | Attractions still return 0 |
| Prior session | Added `"gl": "my"` to hotels and attractions | Hotels fixed, attractions unchanged |
| Prior session | Added `"hl": "en"` to flights and attractions | No change |

---

## 8. Recommended Fix Priority

1. **Run `debug_fetch.py`** (above) — this will immediately reveal whether the API is returning data at all and what the actual response shape is
2. **Remove the bare `except`** during diagnosis — replace with `except Exception as e: print(...)` so errors are visible
3. **Check SerpAPI account plan** — verify `google_maps` and `google_flights` engines are enabled for the key
4. **For attractions**: if `local_results` is empty, try the `"ll"` parameter or a simpler query like `"things to do in Petaling Jaya"`
5. **For flights**: try `type=1` with a `return_date` first to confirm the route exists, then debug the `type=2` failure
