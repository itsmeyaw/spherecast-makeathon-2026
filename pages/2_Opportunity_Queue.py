import streamlit as st

from src.common.db import get_finished_goods
from src.opportunity.store import ensure_workspace_ready, list_opportunities

st.set_page_config(page_title="Opportunity Queue", layout="wide")
ensure_workspace_ready()

st.title("Opportunity Queue")
st.caption("Procurement-style inbox for triage and review.")

finished_goods = get_finished_goods()
company_options = {"all": "All Companies"}
for product in finished_goods:
    company_options[str(product["company_id"])] = product["company_name"]

f1, f2, f3, f4 = st.columns(4)
status = f1.selectbox("Status", ["all", "new", "triaged", "needs-review", "approved", "rejected", "blocked"])
company_id = f2.selectbox("Company", options=list(company_options.keys()), format_func=lambda key: company_options[key])
match_type = f3.selectbox("Match Type", ["all", "exact", "alias", "hypothesis"])
blocker_state = f4.selectbox("Blocker State", ["all", "pass_known_blockers", "needs_review", "blocked"])
confidence = st.selectbox("Confidence", ["all", "high", "medium", "low"])

opportunities = list_opportunities(
    status=status,
    company_id=None if company_id == "all" else int(company_id),
    match_type=match_type,
    blocker_state=blocker_state,
    confidence_label=confidence,
)

rows = [
    {
        "OpportunityId": item["Id"],
        "Company": item["company_name"],
        "Finished Product": item["finished_sku"],
        "Ingredient": item["ParsedIngredientName"],
        "Opportunity Type": item["OpportunityType"],
        "Match": item["MatchType"],
        "Status": item["Status"],
        "Blocker": item["BlockerState"],
        "Evidence": item["EvidenceCompleteness"],
        "Candidates": item["CandidateCount"],
        "Products Affected": item["ProductsAffectedCount"],
        "Suppliers": item["SuppliersAffectedCount"],
        "Priority": round(item["PriorityScore"], 1),
    }
    for item in opportunities
]
st.dataframe(rows, use_container_width=True, hide_index=True)

if opportunities:
    selected_id = st.selectbox(
        "Open opportunity",
        options=[item["Id"] for item in opportunities],
        format_func=lambda opportunity_id: f"Opportunity #{opportunity_id}",
    )
    col_detail, col_review = st.columns(2)
    if col_detail.button("Open Detail"):
        st.session_state["selected_opportunity_id"] = selected_id
        st.switch_page("pages/3_Opportunity_Detail.py")
    if col_review.button("Open Review"):
        st.session_state["selected_opportunity_id"] = selected_id
        st.switch_page("pages/4_Review.py")
else:
    st.info("No opportunities matched the current filters.")
