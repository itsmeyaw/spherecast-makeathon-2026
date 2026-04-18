import json
import logging

from src.common.db import (
    create_research_job,
    update_research_job,
)
from src.compliance.research_agent import research_substitution
from src.substitute.find_candidates import find_candidates_for_component

logger = logging.getLogger(__name__)


def run_research(db_path=None, product=None, component=None):
    ingredient = component.get("sku", "unknown")
    logger.info("Starting research for %s in product %s", ingredient, product.get("sku"))

    job_id = create_research_job(
        db_path=db_path,
        product_id=product["product_id"],
        component_product_id=component["product_id"],
    )
    logger.info("Created research job %d (pending)", job_id)
    update_research_job(db_path=db_path, job_id=job_id, status="running")

    try:
        candidates_data = find_candidates_for_component(
            db_path=db_path,
            component=component,
            finished_product=product,
        )

        all_candidates = candidates_data["exact_candidates"] + candidates_data["alias_candidates"]
        logger.info(
            "Job %d: found %d candidate(s) for %s (%d exact, %d alias)",
            job_id, len(all_candidates), ingredient,
            len(candidates_data["exact_candidates"]),
            len(candidates_data["alias_candidates"]),
        )

        if not all_candidates:
            logger.info("Job %d: no candidates to research, completing with empty result", job_id)

        original_info = {
            "original_ingredient": candidates_data["original_ingredient"],
            "group": {
                "canonical_name": ", ".join(candidates_data["canonical_names"]),
                "function": "reviewed-alias-layer" if candidates_data["alias_candidates"] else "exact-match",
            },
            "requirements": [],
        }

        candidates_researched = []
        for i, candidate in enumerate(all_candidates, 1):
            candidate_name = candidate["current_match_name"]
            logger.info(
                "Job %d: researching candidate %d/%d — %s (%s)",
                job_id, i, len(all_candidates), candidate_name, candidate["match_type"],
            )
            sub_info = {
                "current_match_name": candidate_name,
                "match_type": candidate["match_type"],
            }
            verdict = research_substitution(
                original=original_info,
                substitute=sub_info,
                product_sku=product["sku"],
                company_name=product["company_name"],
            )
            logger.info(
                "Job %d: candidate %s returned %d facts, %d rules",
                job_id, candidate_name, len(verdict["facts"]), len(verdict["rules"]),
            )
            candidates_researched.append({
                "name": candidate_name,
                "match_type": candidate["match_type"],
                "facts": verdict["facts"],
                "rules": verdict["rules"],
                "inference": verdict["inference"],
                "caveats": verdict["caveats"],
                "evidence_rows": verdict["evidence_rows"],
            })

        result_json = json.dumps({"candidates_researched": candidates_researched})
        update_research_job(db_path=db_path, job_id=job_id, status="completed", result_json=result_json)
        logger.info("Job %d: completed with %d candidate(s) researched", job_id, len(candidates_researched))

    except Exception as e:
        logger.exception("Research failed for job %s", job_id)
        update_research_job(db_path=db_path, job_id=job_id, status="failed", error_message=str(e))
