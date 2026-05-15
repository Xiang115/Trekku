# Daily Knowledge Refresh — Design Spec

**Date:** 2026-05-15
**Project:** Trekku
**Scope:** Automated daily re-ingestion of all seed travel data into Firebase

---

## Problem

`knowledge_capture.py` currently refreshes data lazily — only when `capture()` is called at query time and finds a stale TTL. SerpAPI updates hotel, attraction, and flight data daily, so the knowledge base can serve data up to 7 days old before a user query triggers a re-fetch. A proactive daily batch job keeps the knowledge base maximally fresh without depending on user traffic.

The project is not hosted anywhere, so the batch job needs an external trigger that requires no server.

---

## Solution

A GitHub Actions cron workflow that runs daily at 2 AM UTC (10 AM MYT), checks out the repo, and calls a new `refresh_all()` function that re-fetches every entry in `TREKKU_SEED` unconditionally. No TTL check — daily freshness is the goal.

---

## Scope

Refresh is bounded to the existing `TREKKU_SEED` constant:
- **Hotels:** 9 cities (Shah Alam, Petaling Jaya, Klang, Subang Jaya, Sepang, Puchong, Kuala Lumpur, Bukit Bintang, KLCC)
- **Attractions:** same 9 cities
- **Flights:** 12 origins (Johor Bahru, Kota Kinabalu, Kuching, Penang, Langkawi, Kota Bharu, Kuala Terengganu, Alor Setar, Miri, Sibu, Sandakan, Tawau)

**Total: 30 API calls per run → ~900 calls/month**

---

## Architecture

```
GitHub Actions (cron 0 2 * * *)
  └── python backend/run_refresh.py
        └── knowledge_capture.refresh_all()
              ├── for each city  → fetch_and_parse(city, "hotels")  → store_to_firebase()
              ├── for each city  → fetch_and_parse(city, "attractions") → store_to_firebase()
              └── for each origin → fetch_and_parse(state, "flights") → store_to_firebase()
```

---

## Code Changes

### 1. `refresh_all()` in `backend/knowledge_capture.py`

New function — same iteration structure as `seed_database()` but:
- No `_flags.seeded` guard — always re-fetches all entries
- Checks for FALLBACK from `quota_tracker()` and stops early if all quota exhausted
- Calls `_increment_quota()` once per successful `fetch_and_parse()` call
- Calls `store_to_firebase()` for each returned record (overwrites existing documents by deterministic ID)
- Calls `_write_ttl_sentinel()` per entity group after storing
- On the 1st of each calendar month, resets all `quota_tracker` counters to `0` before fetching — aligns with SerpAPI billing cycle
- Returns `{"hotels": N, "attractions": N, "flights": N, "errors": N}`

### 2. `backend/run_refresh.py`

Minimal orchestrator:
- Calls `refresh_all()`
- Prints the summary dict
- Exits with code `1` if `summary["errors"] > 0` — causes GitHub Actions to mark the run failed

### 3. Quota limit fix in `backend/run_seed.py`

`limit` raised from `100` → `250` to match the actual SerpAPI monthly allowance per key.

**Budget check:**
- 5 keys × 250 limit = 1,250 total monthly calls
- Daily refresh consumes ~900/month
- Leaves ~350 calls/month for runtime `capture()` calls

---

## GitHub Actions Workflow

**File:** `.github/workflows/daily-refresh.yml`

**Triggers:**
- `schedule: cron: '0 2 * * *'` — daily at 2 AM UTC / 10 AM MYT
- `workflow_dispatch` — manual trigger via Actions tab

**Steps:**
1. `actions/checkout@v4`
2. `actions/setup-python@v5` with Python 3.11 and pip cache keyed on `backend/requirements.txt`
3. `pip install -r requirements.txt` (working directory: `backend/`)
4. Write `${{ secrets.FIREBASE_SERVICE_ACCOUNT_JSON }}` to `firebase/serviceAccountKey.json` — `config.py` picks this up via its existing `_default_key_path`
5. Run `python run_refresh.py` with `SERPAPI_KEY_1` through `SERPAPI_KEY_5` injected as env vars

---

## Secrets Configuration

Add once in GitHub repo → Settings → Secrets and variables → Actions:

| Secret | Value |
|---|---|
| `FIREBASE_SERVICE_ACCOUNT_JSON` | Full JSON content of `firebase/serviceAccountKey.json` |
| `SERPAPI_KEY_1` | First SerpAPI key |
| `SERPAPI_KEY_2` | Second key (empty string if unused) |
| `SERPAPI_KEY_3` | Third key (empty string if unused) |
| `SERPAPI_KEY_4` | Fourth key (empty string if unused) |
| `SERPAPI_KEY_5` | Fifth key (empty string if unused) |

No changes to `config.py` or `database.py` are needed — the service account path is already parameterised via `FIREBASE_SERVICE_ACCOUNT_PATH`.

---

## Error Handling

- Any `fetch_and_parse()` exception is already caught and logged inside the function; `refresh_all()` counts these as errors and continues to the next entry
- If `quota_tracker()` returns FALLBACK, `refresh_all()` stops immediately and reports remaining entries as errors
- `run_refresh.py` exits with code `1` on any errors, which causes GitHub Actions to mark the workflow run as failed — GitHub sends an email notification to the repo owner by default

---

## Model Reconciliation (`backend/models.py`)

`models.py` is an earlier draft that diverged from the schema `knowledge_capture.py` actually writes. All new code must use these models for type structure. The following fixes are required before `refresh_all()` can use them:

| Model | Current (wrong) | Correct |
|---|---|---|
| `Flight.price_range` | `FlightPriceRange` (min/max) | `price: float` — single one-way fare |
| `Flight.duration` | `str` (e.g. `"1h 10m"`) | `duration_minutes: Optional[int]` |
| `Flight` missing fields | — | add `airline: str`, `flight_number: str`, `departure_time: Optional[str]`, `arrival_time: Optional[str]` |
| `Attraction.source` default | `"serpapi_places"` | `"serpapi_attractions"` |
| `QuotaTracker.limit` default | `100` | `250` |

`FlightPriceRange` becomes unused after the fix and should be removed.

---

## Out of Scope

- Expanding the seed list beyond `TREKKU_SEED` — city/attraction/flight scope is fixed
- Quota auto-reset beyond the 1st-of-month check — manual reset via `run_seed.py` remains the fallback
- Retry logic on individual failed API calls — existing `fetch_and_parse()` error handling is sufficient for a prototype
- Notifications beyond GitHub Actions email — no Slack/webhook alerting
