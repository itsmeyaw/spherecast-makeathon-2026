from src.scraper.cache import get_cached_ingredient_facts


def evaluate_blockers(requirements, candidate, match_type):
    original_allergens = {
        requirement["requirement_value"]
        for requirement in requirements
        if requirement["requirement_type"] == "known_allergen"
    }
    candidate_facts = get_cached_ingredient_facts(candidate["current_match_name"]) or {}
    candidate_allergens = set(candidate_facts.get("allergens", []))
    candidate_certs = set(candidate_facts.get("certifications", []))
    required_certs = {
        requirement["requirement_value"]
        for requirement in requirements
        if requirement["requirement_type"] == "required_certification"
    }

    blockers = []

    if match_type == "hypothesis":
        blockers.append(
            {
                "category": "missing_critical_evidence",
                "severity": "review",
                "message": "Hypothesis-only substitute. The workspace will not auto-approve it.",
            }
        )

    if match_type == "alias":
        evidence_strength = candidate_facts.get("evidence_strength")
        has_identity_review = "demo-identity-reviewed" in candidate_certs
        if not (evidence_strength == "high" and has_identity_review):
            blockers.append(
                {
                    "category": "missing_critical_evidence",
                    "severity": "review",
                    "message": "Alias match lacks high-strength identity evidence in the local demo pack.",
                }
            )

    if any(
        requirement["requirement_type"] == "vegan_compatible" and requirement["requirement_value"] == "true"
        for requirement in requirements
    ) and candidate_facts.get("vegan_compatible") is False:
        blockers.append(
            {
                "category": "vegan_conflict",
                "severity": "block",
                "message": "Candidate is not vegan-compatible while the preserved requirement is vegan compatibility.",
            }
        )

    introduced_allergens = sorted(candidate_allergens - original_allergens)
    if introduced_allergens:
        blockers.append(
            {
                "category": "allergen_conflict",
                "severity": "block",
                "message": f"Candidate introduces new allergen exposure: {', '.join(introduced_allergens)}.",
            }
        )

    missing_certs = sorted(required_certs - candidate_certs)
    if missing_certs:
        blockers.append(
            {
                "category": "certification_mismatch",
                "severity": "review",
                "message": f"Candidate is missing required certification evidence: {', '.join(missing_certs)}.",
            }
        )

    if match_type in {"alias", "hypothesis"} and not candidate_facts:
        blockers.append(
            {
                "category": "missing_critical_evidence",
                "severity": "review",
                "message": "Alias or hypothesis candidate has no cached ingredient facts in the demo workspace.",
            }
        )

    if any(blocker["severity"] == "block" for blocker in blockers):
        state = "blocked"
    elif blockers:
        state = "needs_review"
    else:
        state = "pass_known_blockers"

    summary = "; ".join(blocker["message"] for blocker in blockers) or "No known blockers triggered in the narrow demo rule set."
    return {"state": state, "blockers": blockers, "summary": summary}
