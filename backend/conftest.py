"""
Root conftest.py for the backend test suite.

Mocks firebase_admin at the sys.modules level so that knowledge_capture,
database, and config can be imported without a real service account key or
active Firebase connection.
"""
import sys
from unittest.mock import MagicMock

# ── Firebase mock ─────────────────────────────────────────────────────────────
# Must be installed before any production module is imported.

_mock_db = MagicMock()

_mock_firestore_module = MagicMock()
_mock_firestore_module.client.return_value = _mock_db

_mock_credentials = MagicMock()
_mock_firebase_admin = MagicMock()
_mock_firebase_admin.credentials = _mock_credentials

sys.modules.setdefault("firebase_admin", _mock_firebase_admin)
sys.modules.setdefault("firebase_admin.credentials", _mock_credentials)
sys.modules.setdefault("firebase_admin.firestore", _mock_firestore_module)
