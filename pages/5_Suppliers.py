import streamlit as st

from src.common.db import get_suppliers_with_materials, get_canonical_alias_mapping

st.set_page_config(page_title="Suppliers & Materials", layout="wide")

st.title("Suppliers & Materials")
st.caption("Browse suppliers and the raw materials they provide. Search by material name or alias.")

suppliers = get_suppliers_with_materials()
alias_mapping = get_canonical_alias_mapping()

alias_by_canonical = {}
for alias_name, entries in alias_mapping.items():
    for entry in entries:
        canonical = entry["CanonicalName"]
        alias_by_canonical.setdefault(canonical, []).append(
            {"alias": entry["AliasName"], "match_type": entry["MatchType"], "approved": entry["Approved"]}
        )

def get_aliases_for_ingredient(ingredient_name):
    for entry_list in alias_mapping.get(ingredient_name, []):
        canonical = entry_list["CanonicalName"]
        aliases = alias_by_canonical.get(canonical, [])
        other = [a for a in aliases if a["alias"] != ingredient_name]
        if other:
            return canonical, other
    return None, []

all_material_names = sorted(
    {m["ingredient_name"] for s in suppliers for m in s["materials"]}
)

all_searchable = set()
for name in all_material_names:
    all_searchable.add(name)
    canonical, aliases = get_aliases_for_ingredient(name)
    for a in aliases:
        all_searchable.add(a["alias"])

def material_matches_search(ingredient_name, search_lower):
    if search_lower in ingredient_name.lower():
        return True
    canonical, aliases = get_aliases_for_ingredient(ingredient_name)
    return any(search_lower in a["alias"].lower() for a in aliases)

search_col, filter_col = st.columns([2, 3])
with search_col:
    search = st.text_input("Search by material name or alias", placeholder="e.g. magnesium, ascorbic-acid")
with filter_col:
    material_filter = st.multiselect("Filter by material", options=all_material_names)

if search or material_filter:
    search_lower = search.lower().strip()
    filtered = []
    for s in suppliers:
        matched_materials = [
            m
            for m in s["materials"]
            if (not search_lower or material_matches_search(m["ingredient_name"], search_lower))
            and (not material_filter or m["ingredient_name"] in material_filter)
        ]
        if matched_materials:
            filtered.append({**s, "materials": matched_materials})
    suppliers_to_show = filtered
else:
    suppliers_to_show = suppliers

st.metric("Suppliers shown", len(suppliers_to_show))

for supplier in suppliers_to_show:
    with st.expander(f"{supplier['supplier_name']} ({len(supplier['materials'])} materials)"):
        rows = []
        for m in supplier["materials"]:
            canonical, aliases = get_aliases_for_ingredient(m["ingredient_name"])
            alias_strs = []
            for a in aliases:
                label = a["alias"]
                if a["match_type"] == "hypothesis":
                    label += " (?)"
                alias_strs.append(label)
            rows.append(
                {
                    "Material": m["ingredient_name"],
                    "Canonical Group": canonical or "-",
                    "Aliases": ", ".join(alias_strs) if alias_strs else "-",
                    "SKU": m["sku"],
                }
            )
        st.dataframe(rows, use_container_width=True, hide_index=True)
