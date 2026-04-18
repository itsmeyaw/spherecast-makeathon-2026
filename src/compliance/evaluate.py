import json
from src.common.bedrock import invoke_model_json
from src.common.vector_store import retrieve


def evaluate_substitution(original, substitute, product_sku, company_name):
    kb_product_context = retrieve(f"{company_name} {product_sku} supplement facts certifications claims")
    kb_fda_context = retrieve(f"FDA dietary supplement labeling requirements {original['group']['canonical_name']}")

    product_evidence = "\n".join(
        f"[Source: {r['source']}]\n{r['text']}" for r in kb_product_context
    )
    fda_evidence = "\n".join(
        f"[Source: {r['source']}]\n{r['text']}" for r in kb_fda_context
    )

    prompt = f"""You are an FDA dietary supplement compliance expert evaluating whether an ingredient substitution is safe and compliant.

PRODUCT: {company_name} — {product_sku}
ORIGINAL INGREDIENT: {original['original_ingredient']} (function: {original['group']['function']})
PROPOSED SUBSTITUTE: {substitute['ingredient_name']}

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
    "original": "{original['original_ingredient']}",
    "substitute": "{substitute['ingredient_name']}",
    "verdict": "safe" | "risky" | "incompatible" | "insufficient-evidence",
    "confidence": "high" | "medium" | "low",
    "facts": ["list of facts from scraped product data"],
    "rules": ["list of applicable FDA rules"],
    "inference": "your reasoning connecting facts to rules",
    "sources": ["list of source URLs/references used"],
    "caveats": ["list of limitations or uncertainties"]
}}"""

    system = "You are an FDA compliance expert. Return valid JSON only. Never fabricate evidence."

    result = invoke_model_json(prompt, system=system)

    if isinstance(result, dict):
        source_list = [r["source"] for r in kb_product_context + kb_fda_context]
        result["kb_sources"] = source_list
    return result


def evaluate_all_candidates(candidates, product_sku, company_name):
    evaluations = []
    for component in candidates:
        component_evals = []
        for substitute in component["candidates"]:
            evaluation = evaluate_substitution(
                original=component,
                substitute=substitute,
                product_sku=product_sku,
                company_name=company_name,
            )
            component_evals.append(evaluation)
        evaluations.append({
            "original_ingredient": component["original_ingredient"],
            "group": component["group"],
            "current_suppliers": component["current_suppliers"],
            "evaluations": component_evals,
        })
    return evaluations
