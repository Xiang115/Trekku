"""
Run this once from the backend/ directory to seed Firestore:
    python run_seed.py
"""
import os

from database import set_record
from knowledge_capture import seed_database

RESET_DATE = "2026-08-01"

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
    print(f"Reset quota_tracker/{key_id}")

seed_database()
