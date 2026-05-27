"""
Run this once from the backend/ directory to seed Firestore:
    python run_seed.py
"""
import os
from datetime import datetime, timezone

from database import set_record, delete_record
from knowledge_capture import seed_database

now = datetime.now(timezone.utc)
next_month = now.month % 12 + 1
next_year = now.year + (1 if now.month == 12 else 0)
RESET_DATE = f"{next_year}-{next_month:02d}-01"

# Remove stale quota records for keys that are not configured in the environment.
for i in range(1, 6):
    key_value = os.getenv(f"SERPAPI_KEY_{i}", "")
    if not key_value or key_value == "your_key_here":
        delete_record("quota_tracker", f"key_{i}")
        print(f"Removed stale quota_tracker/key_{i}")

# Create/overwrite quota records for keys that are present.
for i in range(1, 6):
    key_value = os.getenv(f"SERPAPI_KEY_{i}", "")
    if not key_value or key_value == "your_key_here":
        continue
    key_id = f"key_{i}"
    set_record("quota_tracker", key_id, {
        "key_id": key_id,
        "used": 0,
        "limit": 250,
        "reset_date": RESET_DATE,
    })
    print(f"Reset quota_tracker/{key_id} — limit=250, reset_date={RESET_DATE}")

seed_database()
