import argparse
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.common.db import (
    get_bom_components,
    get_finished_goods,
    parse_ingredient_name,
)
from src.compliance.research_agent import research_substitution_stream
from src.opportunity.store import ensure_workspace_ready
from src.substitute.find_candidates import find_candidates_for_component

GREEN = "\033[92m"
ORANGE = "\033[93m"
RED = "\033[91m"
GRAY = "\033[90m"
RESET = "\033[0m"
BOLD = "\033[1m"

VERDICT_COLORS = {
    "safe": GREEN,
    "pass_known_blockers": GREEN,
    "risky": ORANGE,
    "needs_review": ORANGE,
    "incompatible": RED,
    "blocked": RED,
    "insufficient-evidence": GRAY,
}


def find_product_by_sku(sku):
    for product in get_finished_goods():
        if product["sku"] == sku:
            return product
    return None


def find_component_by_ingredient(product, ingredient_name):
    components = get_bom_components(product_id=product["product_id"])
    for component in components:
        if parse_ingredient_name(component["sku"]) == ingredient_name:
            return component
    return None


def print_verdict(candidate_name, result):
    verdict = result.get("verdict", result.get("blocker_state", "unknown"))
    color = VERDICT_COLORS.get(verdict, GRAY)
    print(f"\n{BOLD}Candidate: {candidate_name}{RESET}")
    print(f"  Verdict: {color}{verdict.upper()}{RESET}")
    print(f"  Confidence: {result.get('confidence', 'unknown')}")

    if result.get("facts"):
        print(f"  {BOLD}Facts:{RESET}")
        for fact in result["facts"]:
            print(f"    - {fact}")

    if result.get("rules"):
        print(f"  {BOLD}Rules:{RESET}")
        for rule in result["rules"]:
            print(f"    - {rule}")

    if result.get("inference"):
        print(f"  {BOLD}Reasoning:{RESET} {result['inference']}")

    if result.get("caveats"):
        print(f"  {BOLD}Caveats:{RESET}")
        for caveat in result["caveats"]:
            print(f"    - {caveat}")

    if result.get("sources"):
        print(f"  {BOLD}Sources:{RESET}")
        for source in result["sources"]:
            print(f"    - {source}")


def main():
    parser = argparse.ArgumentParser(
        description="Run the agentic research agent for a product ingredient"
    )
    parser.add_argument("--product-sku", required=True, help="Finished product SKU (e.g. FG-iherb-10421)")
    parser.add_argument("--original", required=True, help="Original ingredient name (e.g. vitamin-d3)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging")
    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.INFO)
    else:
        logging.basicConfig(level=logging.WARNING)

    ensure_workspace_ready()

    product = find_product_by_sku(args.product_sku)
    if not product:
        print(f"{RED}Error: Product '{args.product_sku}' not found.{RESET}", file=sys.stderr)
        sys.exit(1)

    component = find_component_by_ingredient(product, args.original)
    if not component:
        print(
            f"{RED}Error: Ingredient '{args.original}' not found in BOM for {args.product_sku}.{RESET}",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"{BOLD}Product:{RESET} {product['company_name']} — {product['sku']}")
    print(f"{BOLD}Original ingredient:{RESET} {args.original}")

    candidates_data = find_candidates_for_component(component=component, finished_product=product)
    all_candidates = candidates_data["exact_candidates"] + candidates_data["alias_candidates"]

    if not all_candidates:
        print(f"\n{GRAY}No substitution candidates found for {args.original}.{RESET}")
        sys.exit(0)

    print(f"\nFound {len(all_candidates)} candidate(s). Researching...\n")
    print("=" * 60)

    original_info = {
        "original_ingredient": candidates_data["original_ingredient"],
        "group": {
            "canonical_name": ", ".join(candidates_data["canonical_names"]),
            "function": "reviewed-alias-layer" if candidates_data["alias_candidates"] else "exact-match",
        },
        "requirements": [],
    }

    for candidate in all_candidates:
        sub_info = {
            "current_match_name": candidate["current_match_name"],
            "match_type": candidate["match_type"],
            "ingredient_name": candidate["current_match_name"],
        }

        try:
            result = None
            for event_type, data in research_substitution_stream(
                original=original_info,
                substitute=sub_info,
                product_sku=product["sku"],
                company_name=product["company_name"],
            ):
                if event_type == "tool_call":
                    print(f"  {GRAY}🔧 {data['name']}({', '.join(f'{k}={v!r}' for k, v in list(data['args'].items())[:2])}){RESET}", flush=True)
                elif event_type == "tool_result":
                    snippet = data["snippet"][:80].replace("\n", " ")
                    print(f"  {GRAY}   ← {data['name']}: {snippet}...{RESET}", flush=True)
                elif event_type == "thinking":
                    preview = data[:120].replace("\n", " ")
                    print(f"  {GRAY}💭 {preview}{RESET}", flush=True)
                elif event_type == "result":
                    result = data

            if result:
                print_verdict(candidate["current_match_name"], result)
            else:
                print(f"\n{RED}No result for {candidate['current_match_name']}{RESET}")
        except Exception as e:
            print(f"\n{RED}Error researching {candidate['current_match_name']}: {e}{RESET}")

    print("\n" + "=" * 60)
    print(f"{BOLD}Research complete.{RESET}")


if __name__ == "__main__":
    main()
