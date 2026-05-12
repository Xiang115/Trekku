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

`knowledge_capture.py` contains five internal functions with clear, single responsibilities:

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
- Increments the `used` counter of the selected key after every successful API call.
- Resets all counters on the 1st of each month.

**5. `fetch_and_parse(query, entity_type)`**
- Calls SerpAPI using the active key selected by `quota_tracker()`.
- Maps raw response fields to the clean schema (see Schema section below).
- Discards noise: ads, HTML snippets, sponsored listings, thumbnail URLs.
- Returns a structured Python dictionary ready for Firebase storage.

**6. `store_to_firebase(record, collection)`**
- Writes the structured record to the appropriate Firebase collection using the deterministic ID.
- Sets `last_updated` to current timestamp.
- Sets `ttl_expires` based on entity type TTL rules.

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
| `flights/` | origin_state, destination, price_range, duration, last_updated, ttl_expires, source |
| `trending_topics/` | search_count, last_reset, last_fetched |
| `quota_tracker/` | key_id, used, limit, reset_date |

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
Trigger (user search / scheduled batch / trend signal)
    → trend_tracker()     increments search counter; flags if threshold met
    → ttl_checker()       returns FRESH / STALE / NOT_FOUND
    → quota_tracker()     selects active API key or returns FALLBACK
    → fetch_and_parse()   calls SerpAPI; maps to clean schema
    → store_to_firebase() writes record; updates TTL and quota counter
    → ai_engine.py        reads clean structured records for RAG and recommendations
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
- Given a successful API call → increments `used` counter by 1 in Firebase

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

**`seed_database()`**
- Given an empty Firebase instance → all seed cities, attractions, and flight origins produce records in Firebase after seeding completes

---

## Handoff Notes to Next Person

### For the Backend Developer (`database.py`)

The following fields will be present on every Firebase record written by `knowledge_capture.py`. Your read functions in `database.py` can rely on these being consistently populated:

- `last_updated` — ISO timestamp of when the record was last fetched
- `ttl_expires` — ISO timestamp of when the record should be considered stale
- `source` — always `"serpapi_hotels"`, `"serpapi_places"`, or `"serpapi_flights"`
- `data_freshness` — `"fresh"` or `"stale"` (set when serving a fallback record after all quota exhausted)

Your `database.py` does not need to call SerpAPI directly. All writes go through `knowledge_capture.py`. Your responsibility is to expose clean read functions that `ai_engine.py` can call.

### For the AI & Recommendation Engineer (`ai_engine.py`)

All records in Firebase are structured and clean by the time they reach you. You do not need to handle raw API responses or TTL logic.

Key things to know:

- **Hotels** are categorised as `budget`, `mid-range`, or `luxury` — use this field to filter by user budget preference.
- **Attractions** have a `popularity_score` field — use this as a ranking signal for itinerary prioritisation when user trend data is sparse.
- **Flights** contain `price_range` (min/max) and `duration` — use these to filter feasibility based on user budget and travel time constraints.
- **Selangor + KL** is the fixed destination scope. All hotel and attraction records will be within this geographical boundary.
- When `data_freshness` is `"stale"` on a record, flag this to the user in the recommendation output as an estimated rather than confirmed price.

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
