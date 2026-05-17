from unittest.mock import patch, MagicMock


def test_get_document_returns_none_when_missing():
    with patch("database.db") as mock_db:
        mock_doc = MagicMock()
        mock_doc.exists = False
        mock_db.collection.return_value.document.return_value.get.return_value = mock_doc

        from database import get_record
        result = get_record("destinations", "nonexistent")
        assert result is None


def test_set_document_calls_firestore():
    with patch("database.db") as mock_db:
        from database import set_record
        set_record("destinations", "paris", {"name": "Paris"})
        mock_db.collection.return_value.document.return_value.set.assert_called_once()
