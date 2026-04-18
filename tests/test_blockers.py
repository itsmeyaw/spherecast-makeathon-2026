from src.reasoning.blockers import evaluate_blockers


def test_exact_match_passes_when_no_known_blockers():
    requirements = [
        {
            "requirement_type": "ingredient_identity",
            "requirement_value": "vitamin-c",
            "source": "internal-bom",
            "confidence": "high",
        }
    ]
    candidate = {"current_match_name": "vitamin-c", "match_type": "exact"}
    result = evaluate_blockers(requirements, candidate, "exact")
    assert result["state"] == "pass_known_blockers"


def test_hypothesis_defaults_to_needs_review():
    requirements = [
        {
            "requirement_type": "ingredient_identity",
            "requirement_value": "magnesium-source",
            "source": "internal-bom",
            "confidence": "high",
        }
    ]
    candidate = {"current_match_name": "magnesium-citrate", "match_type": "hypothesis"}
    result = evaluate_blockers(requirements, candidate, "hypothesis")
    assert result["state"] == "needs_review"


def test_vegan_conflict_blocks_candidate():
    requirements = [
        {
            "requirement_type": "vegan_compatible",
            "requirement_value": "true",
            "source": "demo-product-pack",
            "confidence": "medium",
        }
    ]
    candidate = {"current_match_name": "gelatin", "match_type": "alias"}
    result = evaluate_blockers(requirements, candidate, "alias")
    assert result["state"] == "blocked"
    assert any(blocker["category"] == "vegan_conflict" for blocker in result["blockers"])
