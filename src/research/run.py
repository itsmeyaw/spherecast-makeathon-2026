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
    job_id = create_research_job(
        db_path=db_path,
        product_id=product["product_id"],
        component_product_id=component["product_id"],
    )
    update_research_job(db_path=db_path, job_id=job_id, status="running")

    try:
        candidates_data = find_candidates_for_component(
            db_path=db_path,
            component=component,
            finished_product=product,
        )

        all_candidates = candidates_data["exact_candidates"] + candidates_data["alias_candidates"]

        original_info = {
            "original_ingredient": candidates_data["original_ingredient"],
            "group": {
                "canonical_name": ", ".join(candidates_data["canonical_names"]),
                "function": "reviewed-alias-layer" if candidates_data["alias_candidates"] else "exact-match",
            },
            "requirements": [],
        }

        candidates_researched = []
        for candidate in all_candidates:
            sub_info = {
                "current_match_name": candidate["current_match_name"],
                "match_type": candidate["match_type"],
            }
            verdict = research_substitution(
                original=original_info,
                substitute=sub_info,
                product_sku=product["sku"],
                company_name=product["company_name"],
            )
            candidates_researched.append({
                "name": candidate["current_match_name"],
                "match_type": candidate["match_type"],
                "facts": verdict["facts"],
                "rules": verdict["rules"],
                "inference": verdict["inference"],
                "caveats": verdict["caveats"],
                "evidence_rows": verdict["evidence_rows"],
            })

        result_json = json.dumps({"candidates_researched": candidates_researched})
        update_research_job(db_path=db_path, job_id=job_id, status="completed", result_json=result_json)

    except Exception as e:
        logger.exception("Research failed for job %s", job_id)
        update_research_job(db_path=db_path, job_id=job_id, status="failed", error_message=str(e))
