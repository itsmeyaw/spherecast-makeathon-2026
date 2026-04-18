import json
import threading

import streamlit as st

from src.common.db import (
    get_bom_components,
    get_finished_goods,
    get_latest_research_job,
    get_research_jobs_for_product,
    get_suppliers_for_product,
    parse_ingredient_name,
)
from src.research.run import run_research
from src.substitute.find_candidates import find_candidates_for_component

st.set_page_config(page_title="Product Research", layout="wide")
st.title("Product Research")
st.caption("Select a product to view its ingredients and trigger agentic substitution research.")

finished_goods = get_finished_goods()
if not finished_goods:
    st.info("No finished goods found. Run the workspace initialization first.")
    st.stop()

companies = sorted({p["company_name"] for p in finished_goods})
company_col, product_col, refresh_col = st.columns([2, 3, 1])

with company_col:
    selected_company = st.selectbox("Company", options=companies)

company_products = [p for p in finished_goods if p["company_name"] == selected_company]
with product_col:
    selected_product = st.selectbox(
        "Product",
        options=company_products,
        format_func=lambda p: p["sku"],
    )

with refresh_col:
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("Refresh"):
        st.rerun()

if not selected_product:
    st.stop()

components = get_bom_components(product_id=selected_product["product_id"])
if not components:
    st.info("No BOM components found for this product.")
    st.stop()

jobs = get_research_jobs_for_product(product_id=selected_product["product_id"])
jobs_by_component = {j["BomComponentProductId"]: j for j in jobs}

st.subheader("Ingredients")

for component in components:
    ingredient_name = parse_ingredient_name(component["sku"])
    suppliers = get_suppliers_for_product(product_id=component["product_id"])
    candidates_data = find_candidates_for_component(
        component=component,
        finished_product=selected_product,
    )
    exact_count = len(candidates_data["exact_candidates"])
    alias_count = len(candidates_data["alias_candidates"])

    job = jobs_by_component.get(component["product_id"])
    job_status = job["Status"] if job else None

    col_name, col_suppliers, col_exact, col_alias, col_status, col_actions = st.columns(
        [2, 2, 1, 1, 1, 2]
    )

    with col_name:
        st.markdown(f"**{ingredient_name}**")
        st.caption(component["sku"])
    with col_suppliers:
        st.write(", ".join(suppliers) if suppliers else "-")
    with col_exact:
        st.metric("Exact", exact_count)
    with col_alias:
        st.metric("Alias", alias_count)
    with col_status:
        if job_status == "completed":
            st.success("Done")
        elif job_status == "running":
            st.warning("Running")
        elif job_status == "pending":
            st.warning("Pending")
        elif job_status == "failed":
            st.error("Failed")
        else:
            st.caption("—")

    with col_actions:
        if job_status in ("pending", "running"):
            st.info("Research in progress...")
        elif job_status == "completed":
            view_key = f"view_{component['product_id']}"
            redo_key = f"redo_{component['product_id']}"
            view_col, redo_col = st.columns(2)
            with view_col:
                if st.button("View results", key=view_key):
                    st.session_state[f"show_results_{component['product_id']}"] = True
            with redo_col:
                if st.button("Redo research", key=redo_key):
                    thread = threading.Thread(
                        target=run_research,
                        kwargs={
                            "product": selected_product,
                            "component": component,
                        },
                        daemon=True,
                    )
                    thread.start()
                    st.rerun()
        elif job_status == "failed":
            st.error(job.get("ErrorMessage", "Unknown error")[:80])
            if st.button("Redo research", key=f"redo_failed_{component['product_id']}"):
                thread = threading.Thread(
                    target=run_research,
                    kwargs={
                        "product": selected_product,
                        "component": component,
                    },
                    daemon=True,
                )
                thread.start()
                st.rerun()
        else:
            if st.button("Find substitution", key=f"find_{component['product_id']}"):
                thread = threading.Thread(
                    target=run_research,
                    kwargs={
                        "product": selected_product,
                        "component": component,
                    },
                    daemon=True,
                )
                thread.start()
                st.rerun()

    show_key = f"show_results_{component['product_id']}"
    if st.session_state.get(show_key) and job_status == "completed" and job.get("ResultJson"):
        result = json.loads(job["ResultJson"])
        candidates = result.get("candidates_researched", [])
        if not candidates:
            st.info("No candidates were researched for this ingredient.")
        for candidate in candidates:
            with st.expander(f"{candidate['name']} ({candidate['match_type']})", expanded=True):
                st.markdown(f"**Inference:** {candidate.get('inference', '-')}")

                if candidate.get("facts"):
                    st.markdown("**Facts:**")
                    for fact in candidate["facts"]:
                        st.markdown(f"- {fact}")

                if candidate.get("rules"):
                    st.markdown("**Rules:**")
                    for rule in candidate["rules"]:
                        st.markdown(f"- {rule}")

                if candidate.get("caveats"):
                    st.markdown("**Caveats:**")
                    for caveat in candidate["caveats"]:
                        st.markdown(f"- {caveat}")

                evidence = candidate.get("evidence_rows", [])
                if evidence:
                    st.markdown("**Evidence:**")
                    st.dataframe(
                        [
                            {
                                "Source Type": e.get("source_type", ""),
                                "Source": e.get("source_label", ""),
                                "Fact Type": e.get("fact_type", ""),
                                "Fact Value": e.get("fact_value", ""),
                                "Quality": e.get("quality_score", ""),
                            }
                            for e in evidence
                        ],
                        use_container_width=True,
                        hide_index=True,
                    )

        st.caption(f"Completed: {job.get('UpdatedAt', '-')}")

    st.divider()
