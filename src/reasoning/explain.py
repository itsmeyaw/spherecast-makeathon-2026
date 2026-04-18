from src.scraper.cache import get_cached_ingredient_facts


def explain_candidate(original_ingredient, candidate_name, comparison):
    candidate_facts = get_cached_ingredient_facts(candidate_name) or {}
    fragments = [
        f"{candidate_name} is being evaluated against {original_ingredient}.",
        f"Match type: {comparison['match_type']}.",
        f"Known blocker state: {comparison['blocker_state']}.",
    ]
    if candidate_facts.get("notes"):
        fragments.append(candidate_facts["notes"])
    if comparison["blockers"]:
        fragments.append("Blockers: " + "; ".join(blocker["message"] for blocker in comparison["blockers"]))
    else:
        fragments.append("The candidate passed the narrow deterministic blocker checks used in the demo workspace.")
    return " ".join(fragments)
