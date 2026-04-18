from src.evidence.normalize import ingredient_fact_rows
from src.reasoning.blockers import evaluate_blockers


def evidence_completeness_label(match_type, candidate_name):
    has_facts = bool(ingredient_fact_rows(candidate_name))
    if match_type == "exact":
        return "high"
    if has_facts and match_type == "alias":
        return "medium"
    return "low"


def compare_candidate(requirements, candidate):
    blocker_result = evaluate_blockers(requirements, candidate, candidate["match_type"])
    completeness = evidence_completeness_label(candidate["match_type"], candidate["current_match_name"])
    return {
        "match_type": candidate["match_type"],
        "candidate_name": candidate["current_match_name"],
        "canonical_name": candidate["canonical_name"],
        "blocker_state": blocker_result["state"],
        "blockers": blocker_result["blockers"],
        "blocker_summary": blocker_result["summary"],
        "evidence_completeness": completeness,
    }

