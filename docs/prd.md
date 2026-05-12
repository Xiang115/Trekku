# PRD: Trekku Knowledge Capture Model
**Module:** `knowledge_capture.py`
**Owner:** GOH KIAN XIANG
**Project:** Trekku — AI-driven Knowledge Management System (WIE 3005)
**Version:** 1.0
**Date:** May 2026

---

## Problem Statement

The Trekku system requires a structured, reliable, and quota-aware mechanism to collect travel knowledge from external APIs and persist it into Firebase for use by the AI recommendation engine. Without a dedicated knowledge capture model, the system has no structured data to reason over — making itinerary generation, hotel recommendations, and travel planning impossible.

Specifically, the knowledge capture model must solve three problems:

1. Travel data is scattered across external APIs (hotels, attractions, flights) and must be fetched, cleaned, and structured before it is useful.
2. API quota is severely limited (250 searches/month per key, 5 keys total = 1,250 calls/month), so every API call must be justified and cached aggressively.
3. The knowledge base must stay fresh enough to be accurate, but not so frequently refreshed that it exhausts the quota mid-month.

---

## Solution

A single Python module, `knowledge_capture.py`, that acts as the sole gateway between external travel APIs (SerpAPI) and the Firebase knowledge base. The module handles:

- **First-time database seeding** — a one-time batch fetch that pre-populates Firebase with a curated list of Selangor and KL hotels, attractions, and Malaysian flight routes before any user interacts with the system.
- **Quota-aware API calls** — tracking remaining calls per API key, rotating across 5 keys when one is exhausted, and falling back to the latest Firebase record when all keys are depleted.
- **TTL-based freshness checking** — each entity in Firebase has a `ttl_expires` timestamp. The module checks freshness before every API call and skips the call if data is still valid.
- **Trend-based re-fetching** — a search counter per destination/POI tracks popularity. When a topic is searched 10 or more times within 7 days and its TTL has also expired, a re-fetch is triggered.
- **Clean schema mapping** — raw SerpAPI responses are parsed and only required fields are retained. Noise such as ads, HTML snippets, and sponsored listings is discarded.
- **Travel-date-aware fetching** — `capture()` accepts an optional `travel_date` parameter. When provided, SerpAPI is queried for that specific date rather than the default near-future window. Results are held in a conversation-scoped in-memory cache (`_conv_cache`) and never persisted to Firebase, keeping the persistent knowledge base clean of date-specific pricing snapshots. Requests beyond the booking horizon (hotels > 365 days, flights > 330 days) return `None` immediately without consuming quota.

---

## User Stories

1. As the AI engine, I want structured hotel records in Firebase, so that I can generate accurate accommodation recommendations without calling external APIs at query time.
2. As the AI engine, I want structured attraction/POI records with popularity scores, so that I can prioritise well-reviewed destinations in itinerary generation.
3. As the AI engine, I want flight route records per Malaysian state with airports, so that I can factor in travel feasibility for users arriving from outside Selangor.
4. As the system, I want a first-time seeding function to run on initial deployment, so that the knowledge base is pre-populated before any user makes a request.
5. As the system, I want TTL expiry checked before every API call, so that fresh Firebase records are served directly without wasting quota.
6. As the system, I want API key rotation across 5 keys, so that the system continues to function even when one key's monthly quota is exhausted.
7. As the system, I want a fallback to the latest Firebase record when all API keys are exhausted, so that the system never returns an empty response to the AI engine.
8. As the system, I want search counters tracked per destination and POI, so that trending topics trigger proactive re-fetches to keep popular knowledge fresh.
9. As the system, I want hotel pricing re-fetched every 7 days, so that budget estimates shown to users remain reasonably accurate.
10. As the system, I want hotel metadata re-fetched every 30 days, so that names, locations, and amenities stay correct without burning quota unnecessarily.
11. As the system, I want attraction and POI data re-fetched every 60 days, so that largely static information like opening hours and categories is maintained efficiently.
12. As the system, I want flight route data re-fetched every 7 days, so that pricing estimates reflect recent changes for inter-state travellers.
13. As the system, I want quota usage tracked per API key in Firebase, so that the module always knows which key to use next without manual monitoring.
14. As the system, I want quota counters to reset monthly, so that the full 250-call allowance per key is available at the start of each billing cycle.
15. As the Backend Developer, I want all Firebase writes to use deterministic IDs, so that the same hotel or attraction is never stored as a duplicate record.
16. As the Backend Developer, I want all captured records to include `last_updated` and `ttl_expires` fields, so that `database.py` can serve freshness metadata to other modules.
17. As the Project Manager, I want the quota tracker stored in Firebase, so that all team members can monitor API consumption without accessing SerpAPI dashboards directly.

---

## Implementation Decisions

### Module Structure

`knowledge_capture.py` contains the following functions with clear, single responsibilities:

**1. `seed_database()`**
- Runs once on initial deployment only.
- Iterates through the pre-defined `TREKKU_SEED` list.
- Calls `fetch_and_parse()` for each seed entry.
- Calls `store_to_firebase()` to persist each record.
- Sets initial attraction priority scores based on Google review ratings before any user trends exist.

**2. `ttl_checker(entity_id, collection)`**
- Queries Firebase for the record matching `entity_id` in the given collection.
- Returns `NOT_FOUND` if no record exists → proceed to fetch.
- Returns `STALE` if `current_time > ttl_expires` → proceed to fetch.
- Returns `FRESH` if record is within TTL → skip API call, serve existing record.

**3. `trend_tracker(topic_name)`**
- Increments the search counter for the given topic in the `trending_topics` Firebase collection.
- If counter reaches 10 or more within a 7-day window AND `ttl_checker()` returns `STALE`, flags the topic for re-fetch.
- Resets counter to zero after a re-fetch is triggered.

**4. `quota_tracker()`**
- Reads the `quota_tracker` Firebase collection to find the active API key.
- Rotates to the next key (`key_1` → `key_2` → ... → `key_5`) when `used >= limit`.
- If all 5 keys are exhausted, returns a `FALLBACK` signal — no API call is made, latest Firebase record is served instead.
- Only keys with a real env var value (non-placeholder) have a quota record in Firestore; placeholder keys are excluded at initialisation time by `run_seed.py`.
- Resets all counters on the 1st of each month.

**5. `_increment_quota(key_id)`**
- Increments the `used` counter for the given key in Firebase by 1.
- Called once per successful `fetch_and_parse()` call in both `seed_database()` and `capture()` — not per record stored.
- Separated from `store_to_firebase()` to prevent quota over-counting when a single API call returns multiple records.

**6. `fetch_and_parse(query, entity_type, api_key, iata, travel_date)`**
- Calls SerpAPI via the official `serpapi.Client` SDK using the key selected by `quota_tracker()`.
- When `travel_date` (ISO date string) is provided, uses it as the hotel `check_in_date` and flight `outbound_date` instead of the default near-future offsets (+1 day for hotels, +7 days for flights).
- Maps raw response fields to the clean schema (see Schema section below).
- Discards noise: ads, HTML snippets, sponsored listings, thumbnail URLs.
- On any exception (HTTP error, bad key, quota exceeded, unexpected response shape), prints the error with full type and message and returns `None` — errors are visible in logs rather than silently swallowed.
- Returns a list of structured Python dicts ready for Firebase storage, or `None` if no usable results.

**7. `store_to_firebase(record, collection, entity_type, id_field)`**
- Writes the structured record to the appropriate Firebase collection using the deterministic ID.
- Sets `last_updated` to current timestamp.
- Sets `ttl_expires` based on entity type TTL rules.
- Does not touch the quota counter — that is the responsibility of `_increment_quota()`.

**8. `capture(query, entity_type, city, travel_date)`**
- Runtime entry point called by the AI engine at query time (not during seeding).
- When `travel_date` is provided and exceeds the booking horizon (`hotels` > 365 days, `flights` > 330 days), returns `None` immediately without consuming quota.
- Checks `_conv_cache` (in-memory, session-scoped) before any Firebase or API call. A cache hit returns the stored result directly.
- When `travel_date` is `None`, runs `ttl_checker()` and returns Firebase records directly if TTL is `FRESH`.
- When all quota is exhausted (FALLBACK): returns stale Firebase records if `travel_date` is `None`; returns `None` if `travel_date` is provided (stale Firebase data is for a different date and is not reliable).
- When `travel_date` is provided and a fresh API result is obtained, stores results in `_conv_cache` only — not in Firebase — to avoid polluting the persistent knowledge base with date-specific snapshots.
- For flights, resolves the IATA code from `_IATA_MAP` by exact state name match; accepts IATA codes directly as a fallback. Returns `None` if no mapping can be resolved.

### Entity ID Generation

All IDs are generated deterministically using MD5 hashing of `name + city` (lowercased, stripped). This ensures the same real-world entity always maps to the same Firebase document, preventing duplicate records.

- Hotels: `hotel_` + first 10 characters of MD5 hash
- Attractions: `attraction_` + first 10 characters of MD5 hash
- Flights: `flight_` + first 10 characters of MD5 hash

### Firebase Collection Structure

| Collection | Key Fields |
|---|---|
| `hotels/` | name, location, price_per_night (min/max), rating, amenities, category, last_updated, ttl_expires, source |
| `attractions/` | name, location, category, opening_hours, estimated_duration, popularity_score, last_updated, ttl_expires, source |
| `flights/` | origin_state, origin_iata, destination, destination_iata, departure_time, arrival_time, duration_minutes, airline, flight_number, price, currency, location, last_updated, ttl_expires, source |
| `trending_topics/` | search_count, last_reset, last_fetched |
| `quota_tracker/` | key_id, used, limit, reset_date |

### Collection Data Reference

#### `hotels/`

**Content:** One document per hotel property, keyed by a deterministic MD5 ID (`hotel_<10-char hash>` of name + city). Each document contains:

| Field | Type | Description |
|---|---|---|
| `hotel_id` | string | Deterministic ID — same property always maps to the same document |
| `name` | string | Hotel property name as returned by Google Hotels via SerpAPI |
| `location.city` | string | Selangor/KL city name used in the seed query (e.g., `"Shah Alam"`) |
| `location.country` | string | Always `"Malaysia"` |
| `location.lat` / `location.lng` | float or null | GPS coordinates from SerpAPI; null if not returned |
| `price_per_night.min` | float | Lowest nightly rate in MYR (0 if unavailable) |
| `price_per_night.max` | float | Highest nightly rate in MYR |
| `price_per_night.currency` | string | Always `"MYR"` |
| `rating` | float or null | Google overall rating (e.g., 4.3) |
| `amenities` | list[string] | Amenity tags returned by SerpAPI (e.g., `["Pool", "Free WiFi"]`) |
| `category` | string | `"budget"` (< MYR 150/night), `"mid-range"` (150–400), `"luxury"` (> 400) |
| `last_updated` | ISO timestamp | When this record was last fetched from SerpAPI |
| `ttl_expires` | ISO timestamp | When the record becomes stale (7 days after `last_updated`) |
| `source` | string | Always `"serpapi_hotels"` |

**Freshness:** 7-day TTL. Hotel pricing changes frequently; records older than 7 days are re-fetched on next query.

**AI usage:** Category (`budget`/`mid-range`/`luxury`) is the primary filter for budget-matching. Rating is a tiebreaker ranking signal. Amenities are used to match user preferences (e.g., pool, parking). Price range with `data_freshness="stale"` is surfaced to the user as an estimate rather than a confirmed rate.

---

#### `attractions/`

**Content:** One document per attraction or POI, keyed by `attraction_<10-char hash>` of name + city. Each document contains:

| Field | Type | Description |
|---|---|---|
| `attraction_id` | string | Deterministic ID |
| `name` | string | Place name (e.g., `"Batu Caves"`) |
| `location.city` | string | City name used in the seed query |
| `location.country` | string | Always `"Malaysia"` |
| `location.lat` / `location.lng` | float or null | GPS coordinates if returned by Google Maps |
| `category` | string or null | Place type tag from Google Maps (e.g., `"Tourist attraction"`, `"Museum"`) |
| `opening_hours` | string or null | Human-readable hours string if returned (e.g., `"Open until 6:00 PM"`) |
| `estimated_duration` | null | Reserved for future enrichment; always null in current version |
| `popularity_score` | float | Google Maps rating (0.0 if unavailable); used as a ranking signal |
| `last_updated` | ISO timestamp | When this record was last fetched |
| `ttl_expires` | ISO timestamp | Stale after 60 days |
| `source` | string | Always `"serpapi_attractions"` |

**Freshness:** 60-day TTL. Attraction metadata (opening hours, category) is largely static. Popularity scores are refreshed when a topic exceeds the trending threshold (≥ 10 searches in 7 days with a stale TTL).

**AI usage:** `popularity_score` is the default ranking signal for itinerary ordering when no user preference data exists. `category` filters attractions by interest type (e.g., nature, shopping, cultural). `opening_hours` is used to flag scheduling conflicts in itinerary generation. `location.lat`/`lng` are passed to routing logic for proximity calculations.

---

#### `flights/`

**Content:** One document per flight option per origin route, keyed by `flight_<10-char hash>` of flight number + IATA code. Each document contains:

| Field | Type | Description |
|---|---|---|
| `flight_id` | string | Deterministic ID |
| `origin_state` | string | Malaysian state name (e.g., `"Johor Bahru"`) |
| `origin_iata` | string | IATA airport code of the departure airport (e.g., `"JHB"`) |
| `destination` | string | Always `"Selangor"` |
| `destination_iata` | string | IATA code of the arrival airport (typically `"KUL"`) |
| `departure_time` | string or null | Departure time as returned by Google Flights (e.g., `"7:30 AM"`) |
| `arrival_time` | string or null | Arrival time as returned by Google Flights |
| `duration_minutes` | int or null | Total flight duration in minutes |
| `airline` | string | Airline name (e.g., `"AirAsia"`) |
| `flight_number` | string | Flight code (e.g., `"AK 6121"`) |
| `price` | float | One-way fare in MYR at the time of fetch |
| `currency` | string | Always `"MYR"` |
| `location.city` | string | Origin city name |
| `last_updated` | ISO timestamp | When this record was last fetched |
| `ttl_expires` | ISO timestamp | Stale after 7 days |
| `source` | string | Always `"serpapi_flights"` |

**Freshness:** 7-day TTL. Flight pricing is advisory — fares fluctuate and this is not a live booking feed. Records older than 7 days are re-fetched on next query.

**AI usage:** `price` and `duration_minutes` are used to assess travel feasibility for users arriving from outside Selangor. The AI filters out routes whose price exceeds the user's stated travel budget or whose duration makes same-day arrival impractical. `data_freshness="stale"` triggers a caveat in the output (e.g., "estimated fare, may vary").

---

#### `trending_topics/`

**Content:** One document per searched topic name (e.g., a city, POI name, or state). Each document contains:

| Field | Type | Description |
|---|---|---|
| `search_count` | int | Number of times this topic has been queried since `last_reset` |
| `last_reset` | ISO timestamp | When the counter was last zeroed (set on first query or after a re-fetch trigger) |
| `last_fetched` | ISO timestamp or null | When a re-fetch was last triggered for this topic; null if never re-fetched |

**Freshness:** Counter resets after a re-fetch is triggered. There is no TTL expiry on these documents — they accumulate across the system lifetime.

**AI usage:** Not consumed by the AI engine directly. Used internally by `trend_tracker()` to decide whether a query warrants a fresh API fetch. A topic that has been searched ≥ 10 times within 7 days with a stale TTL triggers a proactive re-fetch so the AI always receives up-to-date data on popular destinations.

---

#### `quota_tracker/`

**Content:** One document per active SerpAPI key (only keys with a real env var value are initialised). Each document contains:

| Field | Type | Description |
|---|---|---|
| `key_id` | string | Logical key identifier (e.g., `"key_1"`) |
| `used` | int | Number of API calls made with this key in the current billing cycle |
| `limit` | int | Maximum calls allowed before rotation (currently 100) |
| `reset_date` | string | Date on which `used` should be manually reset to 0 (aligned to SerpAPI billing cycle) |

**Freshness:** `used` is incremented once per successful `fetch_and_parse()` call. There is no TTL — this is operational state, not cached knowledge.

**AI usage:** Not consumed by the AI engine. Used exclusively by `quota_tracker()` to select the active API key and by `capture()` to decide whether a live fetch is possible or a stale fallback must be returned.

---

### TTL Rules

| Entity | TTL | Rationale |
|---|---|---|
| Hotel metadata | 30 days | Name, location, amenities rarely change |
| Hotel pricing | 7 days | Pricing is advisory; full accuracy not guaranteed |
| Attractions/POI | 60 days | Opening hours and categories are largely static |
| Flight routes | 7 days | Pricing fluctuates; weekly refresh maintains reasonable accuracy |
| Trending counter | Resets after re-fetch | Prevents repeated triggers on the same topic |

### API Quota Allocation

| API Type | Monthly Call Budget | Keys Available | Total Budget |
|---|---|---|---|
| Hotels (SerpAPI) | 100 calls/key | 5 keys | 500 calls |
| Flights (SerpAPI) | 100 calls/key | 5 keys | 500 calls |
| Buffer (Attractions, POI, other) | 50 calls/key | 5 keys | 250 calls |

### Seed List

**Cities (Hotels seeded per city):**
Selangor — Shah Alam, Petaling Jaya, Klang, Subang Jaya, Sepang, Puchong
KL (shared geographical region) — Kuala Lumpur, Bukit Bintang, KLCC

**Attractions (seeded with initial priority scores from Google reviews):**

| Attraction | Initial Score |
|---|---|
| Petronas Twin Towers | 4.7 |
| Batu Caves | 4.6 |
| Sunway Lagoon | 4.5 |
| Bukit Bintang | 4.4 |
| Blue Mosque Shah Alam | 4.4 |
| KL Tower | 4.3 |
| i-City Shah Alam | 4.2 |
| Central Market KL | 4.1 |

**Flight Origins (Malaysian states with airports):**
Johor Bahru (Senai), Kota Kinabalu, Kuching, Penang, Langkawi, Kota Bharu, Kuala Terengganu, Alor Setar, Miri, Sibu, Sandakan, Tawau

### Capture Trigger Flow

```
capture() — runtime entry point
    → [if travel_date beyond horizon]  return None immediately (no quota consumed)
    → [if _conv_cache hit]             return cached result (no Firebase or API call)
    → trend_tracker()                  increments search counter; flags if threshold met
    → [if no travel_date] ttl_checker() returns FRESH / STALE / NOT_FOUND
    → [if FRESH]           query Firebase directly; store in _conv_cache; return data_freshness=fresh
    → quota_tracker()      selects active API key or returns FALLBACK
    → [if FALLBACK + no travel_date]   query Firebase; return data_freshness=stale
    → [if FALLBACK + travel_date]      return None (stale Firebase data is for a different date)
    → fetch_and_parse()    calls SerpAPI with travel_date if provided; maps to clean schema; logs errors
    → _increment_quota()   increments used counter by 1 for the active key (once per API call)
    → [if travel_date]     store in _conv_cache only; return data_freshness=fresh
    → [if no travel_date]  store_to_firebase(); _write_ttl_sentinel(); store in _conv_cache; return data_freshness=fresh
    → ai_engine.py         reads clean structured records for RAG and recommendations
```

---

## Testing Decisions

### What makes a good test for this module

Tests should verify **external behaviour only** — what goes into Firebase and what decisions the module makes — not internal implementation details like how the hash is computed or which HTTP library is used.

### Modules to test

**`ttl_checker()`**
- Given a Firebase record with `ttl_expires` in the future → returns `FRESH`
- Given a Firebase record with `ttl_expires` in the past → returns `STALE`
- Given no Firebase record for the entity → returns `NOT_FOUND`

**`quota_tracker()`**
- Given `key_1` with `used == limit` → returns `key_2` as active key
- Given all 5 keys exhausted → returns `FALLBACK` signal

**`_increment_quota(key_id)`**
- Given a valid `key_id` → increments `used` counter by 1 in Firebase
- Called once per successful `fetch_and_parse()` call, not per record stored

**`trend_tracker()`**
- Given search count below 10 within 7 days → does not flag for re-fetch
- Given search count at 10 within 7 days AND TTL stale → flags for re-fetch
- Given search count at 10 within 7 days AND TTL fresh → does not flag for re-fetch

**`fetch_and_parse()`**
- Given a raw SerpAPI hotel response → returns only schema-defined fields
- Given a raw SerpAPI response containing sponsored listings → sponsored entries are excluded from output

**`store_to_firebase()`**
- Given a structured hotel record → writes to `hotels/` collection with correct deterministic ID
- Given the same hotel fetched twice → second write overwrites first, no duplicate document created

**`capture()` — travel_date behaviour**
- Given `travel_date` beyond the horizon (e.g. 400 days out for hotels) → returns `None` without calling the API
- Given `travel_date` within the horizon → SerpAPI is called with that date; result stored in `_conv_cache` only, not Firebase
- Given same `query + travel_date` called twice in one session → second call returns `_conv_cache` hit; no API or Firebase call
- Given `travel_date` provided and all quota exhausted → returns `None` (does not serve stale Firebase data)

**`seed_database()`**
- Given an empty Firebase instance → all seed cities, attractions, and flight origins produce records in Firebase after seeding completes

---

## Handoff Notes to Next Person

### For the Backend Developer (`database.py`)

The following fields will be present on every Firebase record written by `knowledge_capture.py`. Your read functions in `database.py` can rely on these being consistently populated:

- `last_updated` — ISO timestamp of when the record was last fetched
- `ttl_expires` — ISO timestamp of when the record should be considered stale
- `source` — always `"serpapi_hotels"`, `"serpapi_attractions"`, or `"serpapi_flights"`
- `data_freshness` — `"fresh"` or `"stale"` (set when serving a fallback record after all quota exhausted)

Your `database.py` does not need to call SerpAPI directly. All writes go through `knowledge_capture.py`. Your responsibility is to expose clean read functions that `ai_engine.py` can call.

### For the AI & Recommendation Engineer (`ai_engine.py`)

All records in Firebase are structured and clean by the time they reach you. You do not need to handle raw API responses or TTL logic.

Key things to know:

- **Hotels** are categorised as `budget`, `mid-range`, or `luxury` — use this field to filter by user budget preference.
- **Attractions** have a `popularity_score` field — use this as a ranking signal for itinerary prioritisation when user trend data is sparse.
- **Flights** contain `price` (one-way fare in MYR) and `duration_minutes` — use these to filter feasibility based on user budget and travel time constraints.
- **Selangor + KL** is the fixed destination scope. All hotel and attraction records will be within this geographical boundary.
- When `data_freshness` is `"stale"` on a record, flag this to the user in the recommendation output as an estimated rather than confirmed price.
- Pass `travel_date` (ISO string, e.g. `"2026-12-25"`) to `capture()` when the user specifies a travel date. If `capture()` returns `None`, the date is either beyond the booking horizon or quota is exhausted — surface this to the user as "pricing unavailable for that date" rather than falling back silently.

### For the API Integration Specialist

The `knowledge_capture.py` module handles all SerpAPI calls for hotels, attractions, and flights. You do not need to write separate fetch logic for these entities. Focus your API integration work on any additional data sources not covered by `knowledge_capture.py` (e.g., Mapbox for routing, TripAdvisor supplementary data).

---

## Out of Scope

- **Real-time booking or payment processing** — Trekku is a decision support system, not a booking platform. `knowledge_capture.py` does not interact with any transactional API.
- **User authentication** — handled by Firebase Auth, not by this module.
- **Review sentiment analysis** — the initial priority score is seeded from Google review ratings. Deep NLP sentiment analysis on review text is out of scope for this prototype.
- **International destinations** — the knowledge base covers Selangor and KL only. Flight data covers inter-state Malaysian routes to KLIA/Subang, not international flights.
- **Real-time pricing guarantees** — all prices captured are estimates with a 7-day TTL. The system makes no guarantee of live accuracy.
- **Complex query resolution** — natural language parsing of user search inputs (e.g., "hotel near Sunway Lagoon") is handled by `ai_engine.py`, not by this module. `knowledge_capture.py` receives a structured query input.

---

## Further Notes

- This is a **functional prototype**. The design prioritises simplicity and demonstrability over production-grade scalability.
- All 5 SerpAPI keys should be stored as environment variables in `.env` and never hardcoded in the module.
- The `seed_database()` function should be protected with a guard (e.g., a `SEEDED` flag in Firebase) to prevent accidental re-seeding on redeployment, which would waste quota.
- Firebase Firestore free tier (Spark plan) is sufficient for the prototype data volume.
- The quota reset date should be checked against the actual SerpAPI billing cycle, not assumed to be the 1st of every calendar month.
