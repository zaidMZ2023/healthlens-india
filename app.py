"""HealthLens India — compare packaged foods from nutrition labels."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from compare import GOALS, Goal, compare_products, sort_products_for_goal
from data import filter_products, load_catalog, serving_values
from ui import (
    comparison_disclaimer,
    demo_banner,
    empty_state,
    format_grams,
    format_kcal,
    format_mg,
    inject_styles,
    render_source_line,
)

st.set_page_config(
    page_title="HealthLens India",
    page_icon="🔎",
    layout="wide",
    initial_sidebar_state="expanded",
)


def _product_label(row: pd.Series) -> str:
    variant = str(row.get("variant") or "").strip()
    if variant:
        return f"{row['name']} ({variant})"
    return str(row["name"])


def render_explore(products: pd.DataFrame, goal: Goal, category: str, brand_query: str, verified_only: bool) -> None:
    st.title("Compare packaged foods, clearly")
    st.markdown(
        '<p class="hl-subtitle">Compare sugar, protein, fibre and sodium from nutrition labels.</p>',
        unsafe_allow_html=True,
    )

    filtered = filter_products(
        products,
        category=category,
        brand_query=brand_query,
        verified_only=verified_only,
    )
    ranked = sort_products_for_goal(filtered, goal)

    total = len(products)
    shown = len(ranked)
    st.markdown(
        f"**{shown}** product{'s' if shown != 1 else ''} shown · **{total}** in the current catalog"
        + (f" · sorted for **{goal.lower()}**" if shown else "")
    )

    if ranked.empty:
        empty_state(
            "No products match these filters. Try another category, clear the brand search, "
            "or turn off “Show verified products only” while demo data is loaded."
        )
        return

    display = pd.DataFrame(
        {
            "Product name": ranked["name"],
            "Brand": ranked["brand"],
            "Category": ranked["category"],
            "Protein per 100g": ranked["protein_g_100g"].map(format_grams),
            "Sugar per 100g": ranked["sugar_g_100g"].map(format_grams),
            "Fibre per 100g": ranked["fibre_g_100g"].map(format_grams),
            "Sodium per 100g": ranked["sodium_mg_100g"].map(format_mg),
            "Last verified": ranked["last_verified"].fillna("—"),
        }
    )
    st.dataframe(
        display,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Product name": st.column_config.TextColumn(width="medium"),
            "Brand": st.column_config.TextColumn(width="medium"),
            "Last verified": st.column_config.TextColumn(width="small"),
        },
    )


def _metric_rows(product_a: pd.Series, product_b: pd.Series) -> pd.DataFrame:
    serving_a = serving_values(product_a)
    serving_b = serving_values(product_b)
    rows = [
        (
            "Calories",
            format_kcal(product_a.get("calories_kcal_100g")),
            format_kcal(serving_a["calories_kcal"]),
            format_kcal(product_b.get("calories_kcal_100g")),
            format_kcal(serving_b["calories_kcal"]),
        ),
        (
            "Protein",
            format_grams(product_a.get("protein_g_100g")),
            format_grams(serving_a["protein_g"]),
            format_grams(product_b.get("protein_g_100g")),
            format_grams(serving_b["protein_g"]),
        ),
        (
            "Sugar",
            format_grams(product_a.get("sugar_g_100g")),
            format_grams(serving_a["sugar_g"]),
            format_grams(product_b.get("sugar_g_100g")),
            format_grams(serving_b["sugar_g"]),
        ),
        (
            "Fibre",
            format_grams(product_a.get("fibre_g_100g")),
            format_grams(serving_a["fibre_g"]),
            format_grams(product_b.get("fibre_g_100g")),
            format_grams(serving_b["fibre_g"]),
        ),
        (
            "Sodium",
            format_mg(product_a.get("sodium_mg_100g")),
            format_mg(serving_a["sodium_mg"]),
            format_mg(product_b.get("sodium_mg_100g")),
            format_mg(serving_b["sodium_mg"]),
        ),
    ]
    serving_a_g = product_a.get("serving_size_g")
    serving_b_g = product_b.get("serving_size_g")
    return pd.DataFrame(
        rows,
        columns=[
            "Nutrient",
            f"{product_a['name']} / 100g",
            f"{product_a['name']} / serving ({format_grams(serving_a_g)})",
            f"{product_b['name']} / 100g",
            f"{product_b['name']} / serving ({format_grams(serving_b_g)})",
        ],
    )


def render_compare(products: pd.DataFrame, goal: Goal) -> None:
    st.title("Compare two products")
    st.caption("Choose one category, then two different products. Verdicts use label values per 100g.")

    categories = sorted(products["category"].dropna().unique().tolist()) if not products.empty else []
    if not categories:
        empty_state("There are no products to compare yet.")
        return

    category = st.selectbox("Category", categories, index=0)
    in_category = products.loc[products["category"] == category].reset_index(drop=True)
    if len(in_category) < 2:
        empty_state("This category needs at least two products before a comparison is possible.")
        return

    labels = [_product_label(row) for _, row in in_category.iterrows()]
    id_by_label = {label: str(row["product_id"]) for label, (_, row) in zip(labels, in_category.iterrows())}

    col_a, col_b = st.columns(2)
    with col_a:
        label_a = st.selectbox("Product A", labels, index=0)
    options_b = [label for label in labels if id_by_label[label] != id_by_label[label_a]]
    with col_b:
        label_b = st.selectbox("Product B", options_b, index=0)

    product_a = in_category.loc[in_category["product_id"] == id_by_label[label_a]].iloc[0]
    product_b = in_category.loc[in_category["product_id"] == id_by_label[label_b]].iloc[0]

    result = compare_products(product_a, product_b, goal)
    if result.is_tie:
        st.info(result.verdict)
    else:
        st.success(result.verdict)

    st.markdown(
        "Per-serving values are calculated as **(value per 100g × serving size in grams) ÷ 100**. "
        "They are not stored in the CSV."
    )
    st.dataframe(_metric_rows(product_a, product_b), use_container_width=True, hide_index=True)

    source_a, source_b = st.columns(2)
    with source_a:
        st.subheader(str(product_a["name"]))
        st.write(f"{product_a['brand']} · {product_a['variant']}")
        render_source_line(product_a)
    with source_b:
        st.subheader(str(product_b["name"]))
        st.write(f"{product_b['brand']} · {product_b['variant']}")
        render_source_line(product_b)

    st.divider()
    comparison_disclaimer()


def render_methodology() -> None:
    st.title("Methodology")
    st.markdown(
        """
Product data is added by hand from packaging or official product pages. This first release
does not scrape the web, call Open Food Facts, or invent nutrition figures for real brands.

Nutrition is compared **per 100g** so pack sizes do not hide differences. Per-serving figures
are calculated from the listed serving size: *(value per 100g × serving size in grams) ÷ 100*.

Labels can be incomplete, outdated, or reformulated. Always check the pack in your hand.

HealthLens India is educational. It does not diagnose conditions, recommend diets for children,
or provide medical advice. It never calls a product “healthy.”

Rankings follow the goal you choose (lower sugar or higher protein). The app does not accept
paid placements or change order for brands.
        """
    )


def main() -> None:
    inject_styles()
    catalog = load_catalog()

    with st.sidebar:
        st.header("HealthLens India")
        page = st.radio("Section", ("Explore products", "Compare products", "Methodology"), index=0)
        st.divider()
        goal: Goal = st.selectbox("Health-goal selector", list(GOALS), index=0)
        categories = ["All categories"]
        if not catalog.products.empty:
            categories.extend(sorted(catalog.products["category"].dropna().unique().tolist()))
        category = st.selectbox("Category filter", categories, index=0)
        brand_query = st.text_input("Brand text search", placeholder="Search brand")
        verified_only = st.checkbox("Show verified products only", value=False)

    demo_banner(catalog.using_demo_data)
    for message in catalog.errors:
        if catalog.using_demo_data and message == (
            "You are viewing fictional demo data. Add manually verified products to "
            "data/products.csv before publishing."
        ):
            continue
        st.error(message)

    if page == "Explore products":
        render_explore(catalog.products, goal, category, brand_query, verified_only)
    elif page == "Compare products":
        render_compare(catalog.products, goal)
    else:
        render_methodology()


main()
