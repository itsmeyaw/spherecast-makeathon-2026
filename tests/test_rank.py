from src.recommend.rank import rank_evaluations

SAMPLE_EVALUATIONS = [
    {
        "original_ingredient": "magnesium-oxide",
        "group": {"canonical_name": "Magnesium Source", "function": "Mg source", "confidence": "medium"},
        "current_suppliers": ["SupA"],
        "evaluations": [
            {
                "original": "magnesium-oxide",
                "substitute": "magnesium-citrate",
                "verdict": "safe",
                "confidence": "medium",
                "facts": ["Product claims 400mg Mg"],
                "rules": ["FDA labeling rule"],
                "inference": "Compatible",
                "sources": ["source1"],
                "caveats": [],
            },
            {
                "original": "magnesium-oxide",
                "substitute": "magnesium-stearate",
                "verdict": "incompatible",
                "confidence": "high",
                "facts": ["Different function"],
                "rules": [],
                "inference": "Not a Mg source",
                "sources": [],
                "caveats": [],
            },
        ],
    },
    {
        "original_ingredient": "vitamin-c",
        "group": {"canonical_name": "Vitamin C", "function": "vitamin C", "confidence": "high"},
        "current_suppliers": ["SupB"],
        "evaluations": [],
    },
]


class TestRankEvaluations:
    def test_safe_ranked_first(self):
        ranked = rank_evaluations(SAMPLE_EVALUATIONS)
        mg = [r for r in ranked if r["original_ingredient"] == "magnesium-oxide"][0]
        assert mg["ranked_substitutes"][0]["verdict"] == "safe"

    def test_incompatible_ranked_last(self):
        ranked = rank_evaluations(SAMPLE_EVALUATIONS)
        mg = [r for r in ranked if r["original_ingredient"] == "magnesium-oxide"][0]
        assert mg["ranked_substitutes"][-1]["verdict"] == "incompatible"

    def test_no_candidates_still_included(self):
        ranked = rank_evaluations(SAMPLE_EVALUATIONS)
        vc = [r for r in ranked if r["original_ingredient"] == "vitamin-c"][0]
        assert len(vc["ranked_substitutes"]) == 0
        assert vc["has_alternatives"] is False

    def test_has_alternatives_flag(self):
        ranked = rank_evaluations(SAMPLE_EVALUATIONS)
        mg = [r for r in ranked if r["original_ingredient"] == "magnesium-oxide"][0]
        assert mg["has_alternatives"] is True
