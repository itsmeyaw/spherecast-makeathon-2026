from src.common.db import get_bom_components, get_finished_goods, parse_ingredient_name
from src.evidence.normalize import ingredient_fact_rows
from src.evidence.store import replace_opportunity_evidence
from src.opportunity.store import (
    reset_workspace_analysis,
    replace_opportunity_candidates,
    upsert_opportunity,
    upsert_requirement_profiles,
)
from src.reasoning.compare import compare_candidate
from src.reasoning.explain import explain_candidate
from src.reasoning.requirements import build_requirement_profile, collect_requirement_evidence
from src.recommend.rank import score_opportunity
from src.substitute.find_candidates import find_candidates_for_component


def _confidence_for_match_type(match_type):
    return {"exact": "high", "alias": "medium", "hypothesis": "low"}[match_type]


def _aggregate_blocker_state(candidate_results):
    states = {result["comparison"]["blocker_state"] for result in candidate_results}
    if "blocked" in states:
        return "blocked"
    if "needs_review" in states:
        return "needs_review"
    return "pass_known_blockers"


def _aggregate_evidence(candidate_results, match_type):
    levels = {result["comparison"]["evidence_completeness"] for result in candidate_results}
    if match_type == "exact" or "high" in levels:
        return "high"
    if "medium" in levels:
        return "medium"
    return "low"


def _build_candidate_rows(original_ingredient, candidate_results):
    rows = []
    for result in candidate_results:
        candidate = result["candidate"]
        comparison = result["comparison"]
        explanation = explain_candidate(original_ingredient, candidate["current_match_name"], comparison)
        suppliers = candidate["candidate_suppliers"] or [None]
        for supplier in suppliers:
            rows.append(
                {
                    "candidate_product_id": candidate["product_id"],
                    "candidate_supplier_id": supplier["supplier_id"] if supplier else None,
                    "match_type": candidate["match_type"],
                    "candidate_summary": comparison["blocker_summary"],
                    "blocker_state": comparison["blocker_state"],
                    "evidence_completeness": comparison["evidence_completeness"],
                    "explanation": explanation,
                    "candidate_name": candidate["current_match_name"],
                    "candidate_supplier_name": supplier["supplier_name"] if supplier else None,
                }
            )
    return rows


def _build_evidence_rows(finished_product, component, candidate_results):
    evidence_rows = collect_requirement_evidence(finished_product, component)
    evidence_rows.append(
        {
            "source_type": "internal-db",
            "source_label": "Portfolio BOM graph",
            "source_uri": f"sqlite://product/{finished_product['product_id']}",
            "fact_type": "original_component",
            "fact_value": component["original_ingredient"],
            "quality_score": 1.0,
            "snippet": "Finished-product BOM component loaded from the provided SQLite dataset.",
        }
    )
    for result in candidate_results:
        candidate = result["candidate"]
        comparison = result["comparison"]
        evidence_rows.append(
            {
                "source_type": "internal-db",
                "source_label": "Supplier mapping",
                "source_uri": f"sqlite://product/{candidate['product_id']}",
                "fact_type": "candidate_supplier_option",
                "fact_value": f"{candidate['current_match_name']} from {candidate['company_name']}",
                "quality_score": 1.0,
                "snippet": f"Match type {candidate['match_type']} with blocker state {comparison['blocker_state']}.",
            }
        )
        evidence_rows.extend(ingredient_fact_rows(candidate["current_match_name"]))
    return evidence_rows


def _build_opportunity_payload(portfolio_usage, finished_product, component, match_type, candidate_results):
    candidate_names = {component["original_ingredient"]} | {
        result["candidate"]["current_match_name"] for result in candidate_results
    }
    unique_finished_products = set()
    for name in candidate_names:
        unique_finished_products |= portfolio_usage.get(name, set())
    unique_suppliers = {
        supplier["supplier_id"]
        for result in candidate_results
        for supplier in result["candidate"]["candidate_suppliers"]
    }
    blocker_state = _aggregate_blocker_state(candidate_results)
    evidence_completeness = _aggregate_evidence(candidate_results, match_type)
    opportunity_type = (
        "exact-match-consolidation"
        if match_type == "exact"
        else "alias-match-substitute"
        if match_type == "alias"
        else "hypothesis-substitute"
    )
    confidence_label = _confidence_for_match_type(match_type)
    summary = (
        f"{component['original_ingredient']} has {len(candidate_results)} {match_type} option(s) "
        f"covering {len(unique_finished_products)} finished goods and {len(unique_suppliers)} suppliers."
    )

    payload = {
        "company_id": finished_product["company_id"],
        "product_id": finished_product["product_id"],
        "bom_id": component.get("bom_id"),
        "component_product_id": component["original_product_id"],
        "parsed_ingredient_name": component["original_ingredient"],
        "canonical_ingredient_name": component["canonical_names"][0],
        "opportunity_type": opportunity_type,
        "match_type": match_type,
        "confidence_label": confidence_label,
        "products_affected_count": len(unique_finished_products),
        "suppliers_affected_count": len(unique_suppliers),
        "candidate_count": len({result["candidate"]["product_id"] for result in candidate_results}),
        "evidence_completeness": evidence_completeness,
        "blocker_state": blocker_state,
        "summary": summary,
        "priority_score": score_opportunity(
            products_affected_count=len(unique_finished_products),
            suppliers_affected_count=len(unique_suppliers),
            evidence_completeness=evidence_completeness,
            blocker_state=blocker_state,
            match_type=match_type,
        ),
    }
    return payload


def build_all_opportunities(db_path=None):
    reset_workspace_analysis(db_path)
    finished_goods = get_finished_goods(db_path)
    portfolio_usage = {}
    components_by_product = {}

    for finished_product in finished_goods:
        components = get_bom_components(db_path, finished_product["product_id"])
        components_by_product[finished_product["product_id"]] = components
        for component in components:
            ingredient_name = parse_ingredient_name(component["sku"])
            portfolio_usage.setdefault(ingredient_name, set()).add(finished_product["product_id"])

    for finished_product in finished_goods:
        components = components_by_product[finished_product["product_id"]]
        for raw_component in components:
            component = find_candidates_for_component(
                db_path=db_path,
                component=raw_component,
                finished_product=finished_product,
            )
            requirements = build_requirement_profile(finished_product, component)
            upsert_requirement_profiles(
                db_path=db_path,
                product_id=finished_product["product_id"],
                component_product_id=component["original_product_id"],
                requirements=requirements,
            )

            grouped_candidates = {
                "exact": component["exact_candidates"],
                "alias": [candidate for candidate in component["alias_candidates"] if candidate["match_type"] == "alias"],
                "hypothesis": [candidate for candidate in component["alias_candidates"] if candidate["match_type"] == "hypothesis"],
            }

            for match_type, candidates in grouped_candidates.items():
                if not candidates:
                    continue
                candidate_results = [
                    {"candidate": candidate, "comparison": compare_candidate(requirements, candidate)}
                    for candidate in candidates
                ]
                payload = _build_opportunity_payload(
                    portfolio_usage, finished_product, component, match_type, candidate_results
                )
                opportunity_id = upsert_opportunity(db_path=db_path, payload=payload)
                candidate_rows = _build_candidate_rows(component["original_ingredient"], candidate_results)
                replace_opportunity_candidates(
                    db_path=db_path, opportunity_id=opportunity_id, candidates=candidate_rows
                )
                evidence_rows = _build_evidence_rows(finished_product, component, candidate_results)
                for row in evidence_rows:
                    product_id = None
                    supplier_id = None
                    if row["fact_type"] == "candidate_supplier_option":
                        # Candidate evidence stays opportunity-level in the current demo workspace.
                        row["opportunity_candidate_id"] = None
                replace_opportunity_evidence(
                    db_path=db_path, opportunity_id=opportunity_id, evidence_rows=evidence_rows
                )
