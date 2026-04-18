from unittest.mock import MagicMock, patch


def test_research_substitution_returns_verdict_shape():
    mock_agent = MagicMock()
    mock_agent.invoke.return_value = {
        "structured_response": MagicMock(
            facts=["Ascorbic acid is the same chemical entity as vitamin C"],
            rules=["FDA allows chemical name variants on supplement facts panels"],
            inference="The substitute is chemically identical to the original.",
            caveats=["No dosage equivalence data available"],
            evidence_rows=[
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
        )
    }

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


def test_research_substitution_excluded_tools_when_no_brave_key():
    with patch("src.compliance.research_agent.create_deep_agent") as mock_create:
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
