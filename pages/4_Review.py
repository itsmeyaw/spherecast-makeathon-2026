import streamlit as st

from src.opportunity.store import (
    ensure_workspace_ready,
    get_opportunity_detail,
    record_review_decision,
)

st.set_page_config(page_title="Review", layout="wide")
ensure_workspace_ready()

selected_id = st.session_state.get("selected_opportunity_id")
st.title("Review")

if not selected_id:
    st.info("Select an opportunity from the queue first.")
    st.stop()

detail = get_opportunity_detail(opportunity_id=selected_id)
if not detail:
    st.error("Opportunity not found.")
    st.stop()

opportunity = detail["opportunity"]

st.subheader(f"Opportunity #{opportunity['Id']} — {opportunity['ParsedIngredientName']}")
st.caption(
    f"Current status: {opportunity['Status']} • blocker state: {opportunity['BlockerState']} • evidence: {opportunity['EvidenceCompleteness']}"
)
st.markdown(f"**Why this may need review:** {opportunity['Summary']}")

status = st.selectbox(
    "Set status",
    ["new", "triaged", "needs-review", "approved", "rejected", "blocked"],
    index=["new", "triaged", "needs-review", "approved", "rejected", "blocked"].index(opportunity["Status"]),
)
reviewer = st.text_input("Reviewer", value="Analyst")
notes = st.text_area("Reviewer notes", placeholder="Record why you approved, rejected, or escalated this opportunity.")

if st.button("Save Review Decision"):
    record_review_decision(opportunity_id=selected_id, status=status, reviewer=reviewer, notes=notes)
    st.success("Review decision saved.")
    st.rerun()

st.subheader("Blocker Summary")
st.write(opportunity["Summary"])

st.subheader("Review History")
history_rows = [
    {
        "When": row["CreatedAt"],
        "Reviewer": row["Reviewer"],
        "Status": row["Status"],
        "Notes": row["Notes"],
    }
    for row in detail["review_history"]
]
if history_rows:
    st.dataframe(history_rows, use_container_width=True, hide_index=True)
else:
    st.info("No review decisions recorded yet.")
