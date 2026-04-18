import streamlit as st

from src.opportunity.store import ensure_workspace_ready, get_workspace_metrics

st.set_page_config(page_title="Agnes Sourcing Workspace", layout="wide")
ensure_workspace_ready()

metrics = get_workspace_metrics()

st.title("Agnes Sourcing Workspace")
st.caption(
    "Evidence-backed sourcing copilot demo. Exact-match opportunities are high-confidence. "
    "Alias and hypothesis opportunities remain review-first."
)

col1, col2, col3 = st.columns(3)
col1.metric("Total Opportunities", metrics["total"])
col2.metric("High-Confidence Exact Matches", metrics["high_confidence_exact"])
col3.metric("Needs-Review Alias Opportunities", metrics["needs_review_alias"])

st.markdown(
    """
    This workspace now persists sourcing opportunities, candidate options, evidence, and review decisions in SQLite.
    Use the pages in the sidebar to triage the queue, inspect opportunity detail, and record review outcomes.
    """
)

if st.button("Rebuild Demo Workspace"):
    ensure_workspace_ready(force_rebuild=True)
    st.success("Workspace rebuilt from the current SQLite graph and the local demo evidence pack.")

st.page_link("pages/1_Overview.py", label="Open Overview", icon="📊")
st.page_link("pages/2_Opportunity_Queue.py", label="Open Opportunity Queue", icon="📥")
st.page_link("pages/3_Opportunity_Detail.py", label="Open Opportunity Detail", icon="🔎")
st.page_link("pages/4_Review.py", label="Open Review", icon="📝")
st.page_link("pages/6_Product_Research.py", label="Open Product Research", icon="🔬")
