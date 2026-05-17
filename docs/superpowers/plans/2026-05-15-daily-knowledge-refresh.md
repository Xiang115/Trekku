# Daily Knowledge Refresh Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `refresh_all()` function that re-fetches all seed travel data daily, expose it via `run_refresh.py`, and trigger it automatically through a GitHub Actions cron workflow.

**Architecture:** `refresh_all()` mirrors `seed_database()` but skips the seeded-flag guard — it unconditionally iterates all cities and flight origins in `TREKKU_SEED`, calls `fetch_and_parse()` + `store_to_firebase()` for each, and resets quota counters on the 1st of each month. `run_refresh.py` calls it and exits with code 1 on errors so GitHub Actions reports failures.

**Tech Stack:** Python 3.11, `knowledge_capture.py`, `models.py` (Pydantic v2), `unittest.mock`, pytest, GitHub Actions YAML

---

## Design Decisions

| Decision | Approach |
|---|---|
| TTL check in daily job | Skipped — job always re-fetches; daily freshness is the goal |
| Monthly quota reset | `refresh_all()` checks `datetime.now(timezone.utc).day == 1` and calls `_reset_monthly_quota()` |
| Error reporting | `refresh_all()` returns `{"hotels": N, "attractions": N, "flights": N, "errors": N}`; exit code 1 if errors > 0 |
| Firebase credential in CI | Service account JSON written from GitHub Secret to `firebase/serviceAccountKey.json` at runtime — no changes to `config.py` |

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `backend/models.py` | **Modify** | Fix `Flight`, `Attraction`, `QuotaTracker` to match actual Firebase schema |
| `backend/knowledge_capture.py` | **Modify** | Add `_reset_monthly_quota()` and `refresh_all()` |
| `backend/run_refresh.py` | **Create** | Orchestrator script — calls `refresh_all()`, exits 1 on errors |
| `backend/run_seed.py` | **Modify** | Raise `limit` from `100` → `250` |
| `backend/tests/test_models.py` | **Create** | Verify updated models instantiate with real data shapes |
| `backend/tests/test_knowledge_capture.py` | **Modify** | Add tests for `_reset_monthly_quota()` and `refresh_all()` |
| `.github/workflows/daily-refresh.yml` | **Create** | Cron workflow — daily 2 AM UTC, manual trigger |

---

## Task 1: Fix `models.py`

**Files:**
- Modify: `backend/models.py`
- Create: `backend/tests/test_models.py`

`models.py` was written before `knowledge_capture.py` finalised its schema. Three models are wrong: `Flight` uses a `price_range` struct instead of a single `price`, `Attraction` has the wrong source string, and `QuotaTracker` has a limit of 100 instead of 250.

- [ ] **Step 1: Write failing model tests**

Create `backend/tests/test_models.py`:

```python
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
```

- [ ] **Step 2: Run tests to confirm they fail**

```
cd backend
pytest tests/test_models.py -v
```

Expected: `ValidationError` on `Flight` (no `price` field), wrong source default, wrong limit default.

- [ ] **Step 3: Replace `backend/models.py` with the corrected version**

```python
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


# ─── SHARED ──────────────────────────────────────────

class Location(BaseModel):
    city: str
    country: str = "Malaysia"
    lat: Optional[float] = None
    lng: Optional[float] = None


# ─── HOTEL ───────────────────────────────────────────

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
    category: Optional[str] = None
    opening_hours: Optional[str] = None
    estimated_duration: Optional[str] = None
    popularity_score: float = 0.0
    last_updated: str
    ttl_expires: str
    source: str = "serpapi_attractions"


# ─── FLIGHT ──────────────────────────────────────────

class Flight(BaseModel):
    flight_id: str
    origin_state: str
    origin_iata: str
    destination: str = "Selangor"
    destination_iata: str = "KUL"
    departure_time: Optional[str] = None
    arrival_time: Optional[str] = None
    duration_minutes: Optional[int] = None
    airline: str
    flight_number: str
    price: float
    currency: str = "MYR"
    location: Location
    last_updated: str
    ttl_expires: str
    source: str = "serpapi_flights"


# ─── TRENDING TOPIC ──────────────────────────────────

class TrendingTopic(BaseModel):
    topic_name: str
    search_count: int = 0
    last_reset: str
    last_fetched: Optional[str] = None


# ─── QUOTA TRACKER ───────────────────────────────────

class QuotaTracker(BaseModel):
    key_id: str
    used: int = 0
    limit: int = 250
    reset_date: str


# ─── SYSTEM FLAG ─────────────────────────────────────

class SystemFlag(BaseModel):
    seeded: bool = False
    seeded_at: Optional[str] = None
```

- [ ] **Step 4: Run tests to confirm they pass**

```
cd backend
pytest tests/test_models.py -v
```

Expected: 4 PASSED

- [ ] **Step 5: Commit**

```bash
git add backend/models.py backend/tests/test_models.py
git commit -m "fix: align models.py with actual Firebase schema (Flight price, Attraction source, QuotaTracker limit)"
```

---

## Task 2: Add `_reset_monthly_quota()` to `knowledge_capture.py`

**Files:**
- Modify: `backend/knowledge_capture.py`
- Modify: `backend/tests/test_knowledge_capture.py`

This helper resets `used` to 0 for every active key in `quota_tracker`. It is called by `refresh_all()` on the 1st of each month.

- [ ] **Step 1: Add the import line and test to `test_knowledge_capture.py`**

Add `_reset_monthly_quota` to the existing import block at the top of `backend/tests/test_knowledge_capture.py`:

```python
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
)
```

Then append this test at the bottom of the file:

```python
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
        assert call.args[2] == {"used": 0}


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
```

- [ ] **Step 2: Run tests to confirm they fail**

```
cd backend
pytest tests/test_knowledge_capture.py::test_reset_monthly_quota_zeroes_used_for_all_active_keys -v
```

Expected: `ImportError: cannot import name '_reset_monthly_quota'`

- [ ] **Step 3: Add `_reset_monthly_quota()` to `knowledge_capture.py`**

Add this function immediately after `_increment_quota()` (around line 237):

```python
def _reset_monthly_quota():
    for i in range(1, 6):
        key_id = f"key_{i}"
        record = get_record("quota_tracker", key_id)
        if record:
            update_record("quota_tracker", key_id, {"used": 0})
            print(f"[quota] Reset {key_id}")
```

- [ ] **Step 4: Run the reset tests**

```
cd backend
pytest tests/test_knowledge_capture.py::test_reset_monthly_quota_zeroes_used_for_all_active_keys tests/test_knowledge_capture.py::test_reset_monthly_quota_skips_keys_with_no_record -v
```

Expected: 2 PASSED

- [ ] **Step 5: Commit**

```bash
git add backend/knowledge_capture.py backend/tests/test_knowledge_capture.py
git commit -m "feat: add _reset_monthly_quota helper to knowledge_capture"
```

---

## Task 3: Add `refresh_all()` to `knowledge_capture.py`

**Files:**
- Modify: `backend/knowledge_capture.py`
- Modify: `backend/tests/test_knowledge_capture.py`

`refresh_all()` iterates all cities for hotels and attractions, then all flight origins, calling the existing `fetch_and_parse()` → `_increment_quota()` → `store_to_firebase()` → `_write_ttl_sentinel()` pipeline for each. On the 1st of the month it calls `_reset_monthly_quota()` first. Stops early and returns with errors if `quota_tracker()` returns FALLBACK.

- [ ] **Step 1: Add `refresh_all` to the import in `test_knowledge_capture.py`**

Update the import block at the top of `backend/tests/test_knowledge_capture.py`:

```python
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
```

Then append these tests at the bottom of the file:

```python
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
         patch("knowledge_capture._write_ttl_sentinel"), \
         patch("knowledge_capture.datetime", mock_dt):
        summary = refresh_all()

    hotel_calls = [c for c in mock_fetch.call_args_list if c.args[1] == "hotels"]
    attraction_calls = [c for c in mock_fetch.call_args_list if c.args[1] == "attractions"]
    flight_calls = [c for c in mock_fetch.call_args_list if c.args[1] == "flights"]

    assert len(hotel_calls) == len(TREKKU_SEED["cities"])
    assert len(attraction_calls) == len(TREKKU_SEED["cities"])
    assert len(flight_calls) == len(TREKKU_SEED["flight_origins"])
    assert summary["errors"] == 0


def test_refresh_all_counts_errors_when_fetch_returns_none():
    mock_dt = MagicMock()
    mock_dt.now.return_value.day = 15

    with patch("knowledge_capture.quota_tracker", return_value=("fake_key", "key_1")), \
         patch("knowledge_capture.fetch_and_parse", return_value=None), \
         patch("knowledge_capture._increment_quota"), \
         patch("knowledge_capture._write_ttl_sentinel"), \
         patch("knowledge_capture.datetime", mock_dt):
        summary = refresh_all()

    total_seed_entries = len(TREKKU_SEED["cities"]) * 2 + len(TREKKU_SEED["flight_origins"])
    assert summary["errors"] == total_seed_entries
    assert summary["hotels"] == 0
    assert summary["attractions"] == 0
    assert summary["flights"] == 0


def test_refresh_all_stops_on_quota_fallback_without_calling_fetch():
    mock_dt = MagicMock()
    mock_dt.now.return_value.day = 15

    with patch("knowledge_capture.quota_tracker", return_value=("FALLBACK", None)), \
         patch("knowledge_capture.fetch_and_parse") as mock_fetch, \
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
         patch("knowledge_capture.datetime", mock_dt):
        refresh_all()

    mock_reset.assert_not_called()
```

- [ ] **Step 2: Run tests to confirm they fail**

```
cd backend
pytest tests/test_knowledge_capture.py::test_refresh_all_calls_fetch_for_every_seed_entry -v
```

Expected: `ImportError: cannot import name 'refresh_all'`

- [ ] **Step 3: Add `refresh_all()` to `knowledge_capture.py`**

Append this function at the end of `backend/knowledge_capture.py`:

```python
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
```

- [ ] **Step 4: Run all `refresh_all` tests**

```
cd backend
pytest tests/test_knowledge_capture.py -k "refresh_all or reset_monthly" -v
```

Expected: 7 PASSED

- [ ] **Step 5: Run full test suite to check for regressions**

```
cd backend
pytest tests/test_knowledge_capture.py -v
```

Expected: all existing tests still PASSED

- [ ] **Step 6: Commit**

```bash
git add backend/knowledge_capture.py backend/tests/test_knowledge_capture.py
git commit -m "feat: add refresh_all() for daily knowledge base re-ingestion"
```

---

## Task 4: Create `backend/run_refresh.py`

**Files:**
- Create: `backend/run_refresh.py`

Minimal orchestrator. Wraps `refresh_all()` in a `main()` function so it is testable, and exits with code 1 when the run has errors so GitHub Actions marks the workflow as failed.

- [ ] **Step 1: Create `backend/run_refresh.py`**

```python
"""
Daily refresh script — called by GitHub Actions cron.
    python run_refresh.py
"""
import sys
from knowledge_capture import refresh_all


def main() -> dict:
    summary = refresh_all()
    print(f"Refresh complete: {summary}")
    return summary


if __name__ == "__main__":
    result = main()
    if result["errors"] > 0:
        sys.exit(1)
```

- [ ] **Step 2: Verify the script runs locally without errors (dry-run with mocked imports)**

```
cd backend
python -c "
from unittest.mock import patch
with patch('knowledge_capture.refresh_all', return_value={'hotels': 0, 'attractions': 0, 'flights': 0, 'errors': 0}):
    import run_refresh
    result = run_refresh.main()
    print('exit would be 0:', result['errors'] == 0)
"
```

Expected output: `exit would be 0: True`

- [ ] **Step 3: Commit**

```bash
git add backend/run_refresh.py
git commit -m "feat: add run_refresh.py orchestrator for daily refresh cron"
```

---

## Task 5: Fix quota limit in `run_seed.py`

**Files:**
- Modify: `backend/run_seed.py`

The current limit of 100 per key gives a total budget of 500 calls/month. The daily refresh uses ~900 calls/month, which would exhaust keys by day 17. Raising to 250 matches the actual SerpAPI allowance and gives 1,250 total — enough for 900 batch + 350 runtime calls.

- [ ] **Step 1: Update the limit in `run_seed.py`**

In `backend/run_seed.py`, change line 14:

Old:
```python
        "limit": 100,
```

New:
```python
        "limit": 250,
```

- [ ] **Step 2: Verify the change**

```
cd backend
python -c "
import ast, sys
tree = ast.parse(open('run_seed.py').read())
for node in ast.walk(tree):
    if isinstance(node, ast.Constant) and node.value == 250:
        print('limit 250 found')
        sys.exit(0)
print('ERROR: 250 not found')
sys.exit(1)
"
```

Expected: `limit 250 found`

- [ ] **Step 3: Commit**

```bash
git add backend/run_seed.py
git commit -m "fix: raise quota limit to 250 to match actual SerpAPI monthly allowance"
```

---

## Task 6: Create GitHub Actions workflow

**Files:**
- Create: `.github/workflows/daily-refresh.yml`

The workflow checks out the repo, installs dependencies, writes the Firebase service account from a secret, then runs `run_refresh.py` with the five SerpAPI keys injected as environment variables.

- [ ] **Step 1: Create the `.github/workflows/` directory and workflow file**

Create `.github/workflows/daily-refresh.yml`:

```yaml
name: Daily Knowledge Refresh

on:
  schedule:
    - cron: '0 2 * * *'   # 2 AM UTC = 10 AM MYT
  workflow_dispatch:        # manual trigger via Actions tab

jobs:
  refresh:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: backend

    steps:
      - name: Checkout repo
        uses: actions/checkout@v4

      - name: Set up Python 3.11
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: pip
          cache-dependency-path: backend/requirements.txt

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Write Firebase service account
        run: echo '${{ secrets.FIREBASE_SERVICE_ACCOUNT_JSON }}' > $GITHUB_WORKSPACE/firebase/serviceAccountKey.json

      - name: Run daily refresh
        env:
          SERPAPI_KEY_1: ${{ secrets.SERPAPI_KEY_1 }}
          SERPAPI_KEY_2: ${{ secrets.SERPAPI_KEY_2 }}
          SERPAPI_KEY_3: ${{ secrets.SERPAPI_KEY_3 }}
          SERPAPI_KEY_4: ${{ secrets.SERPAPI_KEY_4 }}
          SERPAPI_KEY_5: ${{ secrets.SERPAPI_KEY_5 }}
        run: python run_refresh.py
```

- [ ] **Step 2: Validate the YAML is well-formed**

```
python -c "import yaml; yaml.safe_load(open('../.github/workflows/daily-refresh.yml'))"
```

Expected: no output (no parse errors)

- [ ] **Step 3: Add secrets in GitHub**

In your GitHub repo: Settings → Secrets and variables → Actions → New repository secret. Add each of the following:

| Secret name | Value |
|---|---|
| `FIREBASE_SERVICE_ACCOUNT_JSON` | Full JSON content of `firebase/serviceAccountKey.json` |
| `SERPAPI_KEY_1` | Your first SerpAPI key |
| `SERPAPI_KEY_2` | Second key (leave value empty if unused) |
| `SERPAPI_KEY_3` | Third key (leave value empty if unused) |
| `SERPAPI_KEY_4` | Fourth key (leave value empty if unused) |
| `SERPAPI_KEY_5` | Fifth key (leave value empty if unused) |

This step has no automated verification — confirm each secret appears in the GitHub UI without its value visible.

- [ ] **Step 4: Commit the workflow file**

```bash
git add .github/workflows/daily-refresh.yml
git commit -m "ci: add daily knowledge refresh GitHub Actions workflow"
```

- [ ] **Step 5: Trigger a manual run to verify end-to-end**

In GitHub: Actions tab → Daily Knowledge Refresh → Run workflow → Run workflow.

Watch the run. Expected: all steps green, `run_refresh.py` prints `Refresh complete:` with non-zero record counts and `errors: 0`.

---

## Self-Review

### Spec Coverage Check

| Spec requirement | Covered by task |
|---|---|
| `refresh_all()` iterates all `TREKKU_SEED` entries | Task 3 |
| No TTL check — always re-fetches | Task 3 — no `ttl_checker()` call in `refresh_all()` |
| Monthly quota reset on 1st of month | Task 2 (`_reset_monthly_quota`) + Task 3 (called from `refresh_all`) |
| Stops early on FALLBACK | Task 3 — FALLBACK guard before each fetch |
| Returns summary dict with error count | Task 3 — `{"hotels": N, "attractions": N, "flights": N, "errors": N}` |
| `run_refresh.py` exits code 1 on errors | Task 4 — `sys.exit(1)` in `__main__` block |
| Quota limit raised to 250 | Task 5 |
| GitHub Actions cron at 2 AM UTC | Task 6 — `cron: '0 2 * * *'` |
| `workflow_dispatch` manual trigger | Task 6 |
| Firebase credential via secret | Task 6 — written to `firebase/serviceAccountKey.json` |
| SERPAPI keys as env vars | Task 6 — `env:` block in workflow step |
| Model reconciliation (`Flight`, `Attraction`, `QuotaTracker`) | Task 1 |

### Placeholder Scan

No TBDs, TODOs, or incomplete sections. All code blocks are complete and runnable.

### Type Consistency Check

- `refresh_all() -> dict` — return type consistent across Task 3 definition and Task 4 caller
- `_reset_monthly_quota()` — defined in Task 2, called in Task 3, imported in test file in Task 2
- `_ID_FIELD`, `_ENTITY_PREFIX`, `generate_id` — all already defined in `knowledge_capture.py`, used without redefinition
- `TREKKU_SEED["cities"]` and `TREKKU_SEED["flight_origins"]` — keys match the actual dict structure at line 9–29 of `knowledge_capture.py`
