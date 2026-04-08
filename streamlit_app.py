from __future__ import annotations

import streamlit as st

from src.phase2.catalog_loader import get_catalog_filters, load_catalog
from src.phase3.orchestrator import recommend
from src.phase4.schemas import RecommendationRequest


@st.cache_resource
def _load_catalog():
    return load_catalog()


def main() -> None:
    st.set_page_config(page_title="Zomato Recommender", page_icon="🍽️", layout="wide")
    st.title("Zomato Restaurant Recommender")
    st.caption("Streamlit deployment using existing backend recommendation pipeline")

    try:
        catalog = _load_catalog()
    except Exception as exc:  # noqa: BLE001
        st.error(f"Failed to load catalog: {exc}")
        st.stop()

    filters = get_catalog_filters(catalog)
    localities = filters.get("localities", [])
    cuisines = filters.get("cuisines", [])

    with st.form("recommend_form"):
        col1, col2, col3 = st.columns(3)
        with col1:
            locality = st.selectbox("Locality", options=localities, index=0 if localities else None)
            min_rating = st.selectbox("Minimum rating", options=[3.0, 3.5, 4.0, 4.5], index=2)
        with col2:
            cuisine = st.selectbox("Cuisine", options=cuisines, index=0 if cuisines else None)
            budget_min = st.number_input("Budget min (INR for two)", min_value=0, max_value=5000, value=0, step=50)
        with col3:
            budget_max = st.number_input(
                "Budget max (INR for two)", min_value=0, max_value=5000, value=1000, step=50
            )
            persona = st.selectbox("Persona", options=["premium", "budget"], index=0)

        online_order = st.checkbox("Online order available", value=False)
        book_table = st.checkbox("Table booking available", value=False)
        query = st.text_input("Specific cravings (optional)", placeholder="date night under 1000 near indiranagar")

        submitted = st.form_submit_button("Get recommendations")

    if not submitted:
        return

    if not locality or not cuisine:
        st.warning("Please select both locality and cuisine.")
        return

    prefs = RecommendationRequest(
        locality=locality,
        budget_min_inr=int(budget_min),
        budget_max_inr=int(budget_max),
        cuisine=cuisine,
        min_rating=float(min_rating),
        persona=persona,
        online_order=True if online_order else None,
        book_table=True if book_table else None,
        specific_cravings=query.strip() or None,
    )

    with st.spinner("Finding the best restaurants..."):
        response = recommend(prefs=prefs, catalog=catalog)

    st.subheader("Summary")
    st.write(response.summary)

    st.subheader("Recommendations")
    if not response.items:
        st.info("No restaurants matched your filters.")
    else:
        for item in response.items:
            st.markdown(
                f"**{item.rank}. {item.name}**  \n"
                f"Locality: `{item.locality}` | Rating: `{item.rating}` | Cost: `{item.cost_display}`  \n"
                f"Reason: {item.explanation}"
            )

    if response.rejected:
        with st.expander(f"{len(response.rejected)} shortlisted restaurants not recommended"):
            for rej in response.rejected:
                st.write(
                    f"- {rej.name} | rating={rej.rating} | cost={rej.cost_display} | reason={rej.rejection_reason}"
                )

    st.subheader("Meta")
    st.json(response.meta.model_dump())


if __name__ == "__main__":
    main()

