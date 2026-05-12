import firebase_admin
from firebase_admin import firestore
from config import db   # Firebase initialized in config.py

# ─── READ ────────────────────────────────────────────

def get_record(collection: str, document_id: str):
    """
    Fetch a single document from Firestore.
    Returns the document dict, or None if not found.
    
    Used by:
    - knowledge_capture.py → ttl_checker() to check freshness
    - knowledge_capture.py → quota_tracker() to check key usage
    - ai_engine.py → to read hotels, attractions, flights
    """
    doc = db.collection(collection).document(document_id).get()
    if doc.exists:
        return doc.to_dict()
    return None


def get_all_records(collection: str):
    """
    Fetch all documents from a collection.
    Returns a list of dicts.

    Used by:
    - ai_engine.py → to load all hotels/attractions for RAG
    """
    docs = db.collection(collection).stream()
    return [doc.to_dict() for doc in docs]


def query_records(collection: str, field: str, operator: str, value):
    """
    Fetch documents matching a condition.
    e.g. query_records("hotels", "category", "==", "budget")

    Used by:
    - ai_engine.py → filter hotels by budget category
    - ai_engine.py → filter attractions by popularity_score
    """
    docs = (db.collection(collection)
              .where(field, operator, value)
              .stream())
    return [doc.to_dict() for doc in docs]


# ─── WRITE ───────────────────────────────────────────

def set_record(collection: str, document_id: str, data: dict):
    """
    Write or overwrite a document in Firestore.
    Uses set() so same ID always overwrites — no duplicates.

    Used by:
    - knowledge_capture.py → store_to_firebase()
    - knowledge_capture.py → update quota_tracker counter
    - knowledge_capture.py → update _flags after seeding
    """
    db.collection(collection).document(document_id).set(data)


def update_record(collection: str, document_id: str, fields: dict):
    """
    Partially update specific fields without overwriting whole document.
    e.g. update_record("quota_tracker", "key_1", {"used": 43})

    Used by:
    - knowledge_capture.py → increment quota used counter
    - knowledge_capture.py → update trending_topics search_count
    """
    db.collection(collection).document(document_id).update(fields)


# ─── DELETE ──────────────────────────────────────────

def delete_record(collection: str, document_id: str):
    """
    Delete a document from Firestore.
    Rarely used in prototype — mainly for cleanup during testing.
    """
    db.collection(collection).document(document_id).delete()