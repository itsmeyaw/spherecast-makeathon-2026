DEMO_PRODUCT_FACTS = {
    "FG-iherb-10421": {
        "claims": ["softgel-format"],
        "certifications": [],
        "allergens": [],
        "notes": "Demo cache: no portfolio-level claim restrictions were loaded for this product.",
    },
    "FG-iherb-12222": {
        "claims": ["dairy-containing"],
        "certifications": [],
        "allergens": ["milk"],
        "notes": "Demo cache: protein product with explicit milk exposure for blocker demos.",
    },
}

DEMO_INGREDIENT_FACTS = {
    "vitamin-c": {
        "canonical_name": "vitamin-c",
        "display_name": "Vitamin C",
        "vegan_compatible": True,
        "allergens": [],
        "certifications": ["demo-identity-reviewed"],
        "evidence_strength": "high",
        "notes": "Curated demo fact pack marks vitamin-c as a vegan-compatible identity ingredient.",
    },
    "ascorbic-acid": {
        "canonical_name": "vitamin-c",
        "display_name": "Ascorbic Acid",
        "vegan_compatible": True,
        "allergens": [],
        "certifications": ["demo-identity-reviewed"],
        "evidence_strength": "high",
        "notes": "Curated demo fact pack marks ascorbic acid as the same chemical entity as vitamin-c.",
    },
    "vitamin-d3": {
        "canonical_name": "vitamin-d3",
        "vegan_compatible": False,
        "allergens": [],
        "certifications": [],
        "evidence_strength": "medium",
        "notes": "Curated demo fact pack treats vitamin-d3 as lanolin-adjacent and therefore not vegan-safe by default.",
    },
    "vitamin-d3-cholecalciferol": {
        "canonical_name": "vitamin-d3",
        "vegan_compatible": False,
        "allergens": [],
        "certifications": [],
        "evidence_strength": "medium",
        "notes": "Curated demo fact pack treats cholecalciferol as a vitamin-d3 identity alias.",
    },
    "cholecalciferol-vitamin-d3": {
        "canonical_name": "vitamin-d3",
        "vegan_compatible": False,
        "allergens": [],
        "certifications": [],
        "evidence_strength": "medium",
        "notes": "Curated demo fact pack treats cholecalciferol as a vitamin-d3 identity alias.",
    },
    "cellulose": {
        "canonical_name": "cellulose-excipient",
        "vegan_compatible": True,
        "allergens": [],
        "certifications": [],
        "evidence_strength": "medium",
        "notes": "Curated demo fact pack marks cellulose as a vegan-compatible excipient.",
    },
    "microcrystalline-cellulose": {
        "canonical_name": "cellulose-excipient",
        "vegan_compatible": True,
        "allergens": [],
        "certifications": [],
        "evidence_strength": "medium",
        "notes": "Curated demo fact pack marks microcrystalline cellulose as a reviewed excipient alias.",
    },
    "gelatin": {
        "canonical_name": "gelatin-capsule",
        "vegan_compatible": False,
        "allergens": [],
        "certifications": [],
        "evidence_strength": "medium",
        "notes": "Curated demo fact pack marks gelatin as non-vegan capsule material.",
    },
    "bovine-gelatin": {
        "canonical_name": "gelatin-capsule",
        "vegan_compatible": False,
        "allergens": [],
        "certifications": [],
        "evidence_strength": "medium",
        "notes": "Curated demo fact pack marks bovine gelatin as non-vegan capsule material.",
    },
    "softgel-capsule-bovine-gelatin": {
        "canonical_name": "gelatin-capsule",
        "vegan_compatible": False,
        "allergens": [],
        "certifications": [],
        "evidence_strength": "medium",
        "notes": "Curated demo fact pack marks bovine softgel capsule material as non-vegan.",
    },
    "whey-protein-isolate": {
        "canonical_name": "whey-protein-family",
        "vegan_compatible": False,
        "allergens": ["milk"],
        "certifications": [],
        "evidence_strength": "medium",
        "notes": "Curated demo fact pack marks whey protein isolate as milk-derived.",
    },
    "whey-protein-concentrate": {
        "canonical_name": "whey-protein-family",
        "vegan_compatible": False,
        "allergens": ["milk"],
        "certifications": [],
        "evidence_strength": "medium",
        "notes": "Curated demo fact pack marks whey protein concentrate as milk-derived.",
    },
    "magnesium-oxide": {
        "canonical_name": "magnesium-source",
        "vegan_compatible": True,
        "allergens": [],
        "certifications": [],
        "evidence_strength": "low",
        "notes": "Curated demo fact pack marks magnesium-oxide as a related magnesium source, not auto-approvable.",
    },
    "magnesium-citrate": {
        "canonical_name": "magnesium-source",
        "vegan_compatible": True,
        "allergens": [],
        "certifications": [],
        "evidence_strength": "low",
        "notes": "Curated demo fact pack marks magnesium-citrate as a related magnesium source, not auto-approvable.",
    },
    "magnesium-glycinate": {
        "canonical_name": "magnesium-source",
        "vegan_compatible": True,
        "allergens": [],
        "certifications": [],
        "evidence_strength": "low",
        "notes": "Curated demo fact pack marks magnesium-glycinate as a related magnesium source, not auto-approvable.",
    },
}


def get_cached_product_facts(product_sku):
    return DEMO_PRODUCT_FACTS.get(product_sku, {"claims": [], "certifications": [], "allergens": [], "notes": "No cached product facts available."})


def get_cached_ingredient_facts(ingredient_name):
    return DEMO_INGREDIENT_FACTS.get(ingredient_name)

