import json
from src.common.db import get_all_ingredient_names, save_ingredient_groups
from src.common.bedrock import invoke_model_json

BATCH_SIZE = 50


def build_grouping_prompt(ingredient_names):
    names_str = "\n".join(f"- {name}" for name in ingredient_names)

    return f"""You are an expert in dietary supplement formulation and nutraceutical chemistry.

Given this list of raw material ingredient names from supplement bill-of-materials data, group them into functional equivalence classes.

RULES:
1. Group ingredients that serve the SAME FUNCTIONAL ROLE in a supplement formulation.
2. "Same chemical entity, different name" = high confidence (e.g., "vitamin-d3-cholecalciferol" and "cholecalciferol-vitamin-d3")
3. "Same functional role, different chemical form" = medium confidence (e.g., "magnesium-citrate" and "magnesium-glycinate" both serve as bioavailable magnesium sources)
4. Do NOT group ingredients that share a word but serve different functions (e.g., "magnesium-stearate" is a flow agent/lubricant, NOT a magnesium source — do not group it with magnesium-citrate)
5. Ingredients with no functional equivalents in this list should be in their own single-member group.

INGREDIENT LIST:
{names_str}

Return a JSON array of objects, each with:
- "canonical_name": human-readable group name (e.g., "Vitamin D3")
- "function": what this group does in a supplement (e.g., "vitamin D source", "flow agent", "protein source")
- "members": array of ingredient name strings from the list above that belong to this group
- "confidence": "high" if all members are the same chemical entity, "medium" if functionally equivalent but different forms, "low" if grouping is uncertain
- "reasoning": one sentence explaining why these are grouped

Every ingredient from the list must appear in exactly one group."""


def group_all_ingredients(db_path=None):
    all_names = get_all_ingredient_names(db_path)
    all_groups = []

    for i in range(0, len(all_names), BATCH_SIZE):
        batch = all_names[i : i + BATCH_SIZE]
        prompt = build_grouping_prompt(batch)
        system = "You are a nutraceutical chemistry expert. Return valid JSON only."
        groups = invoke_model_json(prompt, system=system)
        all_groups.extend(groups)

    save_ingredient_groups(db_path, all_groups)
    print(f"Saved {len(all_groups)} ingredient groups from {len(all_names)} ingredients")
    return all_groups


if __name__ == "__main__":
    group_all_ingredients()
