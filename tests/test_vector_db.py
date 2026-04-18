import os
import pytest
from unittest.mock import patch, MagicMock


class TestGetConnection:
    @patch("psycopg2.connect")
    def test_connects_with_env_vars(self, mock_connect):
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn

        env = {
            "PGVECTOR_HOST": "test-host",
            "PGVECTOR_PORT": "5432",
            "PGVECTOR_DB": "testdb",
            "PGVECTOR_USER": "testuser",
            "PGVECTOR_PASSWORD": "testpass",
        }
        with patch.dict(os.environ, env):
            from src.common.vector_db import get_connection
            conn = get_connection()

        mock_connect.assert_called_once_with(
            host="test-host",
            port=5432,
            dbname="testdb",
            user="testuser",
            password="testpass",
        )
        assert conn is mock_conn

    @patch("psycopg2.connect")
    def test_uses_default_port(self, mock_connect):
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn

        env = {
            "PGVECTOR_HOST": "test-host",
            "PGVECTOR_DB": "testdb",
            "PGVECTOR_USER": "testuser",
            "PGVECTOR_PASSWORD": "testpass",
        }
        with patch.dict(os.environ, env, clear=False):
            os.environ.pop("PGVECTOR_PORT", None)
            from importlib import reload
            import src.common.vector_db as vdb
            reload(vdb)
            conn = vdb.get_connection()

        mock_connect.assert_called_once_with(
            host="test-host",
            port=5432,
            dbname="testdb",
            user="testuser",
            password="testpass",
        )
