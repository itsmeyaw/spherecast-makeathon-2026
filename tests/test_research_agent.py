import json
from unittest.mock import MagicMock, patch

from langchain_core.messages import AIMessage


def test_research_substitution_returns_verdict_shape():
    verdict_json = json.dumps({
        "facts": ["Ascorbic acid is the same chemical entity as vitamin C"],
        "rules": ["FDA allows chemical name variants on supplement facts panels"],
        "inference": "The substitute is chemically identical to the original.",
        "caveats": ["No dosage equivalence data available"],
        "evidence_rows": [
            {
                "source_type": "pgvector",
                "source_label": "Document search",
                "source_uri": "s3://docs/product.json",
                "fact_type": "product_context",
                "fact_value": "Product contains vitamin C as ascorbic acid",
                "quality_score": 0.9,
                "snippet": "Supplement Facts: Vitamin C (as Ascorbic Acid) 1000mg",
            }
        ],
    })
    mock_agent = MagicMock()
    mock_agent.stream.return_value = iter([
        {"model": {"messages": [AIMessage(content=verdict_json)]}},
    ])

    with patch("src.compliance.research_agent.create_deep_agent", return_value=mock_agent):
        with patch("src.compliance.research_agent.ChatBedrockConverse"):
            from src.compliance.research_agent import research_substitution

            result = research_substitution(
                original={
                    "original_ingredient": "vitamin-c",
                    "group": {"canonical_name": "vitamin-c", "function": "antioxidant"},
                    "requirements": [],
                },
                substitute={"current_match_name": "ascorbic-acid", "match_type": "alias"},
                product_sku="FG-iherb-10421",
                company_name="NOW Foods",
            )

    assert "facts" in result
    assert "rules" in result
    assert "inference" in result
    assert "caveats" in result
    assert "evidence_rows" in result
    assert isinstance(result["facts"], list)
    assert isinstance(result["evidence_rows"], list)
    assert result["evidence_rows"][0]["source_type"] == "pgvector"


def test_research_substitution_excluded_tools_when_no_brave_key():
    with patch("src.compliance.research_agent.create_deep_agent"):
        with patch("src.compliance.research_agent.ChatBedrockConverse"):
            with patch.dict("os.environ", {}, clear=False):
                import os
                os.environ.pop("BRAVE_API_KEY", None)
                from src.compliance.research_agent import _build_tools
                tools = _build_tools()

    tool_names = [t.__name__ for t in tools]
    assert "search_documents" in tool_names
    assert "query_database" in tool_names
    assert "web_search" not in tool_names


def test_research_substitution_with_list_content():
    import json as _json
    verdict_json = _json.dumps({
        "facts": ["Ascorbic acid is vitamin C"],
        "rules": ["FDA allows name variants"],
        "inference": "Chemically identical.",
        "caveats": ["No dosage data"],
        "evidence_rows": [
            {
                "source_type": "pgvector",
                "source_label": "Doc search",
                "source_uri": "s3://docs/product.json",
                "fact_type": "product_context",
                "fact_value": "Contains vitamin C",
                "quality_score": 0.9,
                "snippet": "Vitamin C (as Ascorbic Acid) 1000mg",
            }
        ],
    })
    mock_agent = MagicMock()
    mock_agent.stream.return_value = iter([
        {"model": {"messages": [AIMessage(content=[{"type": "text", "text": verdict_json}])]}},
    ])

    with patch("src.compliance.research_agent.create_deep_agent", return_value=mock_agent):
        with patch("src.compliance.research_agent.ChatBedrockConverse"):
            from src.compliance.research_agent import research_substitution

            result = research_substitution(
                original={
                    "original_ingredient": "vitamin-c",
                    "group": {"canonical_name": "vitamin-c", "function": "antioxidant"},
                    "requirements": [],
                },
                substitute={"current_match_name": "ascorbic-acid", "match_type": "alias"},
                product_sku="FG-iherb-10421",
                company_name="NOW Foods",
            )

    assert result["inference"] == "Chemically identical."
    assert result["evidence_rows"][0]["source_type"] == "pgvector"


def test_build_tools_includes_search_tds():
    with patch("src.compliance.research_agent.create_deep_agent"):
        with patch("src.compliance.research_agent.ChatBedrockConverse"):
            from src.compliance.research_agent import _build_tools
            tools = _build_tools()

    tool_names = [t.__name__ for t in tools]
    assert "search_tds" in tool_names
