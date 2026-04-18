import json
import os
import pytest
from unittest.mock import patch, MagicMock


class TestEmbedText:
    @patch("src.common.embeddings.get_bedrock_client")
    def test_returns_embedding_vector(self, mock_get_client):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        fake_embedding = [0.1] * 1024
        response_body = json.dumps({"embedding": fake_embedding}).encode()
        mock_response = MagicMock()
        mock_response.read.return_value = response_body
        mock_client.invoke_model.return_value = {"body": mock_response}

        from src.common.embeddings import embed_text
        result = embed_text("test query")

        assert result == fake_embedding
        assert len(result) == 1024
        mock_client.invoke_model.assert_called_once()
        call_kwargs = mock_client.invoke_model.call_args[1]
        assert call_kwargs["modelId"] == "amazon.titan-embed-text-v2:0"
        body = json.loads(call_kwargs["body"])
        assert body["inputText"] == "test query"

    @patch("src.common.bedrock.get_bedrock_client")
    def test_uses_custom_model_id(self, mock_get_client):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        fake_embedding = [0.2] * 1024
        response_body = json.dumps({"embedding": fake_embedding}).encode()
        mock_response = MagicMock()
        mock_response.read.return_value = response_body
        mock_client.invoke_model.return_value = {"body": mock_response}

        with patch.dict(os.environ, {"EMBEDDING_MODEL_ID": "custom-model"}):
            from importlib import reload
            import src.common.embeddings as emb
            reload(emb)
            result = emb.embed_text("test")

        call_kwargs = mock_client.invoke_model.call_args[1]
        assert call_kwargs["modelId"] == "custom-model"


class TestEmbedTexts:
    @patch("src.common.embeddings.embed_text")
    def test_embeds_multiple_texts(self, mock_embed):
        mock_embed.side_effect = [[0.1] * 1024, [0.2] * 1024]

        from src.common.embeddings import embed_texts
        results = embed_texts(["text1", "text2"])

        assert len(results) == 2
        assert mock_embed.call_count == 2
