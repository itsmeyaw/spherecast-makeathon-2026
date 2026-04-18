import streamlit as st

from src.opportunity.store import ensure_workspace_ready, get_opportunity_detail

st.set_page_config(page_title="Opportunity Detail", layout="wide")
ensure_workspace_ready()

selected_id = st.session_state.get("selected_opportunity_id")
st.title("Opportunity Detail")

if not selected_id:
    st.info("Select an opportunity from the queue first.")
    st.stop()

detail = get_opportunity_detail(opportunity_id=selected_id)
if not detail:
    st.error("Opportunity not found.")
    st.stop()

opportunity = detail["opportunity"]
candidates = detail["candidates"]
evidence = detail["evidence"]
requirements = detail["requirements"]

st.subheader(f"Opportunity #{opportunity['Id']} — {opportunity['ParsedIngredientName']}")
st.caption(
    f"{opportunity['company_name']} • {opportunity['finished_sku']} • "
    f"{opportunity['OpportunityType']} • {opportunity['MatchType']} • {opportunity['Status']}"
)

top1, top2, top3, top4 = st.columns(4)
top1.metric("Blocker State", opportunity["BlockerState"])
top2.metric("Evidence", opportunity["EvidenceCompleteness"])
top3.metric("Candidate Count", opportunity["CandidateCount"])
top4.metric("Priority", round(opportunity["PriorityScore"], 1))

st.markdown(f"**Summary:** {opportunity['Summary']}")
st.markdown(f"**Original Component SKU:** `{opportunity['component_sku']}`")
st.markdown(f"**Canonical Ingredient:** `{opportunity['CanonicalIngredientName']}`")

st.subheader("Requirement Profile")
if requirements:
    st.dataframe(
        [
            {
                "Type": row["RequirementType"],
                "Value": row["RequirementValue"],
                "Source": row["Source"],
                "Confidence": row["Confidence"],
            }
            for row in requirements
        ],
        use_container_width=True,
        hide_index=True,
    )
else:
    st.info("No requirement profile persisted for this opportunity.")

st.subheader("Candidate Options")
candidate_rows = [
    {
        "Candidate SKU": row["candidate_sku"],
        "Candidate Company": row["candidate_company_name"],
        "Supplier": row["candidate_supplier_name"] or "Unspecified",
        "Match Type": row["MatchType"],
        "Blocker": row["BlockerState"],
        "Evidence": row["EvidenceCompleteness"],
        "Summary": row["CandidateSummary"],
    }
    for row in candidates
]
st.dataframe(candidate_rows, use_container_width=True, hide_index=True)

st.subheader("Explanation")
for row in candidates[:10]:
    st.markdown(f"**{row['candidate_sku']}**")
    st.write(row["Explanation"] or row["CandidateSummary"])

st.subheader("Evidence")
st.dataframe(
    [
        {
            "Source Type": row["SourceType"],
            "Source": row["SourceLabel"],
            "Fact Type": row["FactType"],
            "Fact Value": row["FactValue"],
            "Score": row["QualityScore"],
            "Snippet": row["Snippet"],
        }
        for row in evidence
    ],
    use_container_width=True,
    hide_index=True,
)

if st.button("Open Review"):
    st.switch_page("pages/4_Review.py")
