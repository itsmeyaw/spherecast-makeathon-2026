from unittest.mock import patch


def test_evaluate_substitution_uses_research_agent():
    mock_blocker = {
        "verdict": "pass_known_blockers",
        "confidence": "high",
        "rules": ["No known blockers"],
        "inference": "Passed blocker checks.",
        "blocker_state": "pass_known_blockers",
        "evidence_completeness": "high",
    }
    mock_research = {
        "facts": ["Ascorbic acid is vitamin C"],
        "rules": ["FDA 21 CFR 101.36"],
        "inference": "Chemically identical.",
        "caveats": [],
        "evidence_rows": [
            {
                "source_type": "pgvector",
                "source_label": "Document search",
                "source_uri": "s3://test",
                "fact_type": "identity",
                "fact_value": "same compound",
                "quality_score": 0.95,
                "snippet": "test",
            }
        ],
        "kb_sources": ["s3://test"],
    }

    with patch("src.compliance.evaluate._blocker_evaluation", return_value=mock_blocker):
        with patch("src.compliance.evaluate.research_substitution", return_value=mock_research):
            from src.compliance.evaluate import evaluate_substitution

            result = evaluate_substitution(
                original={
                    "original_ingredient": "vitamin-c",
                    "group": {"canonical_name": "vitamin-c", "function": "antioxidant"},
                    "requirements": [],
                },
                substitute={"current_match_name": "ascorbic-acid", "match_type": "alias", "ingredient_name": "ascorbic-acid"},
                product_sku="FG-iherb-10421",
                company_name="NOW Foods",
            )

    assert result["verdict"] == "pass_known_blockers"
    assert "Ascorbic acid is vitamin C" in result["facts"]
    assert "FDA 21 CFR 101.36" in result["rules"]


def test_evaluate_substitution_falls_back_on_research_failure():
    mock_blocker = {
        "verdict": "pass_known_blockers",
        "confidence": "high",
        "rules": ["No known blockers"],
        "inference": "Passed blocker checks.",
        "blocker_state": "pass_known_blockers",
        "evidence_completeness": "high",
    }
    mock_rag = {
        "facts": ["fallback fact"],
        "rules": [],
        "inference": "fallback",
        "caveats": ["RAG only"],
        "kb_sources": ["s3://fallback"],
    }

    with patch("src.compliance.evaluate._blocker_evaluation", return_value=mock_blocker):
        with patch("src.compliance.evaluate.research_substitution", side_effect=Exception("agent failed")):
            with patch("src.compliance.evaluate._rag_evaluation", return_value=mock_rag):
                from src.compliance.evaluate import evaluate_substitution

                result = evaluate_substitution(
                    original={
                        "original_ingredient": "vitamin-c",
                        "group": {"canonical_name": "vitamin-c", "function": "antioxidant"},
                        "requirements": [],
                    },
                    substitute={"current_match_name": "ascorbic-acid", "match_type": "alias", "ingredient_name": "ascorbic-acid"},
                    product_sku="FG-iherb-10421",
                    company_name="NOW Foods",
                )

    assert "fallback fact" in result["facts"]
