# tests/test_vector_store.py
import pytest
from unittest.mock import patch, MagicMock


class TestRetrieve:
    @patch("src.common.vector_store.get_connection")
    @patch("src.common.vector_store.embed_text")
    def test_returns_merged_results(self, mock_embed, mock_get_conn):
        mock_embed.return_value = [0.1] * 1024

        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value = mock_cur
        mock_get_conn.return_value = mock_conn

        # Vector search returns 2 results
        mock_cur.fetchall.side_effect = [
            [
                (1, "chunk A content", "s3-key-a", "Section A", "{}"),
                (2, "chunk B content", "s3-key-b", "Section B", "{}"),
            ],
            # Keyword search returns 2 results (one overlapping)
            [
                (2, "chunk B content", "s3-key-b", "Section B", "{}"),
                (3, "chunk C content", "s3-key-c", "Section C", "{}"),
            ],
        ]

        from src.common.vector_store import retrieve
        results = retrieve("test query", n_results=3)

        assert len(results) <= 3
        assert all("text" in r for r in results)
        assert all("score" in r for r in results)
        assert all("source" in r for r in results)
        assert all("section_title" in r for r in results)
        mock_conn.close.assert_called_once()

    @patch("src.common.vector_store.get_connection")
    @patch("src.common.vector_store.embed_text")
    def test_empty_results(self, mock_embed, mock_get_conn):
        mock_embed.return_value = [0.1] * 1024

        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value = mock_cur
        mock_get_conn.return_value = mock_conn
        mock_cur.fetchall.side_effect = [[], []]

        from src.common.vector_store import retrieve
        results = retrieve("query with no results")

        assert results == []
        mock_conn.close.assert_called_once()

    @patch("src.common.vector_store.get_connection")
    @patch("src.common.vector_store.embed_text")
    def test_rrf_ranks_items_in_both_searches_higher(self, mock_embed, mock_get_conn):
        mock_embed.return_value = [0.1] * 1024

        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value = mock_cur
        mock_get_conn.return_value = mock_conn

        # Chunk 2 appears in both searches — should rank highest
        mock_cur.fetchall.side_effect = [
            [
                (1, "only in vector", "key-a", "Sec A", "{}"),
                (2, "in both searches", "key-b", "Sec B", "{}"),
            ],
            [
                (2, "in both searches", "key-b", "Sec B", "{}"),
                (3, "only in keyword", "key-c", "Sec C", "{}"),
            ],
        ]

        from src.common.vector_store import retrieve
        results = retrieve("test", n_results=3)

        assert results[0]["text"] == "in both searches"
