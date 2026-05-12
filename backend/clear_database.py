"""
Run from the backend/ directory to wipe seeded data and reset quota counters:
    python clear_database.py

Clears: hotels, attractions, flights, trending_topics
Resets: quota_tracker used counts → 0
"""
from config import db

COLLECTIONS_TO_CLEAR = ["hotels", "attractions", "flights", "trending_topics"]

for collection in COLLECTIONS_TO_CLEAR:
    docs = list(db.collection(collection).stream())
    for doc in docs:
        doc.reference.delete()
    print(f"{collection}: deleted {len(docs)} documents")

for i in range(1, 6):
    key_id = f"key_{i}"
    doc = db.collection("quota_tracker").document(key_id).get()
    if doc.exists:
        db.collection("quota_tracker").document(key_id).update({"used": 0})
        print(f"quota_tracker/{key_id}: reset used → 0")

print("\nDone. Run: python run_seed.py")
