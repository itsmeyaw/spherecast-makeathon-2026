import json
import logging
import os

from src.common.bedrock import invoke_model_json
from src.common.vector_store import retrieve
from src.compliance.research_agent import research_substitution
from src.reasoning.compare import compare_candidate
from src.reasoning.explain import explain_candidate

logger = logging.getLogger(__name__)


def _blocker_evaluation(original, substitute, product_sku):
    requirements = original.get("requirements", [])
    comparison = compare_candidate(requirements, substitute)
    explanation = explain_candidate(
        original["original_ingredient"], substitute["current_match_name"], comparison
    )
    return {
        "verdict": comparison["blocker_state"],
        "confidence": {"exact": "high", "alias": "medium", "hypothesis": "low"}[
            substitute["match_type"]
        ],
        "rules": [blocker["message"] for blocker in comparison["blockers"]],
        "inference": explanation,
        "blocker_state": comparison["blocker_state"],
        "evidence_completeness": comparison["evidence_completeness"],
    }


def _rag_evaluation(original, substitute, product_sku, company_name):
    kb_product_context = retrieve(
        f"{company_name} {product_sku} supplement facts certifications claims"
    )
    kb_fda_context = retrieve(
        f"FDA dietary supplement labeling requirements {original['group']['canonical_name']}"
    )

    product_evidence = "\n".join(
        f"[Source: {r['source']}]\n{r['text']}" for r in kb_product_context
    )
    fda_evidence = "\n".join(
        f"[Source: {r['source']}]\n{r['text']}" for r in kb_fda_context
    )

    prompt = f"""You are an FDA dietary supplement compliance expert evaluating whether an ingredient substitution is safe and compliant.

PRODUCT: {company_name} — {product_sku}
ORIGINAL INGREDIENT: {original['original_ingredient']} (function: {original['group']['function']})
PROPOSED SUBSTITUTE: {substitute.get('current_match_name') or substitute['ingredient_name']}

PRODUCT INFORMATION FROM KNOWLEDGE BASE:
{product_evidence if product_evidence.strip() else "No product information available in knowledge base."}

FDA REGULATORY CONTEXT FROM KNOWLEDGE BASE:
{fda_evidence if fda_evidence.strip() else "No specific FDA guidance found in knowledge base."}

EVALUATE THIS SUBSTITUTION:
1. Does the substitute serve the same functional role?
2. Are there FDA labeling implications (name change on supplement facts panel)?
3. Does it conflict with any product claims (organic, non-GMO, allergen-free, etc.)?
4. Are there allergen implications?
5. Are there bioavailability or efficacy differences?

IMPORTANT:
- Only state facts you can support with the evidence above.
- If evidence is missing, say "insufficient evidence" for that aspect.
- Never guess about compliance — flag uncertainty explicitly.

Return a JSON object:
{{
    "facts": ["list of facts from scraped product data"],
    "rules": ["list of applicable FDA rules"],
    "inference": "your reasoning connecting facts to rules",
    "caveats": ["list of limitations or uncertainties"]
}}"""

    system = "You are an FDA compliance expert. Return valid JSON only. Never fabricate evidence."

    result = invoke_model_json(prompt, system=system)
    source_list = [r["source"] for r in kb_product_context + kb_fda_context]
    if isinstance(result, dict):
        result["kb_sources"] = source_list
    else:
        result = {"kb_sources": source_list}
    return result


def evaluate_substitution(original, substitute, product_sku, company_name):
    blocker_result = _blocker_evaluation(original, substitute, product_sku)

    research_enabled = os.environ.get("RESEARCH_ENABLED", "true").lower() == "true"

    rag_result = {}
    if research_enabled:
        try:
            rag_result = research_substitution(
                original=original,
                substitute=substitute,
                product_sku=product_sku,
                company_name=company_name,
            )
        except Exception:
            logger.warning(
                "Research agent failed for %s → %s, falling back to RAG",
                original["original_ingredient"],
                substitute.get("current_match_name") or substitute.get("ingredient_name"),
                exc_info=True,
            )

    if not rag_result:
        try:
            rag_result = _rag_evaluation(original, substitute, product_sku, company_name)
        except Exception:
            logger.warning(
                "RAG evaluation also unavailable for %s → %s, using blocker engine only",
                original["original_ingredient"],
                substitute.get("current_match_name") or substitute.get("ingredient_name"),
                exc_info=True,
            )

    rag_facts = rag_result.get("facts", [])
    rag_rules = rag_result.get("rules", [])
    rag_inference = rag_result.get("inference", "")
    rag_caveats = rag_result.get("caveats", [])

    combined_rules = blocker_result["rules"] + [
        r for r in rag_rules if r not in blocker_result["rules"]
    ]
    combined_inference = blocker_result["inference"]
    if rag_inference:
        combined_inference += "\n\n[Research-grounded analysis]\n" + rag_inference

    caveats = rag_caveats if rag_caveats else [
        "Research agent and RAG evaluation unavailable. Deterministic blocker engine only."
    ]

    sub_name = substitute.get("current_match_name") or substitute["ingredient_name"]

    return {
        "original": original["original_ingredient"],
        "substitute": sub_name,
        "verdict": blocker_result["verdict"],
        "confidence": blocker_result["confidence"],
        "facts": rag_facts,
        "rules": combined_rules,
        "inference": combined_inference,
        "sources": [
            f"demo://product/{product_sku}",
            f"demo://ingredient/{sub_name}",
        ] + rag_result.get("kb_sources", []),
        "caveats": caveats,
        "blocker_state": blocker_result["blocker_state"],
        "evidence_completeness": blocker_result["evidence_completeness"],
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
