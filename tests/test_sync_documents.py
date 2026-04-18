# tests/test_sync_documents.py
import json
import pytest
from unittest.mock import patch, MagicMock, call


class TestListNewS3Objects:
    @patch("scripts.sync_documents.get_connection")
    def test_filters_out_already_ingested(self, mock_get_conn):
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value = mock_cur
        mock_cur.fetchall.return_value = [("documents/a.pdf", "etag-a")]
        mock_get_conn.return_value = mock_conn

        s3_objects = [
            {"Key": "documents/a.pdf", "ETag": '"etag-a"'},
            {"Key": "documents/b.pdf", "ETag": '"etag-b"'},
        ]

        from scripts.sync_documents import list_new_s3_objects
        new_objects = list_new_s3_objects(s3_objects, mock_conn)

        assert len(new_objects) == 1
        assert new_objects[0]["Key"] == "documents/b.pdf"

    @patch("scripts.sync_documents.get_connection")
    def test_detects_changed_etag(self, mock_get_conn):
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value = mock_cur
        mock_cur.fetchall.return_value = [("documents/a.pdf", "old-etag")]
        mock_get_conn.return_value = mock_conn

        s3_objects = [
            {"Key": "documents/a.pdf", "ETag": '"new-etag"'},
        ]

        from scripts.sync_documents import list_new_s3_objects
        new_objects = list_new_s3_objects(s3_objects, mock_conn)

        assert len(new_objects) == 1


class TestExtractSections:
    @patch("scripts.sync_documents.invoke_model_json")
    def test_returns_sections_from_claude(self, mock_invoke):
        mock_invoke.return_value = [
            {"section_title": "Overview", "content": "This is the overview."},
            {"section_title": "Details", "content": "These are the details."},
        ]

        from scripts.sync_documents import extract_sections
        sections = extract_sections("Some raw document text")

        assert len(sections) == 2
        assert sections[0]["section_title"] == "Overview"
        mock_invoke.assert_called_once()
