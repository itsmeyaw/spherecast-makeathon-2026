VERDICT_ORDER = {"safe": 0, "risky": 1, "insufficient-evidence": 2, "incompatible": 3}
CONFIDENCE_ORDER = {"high": 0, "medium": 1, "low": 2}


def rank_evaluations(evaluations):
    ranked = []
    for component in evaluations:
        sorted_evals = sorted(
            component["evaluations"],
            key=lambda e: (
                VERDICT_ORDER.get(e.get("verdict", "incompatible"), 3),
                CONFIDENCE_ORDER.get(e.get("confidence", "low"), 2),
            ),
        )

        safe_count = sum(1 for e in sorted_evals if e.get("verdict") == "safe")
        risky_count = sum(1 for e in sorted_evals if e.get("verdict") == "risky")

        ranked.append({
            "original_ingredient": component["original_ingredient"],
            "group": component["group"],
            "current_suppliers": component["current_suppliers"],
            "ranked_substitutes": sorted_evals,
            "has_alternatives": len(sorted_evals) > 0,
            "safe_count": safe_count,
            "risky_count": risky_count,
            "total_candidates": len(sorted_evals),
        })

    ranked.sort(key=lambda r: (-r["safe_count"], -r["total_candidates"]))
    return ranked
