from unittest.mock import patch, MagicMock


def test_get_document_returns_none_when_missing():
    with patch("database.db") as mock_db:
        mock_doc = MagicMock()
        mock_doc.exists = False
        mock_db.collection.return_value.document.return_value.get.return_value = mock_doc

        from database import get_document
        result = get_document("destinations", "nonexistent")
        assert result is None


def test_set_document_calls_firestore():
    with patch("database.db") as mock_db:
        from database import set_document
        set_document("destinations", "paris", {"name": "Paris"})
        mock_db.collection.return_value.document.return_value.set.assert_called_once()
