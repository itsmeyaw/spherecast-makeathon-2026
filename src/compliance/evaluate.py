from src.reasoning.compare import compare_candidate
from src.reasoning.explain import explain_candidate


def evaluate_substitution(original, substitute, product_sku, company_name):
    requirements = original.get("requirements", [])
    comparison = compare_candidate(requirements, substitute)
    explanation = explain_candidate(original["original_ingredient"], substitute["current_match_name"], comparison)
    return {
        "original": original["original_ingredient"],
        "substitute": substitute["current_match_name"],
        "verdict": comparison["blocker_state"],
        "confidence": {"exact": "high", "alias": "medium", "hypothesis": "low"}[substitute["match_type"]],
        "facts": [],
        "rules": [blocker["message"] for blocker in comparison["blockers"]],
        "inference": explanation,
        "sources": [
            f"demo://product/{product_sku}",
            f"demo://ingredient/{substitute['current_match_name']}",
        ],
        "caveats": ["Deterministic demo blocker engine only. Human review remains required for non-exact substitutions."],
        "blocker_state": comparison["blocker_state"],
        "evidence_completeness": comparison["evidence_completeness"],
        "match_type": substitute["match_type"],
    }


def evaluate_all_candidates(candidates, product_sku, company_name):
    evaluations = []
    for component in candidates:
        component_evals = []
        requirements = component.get("requirements", [])
        for substitute in component["candidates"]:
            enriched_original = dict(component)
            enriched_original["requirements"] = requirements
            component_evals.append(
                evaluate_substitution(
                    original=enriched_original,
                    substitute={
                        **substitute,
                        "current_match_name": substitute["ingredient_name"],
                        "match_type": substitute.get("match_type", "hypothesis"),
                    },
                    product_sku=product_sku,
                    company_name=company_name,
                )
            )
        evaluations.append(
            {
                "original_ingredient": component["original_ingredient"],
                "group": component["group"],
                "current_suppliers": component["current_suppliers"],
                "evaluations": component_evals,
            }
        )
    return evaluations
