import streamlit as st

from src.opportunity.store import ensure_workspace_ready, get_workspace_metrics, list_opportunities

st.set_page_config(page_title="Overview", layout="wide")
ensure_workspace_ready()
metrics = get_workspace_metrics()
opportunities = list_opportunities()

st.title("Overview")
st.caption("Portfolio-level view of structurally actionable sourcing opportunities.")

top1, top2, top3, top4 = st.columns(4)
top1.metric("Total Opportunities", metrics["total"])
top2.metric("Products Affected", metrics["products_affected"])
top3.metric("Supplier Options Surfaced", metrics["suppliers_affected"])
top4.metric("High-Confidence Exact", metrics["high_confidence_exact"])

left, right = st.columns(2)
with left:
    st.subheader("By Status")
    for status, count in metrics["by_status"].items():
        st.metric(status, count)

    st.subheader("By Match Type")
    for match_type, count in metrics["by_match_type"].items():
        st.metric(match_type, count)

with right:
    st.subheader("By Blocker State")
    for blocker_state, count in metrics["by_blocker_state"].items():
        st.metric(blocker_state, count)

    st.subheader("Priority Signals")
    actionable = [item for item in opportunities if item["BlockerState"] == "pass_known_blockers"]
    review = [item for item in opportunities if item["BlockerState"] == "needs_review"]
    blocked = [item for item in opportunities if item["BlockerState"] == "blocked"]
    st.metric("Pass Known Blockers", len(actionable))
    st.metric("Needs Review", len(review))
    st.metric("Blocked", len(blocked))

st.subheader("Top Opportunities")
top_rows = [
    {
        "OpportunityId": item["Id"],
        "Company": item["company_name"],
        "Finished Product": item["finished_sku"],
        "Ingredient": item["ParsedIngredientName"],
        "Type": item["OpportunityType"],
        "Match": item["MatchType"],
        "Status": item["Status"],
        "Blocker": item["BlockerState"],
        "Evidence": item["EvidenceCompleteness"],
        "Priority": round(item["PriorityScore"], 1),
    }
    for item in opportunities[:15]
]
st.dataframe(top_rows, use_container_width=True)
