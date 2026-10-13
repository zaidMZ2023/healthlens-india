"""HealthLens — compare packaged foods from nutrition labels."""

from __future__ import annotations

import json

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from compare import (
    GOALS,
    PAGE_COMPARE,
    PAGE_EXPLORE,
    PAGE_METHODOLOGY,
    Goal,
    LoadedComparison,
    build_comparison_query,
    compare_products,
    comparison_url,
    dropdown_slugs,
    load_comparison_query,
    sort_products_for_goal,
)
from data import data_coverage, filter_products, load_catalog, serving_values, verified_products
from ui import (
    comparison_disclaimer,
    empty_state,
    format_grams,
    format_kcal,
    format_mg,
    inject_styles,
    render_source_line,
)

st.set_page_config(
    page_title="HealthLens",
    page_icon="🔎",
    layout="wide",
    initial_sidebar_state="auto",
)

CATALOGUE_EMPTY = (
    "The catalogue is being verified. No verified products are available yet, "
    "so there is nothing to explore or compare."
)
FILTER_EMPTY = (
    "No verified products match these filters. Try another category or clear the brand search."
)
PAGES = (PAGE_EXPLORE, PAGE_COMPARE, PAGE_METHODOLOGY)


def _product_label(row: pd.Series) -> str:
    variant = str(row.get("variant") or "").strip()
    if variant and variant.lower() not in {"nan", "none"}:
        return f"{row['name']} ({variant})"
    return str(row["name"])


def _label_for_slug(products: pd.DataFrame, slug: str) -> str:
    matches = products.loc[products["slug"] == slug]
    if matches.empty:
        return slug
    return _product_label(matches.iloc[0])


def _row_for_slug(products: pd.DataFrame, slug: str) -> pd.Series:
    return products.loc[products["slug"] == slug].iloc[0]


def render_brand() -> None:
    st.markdown('<p class="hl-brand">HealthLens</p>', unsafe_allow_html=True)


def render_data_coverage(products: pd.DataFrame) -> None:
    coverage = data_coverage(products)
    st.subheader("Data coverage")
    verified, categories, recent = st.columns(3)
    verified.metric("Verified products", coverage["verified_products"])
    categories.metric("Categories with verified products", coverage["categories"])
    recent.metric("Most recent last verified", coverage["most_recent"])


def _app_base_url() -> str:
    try:
        return str(st.context.url).split("?", 1)[0]
    except Exception:
        return ""


def _sync_query(values: dict[str, str]) -> None:
    existing = {str(key): str(st.query_params.get(key, "")) for key in st.query_params}
    if existing == values:
        return
    st.query_params.clear()
    st.query_params.update(values)


def render_goal_selector() -> Goal:
    goal = st.selectbox("Health-goal selector", list(GOALS), key="hl_goal")
    return goal  # type: ignore[return-value]


def render_explore(products: pd.DataFrame) -> None:
    _sync_query({"page": "explore"})
    render_brand()
    st.title("Compare packaged foods, clearly")
    st.markdown(
        '<p class="hl-subtitle">Compare sugar, protein, fibre and sodium from nutrition labels. '
        "Only verified products are shown.</p>",
        unsafe_allow_html=True,
    )
    render_data_coverage(products)

    categories = ["All categories"]
    if not products.empty:
        categories.extend(sorted(products["category"].dropna().unique().tolist()))
    if st.session_state.get("hl_explore_category") not in categories:
        st.session_state.hl_explore_category = "All categories"

    filter_col, brand_col = st.columns(2)
    with filter_col:
        category = st.selectbox("Category filter", categories, key="hl_explore_category")
    with brand_col:
        brand_query = st.text_input("Brand text search", placeholder="Search brand", key="hl_brand_query")
    goal = render_goal_selector()

    if products.empty:
        empty_state(CATALOGUE_EMPTY)
        return

    filtered = filter_products(products, category=category, brand_query=brand_query)
    ranked = sort_products_for_goal(filtered, goal)

    total = len(products)
    shown = len(ranked)
    st.markdown(
        f"**{shown}** product{'s' if shown != 1 else ''} shown · **{total}** in the current catalog"
        + (f" · sorted for **{goal.lower()}**" if shown else "")
    )

    if ranked.empty:
        empty_state(FILTER_EMPTY)
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
        width="stretch",
        hide_index=True,
        column_config={
            "Product name": st.column_config.TextColumn(width="medium"),
            "Brand": st.column_config.TextColumn(width="medium"),
            "Last verified": st.column_config.TextColumn(width="small"),
        },
    )

    def _open_compare() -> None:
        chosen = st.session_state.get("hl_explore_category")
        if chosen and chosen != "All categories":
            st.session_state.hl_compare_category = chosen
        st.session_state.hl_page = PAGE_COMPARE

    st.button("Compare products", type="primary", key="hl_compare_cta", on_click=_open_compare)


def _nutrient_table(product: pd.Series) -> pd.DataFrame:
    serving = serving_values(product)
    rows = [
        ("Calories", format_kcal(product.get("calories_kcal_100g")), format_kcal(serving["calories_kcal"])),
        ("Protein", format_grams(product.get("protein_g_100g")), format_grams(serving["protein_g"])),
        ("Sugar", format_grams(product.get("sugar_g_100g")), format_grams(serving["sugar_g"])),
        ("Fibre", format_grams(product.get("fibre_g_100g")), format_grams(serving["fibre_g"])),
        ("Sodium", format_mg(product.get("sodium_mg_100g")), format_mg(serving["sodium_mg"])),
    ]
    return pd.DataFrame(rows, columns=["Nutrient", "Per 100g", "Per serving"])


def _render_product_card(product: pd.Series) -> None:
    with st.container(border=True):
        st.subheader(str(product["name"]))
        st.write(f"{product['brand']} · {product['variant']}")
        st.caption(f"Serving size: {format_grams(product.get('serving_size_g'))}")
        st.dataframe(_nutrient_table(product), width="stretch", hide_index=True)
        render_source_line(product)


def _render_copy_button(url: str) -> None:
    components.html(
        f"""
        <button id="hl-copy" style="font: 600 0.95rem sans-serif; padding: 0.55rem 0.9rem;
            border: 0; border-radius: 8px; background: #16324f; color: white; cursor: pointer;">
          Copy comparison link
        </button>
        <script>
        const url = {json.dumps(url)};
        const button = document.getElementById("hl-copy");
        button.addEventListener("click", async () => {{
          if (!navigator.clipboard || !navigator.clipboard.writeText) {{
            button.textContent = "Copy unavailable";
            return;
          }}
          try {{
            await navigator.clipboard.writeText(url);
            button.textContent = "Copied";
          }} catch (error) {{
            button.textContent = "Copy unavailable";
          }}
        }});
        </script>
        """,
        height=52,
    )
    st.caption("If copying is unavailable, select the link below and copy it manually.")
    st.session_state.hl_share_url = url
    st.text_input("Comparison link", key="hl_share_url", label_visibility="collapsed")


def _prepare_slug(key: str, allowed: list[str]) -> None:
    if not allowed:
        return
    if st.session_state.get(key) not in allowed:
        st.session_state[key] = allowed[0]


def render_compare(products: pd.DataFrame, loaded: LoadedComparison) -> None:
    render_brand()
    st.title("Compare two products")
    st.caption("Choose one category, then two different products. Verdicts use label values per 100g.")
    render_data_coverage(products)
    goal = render_goal_selector()

    if products.empty:
        empty_state(CATALOGUE_EMPTY)
        return

    categories = sorted(products["category"].dropna().unique().tolist())
    if not categories:
        empty_state(CATALOGUE_EMPTY)
        return

    if st.session_state.get("hl_compare_category") not in categories:
        st.session_state.hl_compare_category = loaded.category if loaded.category in categories else None

    category = st.selectbox(
        "Category",
        categories,
        index=None,
        placeholder="Choose a category",
        key="hl_compare_category",
    )
    if not category:
        _sync_query({"page": "compare", "goal": goal})
        empty_state("Choose one category before selecting products.")
        return

    in_category = products.loc[products["category"] == category].reset_index(drop=True)
    slugs = dropdown_slugs(in_category, category)
    if len(slugs) < 2:
        empty_state("This category needs at least two products before a comparison is possible.")
        return

    _prepare_slug("hl_slug_a", slugs)
    options_b = dropdown_slugs(in_category, category, exclude_slug=st.session_state.hl_slug_a)
    _prepare_slug("hl_slug_b", options_b)

    if loaded.duplicate_selection and st.session_state.get("hl_duplicate_notice"):
        st.warning("Choose two different products. The same product cannot be compared with itself.")
        st.session_state.hl_duplicate_notice = False

    product_col_a, product_col_b = st.columns(2)
    with product_col_a:
        st.selectbox(
            "Product A",
            slugs,
            key="hl_slug_a",
            format_func=lambda slug: _label_for_slug(in_category, slug),
        )
    options_b = dropdown_slugs(in_category, category, exclude_slug=st.session_state.hl_slug_a)
    _prepare_slug("hl_slug_b", options_b)
    with product_col_b:
        st.selectbox(
            "Product B",
            options_b,
            key="hl_slug_b",
            format_func=lambda slug: _label_for_slug(in_category, slug),
        )

    slug_a = str(st.session_state.hl_slug_a)
    slug_b = str(st.session_state.hl_slug_b)
    if slug_a == slug_b:
        empty_state("Choose two different products. The same product cannot be compared with itself.")
        return

    product_a = _row_for_slug(in_category, slug_a)
    product_b = _row_for_slug(in_category, slug_b)
    result = compare_products(product_a, product_b, goal)

    st.markdown(f"**Goal:** {goal}")
    if result.is_tie:
        st.info(result.verdict)
    else:
        st.success(result.verdict)

    st.markdown(
        "Values are shown **per 100g** and **per serving**. "
        "Per serving is **(value per 100g × serving size in grams) ÷ 100**. "
        "Those per-serving figures are not stored in the CSV."
    )
    card_a, card_b = st.columns(2)
    with card_a:
        _render_product_card(product_a)
    with card_b:
        _render_product_card(product_b)

    share = comparison_url(_app_base_url(), str(category), slug_a, slug_b, goal)
    _sync_query(build_comparison_query(str(category), slug_a, slug_b, goal))
    _render_copy_button(share)
    st.divider()
    comparison_disclaimer()


def render_methodology() -> None:
    _sync_query({"page": "methodology"})
    render_brand()
    st.title("Methodology")
    st.markdown(
        """
Product data is added by hand from packaging or official product pages. This first release
does not scrape the web, call Open Food Facts, or invent nutrition figures for real brands.
The public catalogue shows only products marked **Verified**. Rows marked Needs review or Demo
stay out of Explore and Compare.

Nutrition is compared **per 100g** so pack sizes do not hide differences. Per-serving figures
are calculated from the listed serving size: *(value per 100g × serving size in grams) ÷ 100*.

Labels can be incomplete, outdated, or reformulated. Always check the pack in your hand.

HealthLens is educational. It does not diagnose conditions, recommend diets for children,
or provide medical advice. It never calls a product “healthy.”

Rankings follow the goal you choose (lower sugar or higher protein). The app does not accept
paid placements or change order for brands.
        """
    )


def _init_state(loaded: LoadedComparison) -> None:
    if st.session_state.get("hl_ready"):
        return
    st.session_state.hl_ready = True
    st.session_state.hl_page = loaded.page if loaded.page in PAGES else PAGE_EXPLORE
    st.session_state.hl_goal = loaded.goal
    if loaded.category:
        st.session_state.hl_compare_category = loaded.category
    if loaded.slug_a:
        st.session_state.hl_slug_a = loaded.slug_a
    if loaded.slug_b:
        st.session_state.hl_slug_b = loaded.slug_b
    st.session_state.hl_duplicate_notice = loaded.duplicate_selection


def main() -> None:
    inject_styles()
    catalog = load_catalog()
    public = verified_products(catalog.products)
    loaded = load_comparison_query(dict(st.query_params), public)
    _init_state(loaded)

    with st.sidebar:
        st.header("HealthLens")
        st.radio("Section", PAGES, key="hl_page")

    for message in catalog.errors:
        st.error(message)

    page = st.session_state.hl_page
    if page == PAGE_EXPLORE:
        render_explore(public)
    elif page == PAGE_COMPARE:
        render_compare(public, loaded)
    else:
        render_methodology()


main()
