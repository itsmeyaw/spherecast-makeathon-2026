BLOCKER_SCORE = {
    "pass_known_blockers": 30,
    "needs_review": 10,
    "blocked": -40,
}

EVIDENCE_SCORE = {"high": 25, "medium": 12, "low": 0}
MATCH_SCORE = {"exact": 40, "alias": 15, "hypothesis": 0}


def score_opportunity(
    products_affected_count,
    suppliers_affected_count,
    evidence_completeness,
    blocker_state,
    match_type,
):
    return (
        MATCH_SCORE.get(match_type, 0)
        + BLOCKER_SCORE.get(blocker_state, 0)
        + EVIDENCE_SCORE.get(evidence_completeness, 0)
        + (products_affected_count * 2)
        + suppliers_affected_count
    )


def rank_evaluations(evaluations):
    """
    Backward-compatible helper for the old one-shot path.
    """
    ranked = []
    for component in evaluations:
        sorted_evals = sorted(
            component["evaluations"],
            key=lambda e: (
                -score_opportunity(
                    products_affected_count=e.get("products_affected_count", 1),
                    suppliers_affected_count=e.get("suppliers_affected_count", 1),
                    evidence_completeness=e.get("evidence_completeness", "low"),
                    blocker_state=e.get("blocker_state", _legacy_blocker_state(e.get("verdict"))),
                    match_type=e.get("match_type", _legacy_match_type(e.get("confidence"))),
                ),
                e.get("substitute", ""),
            ),
        )

        ranked.append(
            {
                "original_ingredient": component["original_ingredient"],
                "group": component["group"],
                "current_suppliers": component["current_suppliers"],
                "ranked_substitutes": sorted_evals,
                "has_alternatives": bool(sorted_evals),
                "safe_count": sum(
                    1
                    for e in sorted_evals
                    if e.get("blocker_state", _legacy_blocker_state(e.get("verdict"))) == "pass_known_blockers"
                ),
                "risky_count": sum(
                    1
                    for e in sorted_evals
                    if e.get("blocker_state", _legacy_blocker_state(e.get("verdict"))) == "needs_review"
                ),
                "total_candidates": len(sorted_evals),
            }
        )

    ranked.sort(key=lambda item: (-item["safe_count"], -item["total_candidates"]))
    return ranked


def _legacy_blocker_state(verdict):
    if verdict == "safe":
        return "pass_known_blockers"
    if verdict == "incompatible":
        return "blocked"
    return "needs_review"


def _legacy_match_type(confidence):
    if confidence == "high":
        return "exact"
    if confidence == "medium":
        return "alias"
    return "hypothesis"
