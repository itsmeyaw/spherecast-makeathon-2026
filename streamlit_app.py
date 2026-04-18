import streamlit as st
from src.common.db import (
    get_connection,
    get_finished_goods,
    get_bom_components,
    get_suppliers_for_product,
    parse_ingredient_name,
)

st.set_page_config(page_title="Agnes — Raw Material Superpowers", layout="wide")
st.title("Agnes — Raw Material Superpowers")
st.caption("AI-powered ingredient substitution & compliance analysis for supplements")


def get_consolidation_opportunities():
    conn = get_connection()
    rows = conn.execute("""
        SELECT p.SKU, p.CompanyId, c.Name as company_name
        FROM Product p
        JOIN Company c ON p.CompanyId = c.Id
        WHERE p.Type = 'raw-material'
    """).fetchall()
    conn.close()

    ingredient_companies = {}
    for r in rows:
        name = parse_ingredient_name(r["SKU"])
        if name not in ingredient_companies:
            ingredient_companies[name] = set()
        ingredient_companies[name].add(r["company_name"])

    shared = {
        name: companies
        for name, companies in ingredient_companies.items()
        if len(companies) > 1
    }
    return dict(sorted(shared.items(), key=lambda x: -len(x[1])))


with st.sidebar:
    st.header("Consolidation Opportunities")
    st.caption("Ingredients used by multiple companies")
    opportunities = get_consolidation_opportunities()
    for ingredient, companies in list(opportunities.items())[:15]:
        st.markdown(f"**{ingredient}** — {len(companies)} companies")
        st.caption(", ".join(sorted(companies)[:5]) + ("..." if len(companies) > 5 else ""))

products = get_finished_goods()

product_options = {
    f"{p['company_name']} — {p['sku']}": p for p in products
}

selected_label = st.selectbox(
    "Select a finished good product",
    options=list(product_options.keys()),
)

if selected_label:
    product = product_options[selected_label]
    st.subheader(f"Bill of Materials — {product['company_name']}")

    components = get_bom_components(product_id=product["product_id"])

    bom_data = []
    for comp in components:
        ingredient = parse_ingredient_name(comp["sku"])
        suppliers = get_suppliers_for_product(product_id=comp["product_id"])
        bom_data.append({
            "Ingredient": ingredient,
            "SKU": comp["sku"],
            "Suppliers": ", ".join(suppliers) if suppliers else "None",
        })

    st.dataframe(bom_data, use_container_width=True)

    from src.substitute.find_candidates import find_candidates_for_product
    from src.compliance.evaluate import evaluate_all_candidates
    from src.recommend.rank import rank_evaluations

    st.divider()

    if st.button("Analyze Substitution Opportunities", type="primary"):
        with st.spinner("Finding substitution candidates..."):
            candidates = find_candidates_for_product(product_id=product["product_id"])

        if not any(c["candidates"] for c in candidates):
            st.info("No substitution candidates found for this product's ingredients.")
        else:
            with st.spinner("Evaluating compliance for each candidate..."):
                evaluations = evaluate_all_candidates(
                    candidates, product["sku"], product["company_name"]
                )

            ranked = rank_evaluations(evaluations)
            st.session_state["ranked_results"] = ranked

    if "ranked_results" in st.session_state:
        ranked = st.session_state["ranked_results"]

        st.subheader("Substitution Analysis")

        col_safe, col_risky, col_total = st.columns(3)
        total_safe = sum(r["safe_count"] for r in ranked)
        total_risky = sum(r["risky_count"] for r in ranked)
        total_candidates = sum(r["total_candidates"] for r in ranked)
        col_safe.metric("Safe Substitutions", total_safe)
        col_risky.metric("Risky Substitutions", total_risky)
        col_total.metric("Total Candidates Evaluated", total_candidates)

        for component in ranked:
            with st.expander(
                f"**{component['original_ingredient']}** "
                f"({component['group']['canonical_name']}) — "
                f"{component['safe_count']} safe, "
                f"{component['total_candidates']} total",
                expanded=component["safe_count"] > 0,
            ):
                st.caption(f"Function: {component['group']['function']}")
                st.caption(f"Current suppliers: {', '.join(component['current_suppliers'])}")

                if not component["ranked_substitutes"]:
                    st.info("No functional equivalents found.")
                    continue

                for sub in component["ranked_substitutes"]:
                    verdict = sub.get("verdict", "unknown")
                    color = {
                        "safe": "green",
                        "risky": "orange",
                        "incompatible": "red",
                        "insufficient-evidence": "gray",
                    }.get(verdict, "gray")

                    st.markdown(
                        f"**:{color}[{verdict.upper()}]** — "
                        f"**{sub.get('substitute', 'unknown')}** "
                        f"(confidence: {sub.get('confidence', 'unknown')})"
                    )

                    if sub.get("facts"):
                        st.markdown("**Facts:**")
                        for fact in sub["facts"]:
                            st.markdown(f"- {fact}")

                    if sub.get("rules"):
                        st.markdown("**FDA Rules:**")
                        for rule in sub["rules"]:
                            st.markdown(f"- {rule}")

                    if sub.get("inference"):
                        st.markdown(f"**Reasoning:** {sub['inference']}")

                    if sub.get("sources"):
                        st.markdown("**Sources:**")
                        for source in sub["sources"]:
                            st.markdown(f"- {source}")

                    if sub.get("caveats"):
                        st.warning("**Caveats:** " + "; ".join(sub["caveats"]))

                    st.divider()
