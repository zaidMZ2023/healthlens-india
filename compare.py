"""Ranking and comparison verdicts, independent of Streamlit."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import pandas as pd

Goal = Literal["Lower sugar", "Higher protein"]

GOALS: tuple[Goal, ...] = ("Lower sugar", "Higher protein")

NUTRITION_COLUMNS = (
    "calories_kcal_100g",
    "protein_g_100g",
    "sugar_g_100g",
    "fibre_g_100g",
    "sodium_mg_100g",
)


@dataclass(frozen=True)
class ComparisonResult:
    winner_id: str | None
    is_tie: bool
    verdict: str
    goal: Goal
    sugar_delta_g: float | None
    protein_delta_g: float | None


def nutrition_per_serving(value_per_100g: float | None, serving_size_g: float | None) -> float | None:
    """Convert a per-100g nutrient value into a per-serving value."""
    if value_per_100g is None or serving_size_g is None:
        return None
    if pd.isna(value_per_100g) or pd.isna(serving_size_g):
        return None
    if float(serving_size_g) <= 0:
        return None
    return float(value_per_100g) * float(serving_size_g) / 100.0


def _numeric(value: object) -> float | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if pd.isna(number):
        return None
    return number


def _format_delta(value: float, unit: str) -> str:
    magnitude = abs(value)
    text = f"{magnitude:.1f}".rstrip("0").rstrip(".")
    return f"{text}{unit}"


def sort_products_for_goal(frame: pd.DataFrame, goal: Goal) -> pd.DataFrame:
    """Sort products for Explore: primary goal, then the specified tie-breaker."""
    if frame.empty:
        return frame.copy()
    ranked = frame.copy()
    if goal == "Lower sugar":
        ranked["_sugar"] = ranked["sugar_g_100g"]
        ranked["_protein"] = ranked["protein_g_100g"]
        ranked = ranked.sort_values(
            by=["_sugar", "_protein"],
            ascending=[True, False],
            na_position="last",
            kind="mergesort",
        )
    elif goal == "Higher protein":
        ranked["_protein"] = ranked["protein_g_100g"]
        ranked["_sugar"] = ranked["sugar_g_100g"]
        ranked = ranked.sort_values(
            by=["_protein", "_sugar"],
            ascending=[False, True],
            na_position="last",
            kind="mergesort",
        )
    else:
        raise ValueError(f"Unsupported goal: {goal}")
    return ranked.drop(columns=["_sugar", "_protein"], errors="ignore")


def compare_products(product_a: pd.Series, product_b: pd.Series, goal: Goal) -> ComparisonResult:
    """Deterministic two-product comparison. Never uses the word 'healthier'."""
    name_a = str(product_a.get("name", "Product A"))
    name_b = str(product_b.get("name", "Product B"))
    id_a = str(product_a.get("product_id", "A"))
    id_b = str(product_b.get("product_id", "B"))

    if id_a == id_b:
        return ComparisonResult(
            winner_id=None,
            is_tie=True,
            verdict="Select two different products to compare.",
            goal=goal,
            sugar_delta_g=None,
            protein_delta_g=None,
        )

    sugar_a = _numeric(product_a.get("sugar_g_100g"))
    sugar_b = _numeric(product_b.get("sugar_g_100g"))
    protein_a = _numeric(product_a.get("protein_g_100g"))
    protein_b = _numeric(product_b.get("protein_g_100g"))

    sugar_delta = None if sugar_a is None or sugar_b is None else sugar_a - sugar_b
    protein_delta = None if protein_a is None or protein_b is None else protein_a - protein_b

    if goal == "Lower sugar":
        if sugar_a is None or sugar_b is None:
            return ComparisonResult(
                winner_id=None,
                is_tie=True,
                verdict="Sugar per 100g is missing for one or both products, so a lower-sugar comparison is not available.",
                goal=goal,
                sugar_delta_g=sugar_delta,
                protein_delta_g=protein_delta,
            )
        if sugar_a != sugar_b:
            winner = product_a if sugar_a < sugar_b else product_b
            winner_name = str(winner.get("name"))
            delta = abs(sugar_a - sugar_b)
            return ComparisonResult(
                winner_id=str(winner.get("product_id")),
                is_tie=False,
                verdict=(
                    f"{winner_name} is the better fit for lower sugar because it has "
                    f"{_format_delta(delta, 'g')} less sugar per 100g."
                ),
                goal=goal,
                sugar_delta_g=sugar_delta,
                protein_delta_g=protein_delta,
            )
        if protein_a is None or protein_b is None:
            return ComparisonResult(
                winner_id=None,
                is_tie=True,
                verdict=(
                    f"{name_a} and {name_b} have the same sugar per 100g. "
                    "Protein is missing, so there is no tie-breaker."
                ),
                goal=goal,
                sugar_delta_g=sugar_delta,
                protein_delta_g=protein_delta,
            )
        if protein_a != protein_b:
            winner = product_a if protein_a > protein_b else product_b
            winner_name = str(winner.get("name"))
            delta = abs(protein_a - protein_b)
            return ComparisonResult(
                winner_id=str(winner.get("product_id")),
                is_tie=False,
                verdict=(
                    f"{winner_name} is the better fit for lower sugar because sugar is tied "
                    f"and it has {_format_delta(delta, 'g')} more protein per 100g."
                ),
                goal=goal,
                sugar_delta_g=sugar_delta,
                protein_delta_g=protein_delta,
            )
        return ComparisonResult(
            winner_id=None,
            is_tie=True,
            verdict=(
                f"{name_a} and {name_b} have the same sugar and protein per 100g, "
                "so this is a tie for lower sugar."
            ),
            goal=goal,
            sugar_delta_g=sugar_delta,
            protein_delta_g=protein_delta,
        )

    if goal == "Higher protein":
        if protein_a is None or protein_b is None:
            return ComparisonResult(
                winner_id=None,
                is_tie=True,
                verdict="Protein per 100g is missing for one or both products, so a higher-protein comparison is not available.",
                goal=goal,
                sugar_delta_g=sugar_delta,
                protein_delta_g=protein_delta,
            )
        if protein_a != protein_b:
            winner = product_a if protein_a > protein_b else product_b
            winner_name = str(winner.get("name"))
            delta = abs(protein_a - protein_b)
            return ComparisonResult(
                winner_id=str(winner.get("product_id")),
                is_tie=False,
                verdict=(
                    f"{winner_name} is the better fit for higher protein because it has "
                    f"{_format_delta(delta, 'g')} more protein per 100g."
                ),
                goal=goal,
                sugar_delta_g=sugar_delta,
                protein_delta_g=protein_delta,
            )
        if sugar_a is None or sugar_b is None:
            return ComparisonResult(
                winner_id=None,
                is_tie=True,
                verdict=(
                    f"{name_a} and {name_b} have the same protein per 100g. "
                    "Sugar is missing, so there is no tie-breaker."
                ),
                goal=goal,
                sugar_delta_g=sugar_delta,
                protein_delta_g=protein_delta,
            )
        if sugar_a != sugar_b:
            winner = product_a if sugar_a < sugar_b else product_b
            winner_name = str(winner.get("name"))
            delta = abs(sugar_a - sugar_b)
            return ComparisonResult(
                winner_id=str(winner.get("product_id")),
                is_tie=False,
                verdict=(
                    f"{winner_name} is the better fit for higher protein because protein is tied "
                    f"and it has {_format_delta(delta, 'g')} less sugar per 100g."
                ),
                goal=goal,
                sugar_delta_g=sugar_delta,
                protein_delta_g=protein_delta,
            )
        return ComparisonResult(
            winner_id=None,
            is_tie=True,
            verdict=(
                f"{name_a} and {name_b} have the same protein and sugar per 100g, "
                "so this is a tie for higher protein."
            ),
            goal=goal,
            sugar_delta_g=sugar_delta,
            protein_delta_g=protein_delta,
        )

    raise ValueError(f"Unsupported goal: {goal}")


QUERY_PAGE = "page"
QUERY_CATEGORY = "category"
QUERY_PRODUCT_A = "a"
QUERY_PRODUCT_B = "b"
QUERY_GOAL = "goal"

PAGE_EXPLORE = "Explore products"
PAGE_COMPARE = "Compare products"
PAGE_METHODOLOGY = "Methodology"

_PAGE_FROM_QUERY = {
    "explore": PAGE_EXPLORE,
    "compare": PAGE_COMPARE,
    "methodology": PAGE_METHODOLOGY,
}
_QUERY_FROM_PAGE = {label: key for key, label in _PAGE_FROM_QUERY.items()}


@dataclass(frozen=True)
class LoadedComparison:
    page: str
    category: str | None
    slug_a: str | None
    slug_b: str | None
    goal: Goal
    duplicate_selection: bool


def _query_value(params: dict[str, object], key: str) -> str:
    value = params.get(key, "")
    if isinstance(value, (list, tuple)):
        value = value[0] if value else ""
    return str(value).strip()


def slugs_in_category(products: pd.DataFrame, category: str | None) -> list[str]:
    """Product slugs available in one category, in catalogue order."""
    if products.empty or not category or "category" not in products.columns or "slug" not in products.columns:
        return []
    subset = products.loc[products["category"] == category]
    return [str(slug).strip() for slug in subset["slug"].tolist() if str(slug).strip()]


def dropdown_slugs(products: pd.DataFrame, category: str | None, exclude_slug: str | None = None) -> list[str]:
    """Slugs for a category dropdown, optionally excluding the other selected product."""
    slugs = slugs_in_category(products, category)
    if exclude_slug:
        slugs = [slug for slug in slugs if slug != exclude_slug]
    return slugs


def load_comparison_query(params: dict[str, object], products: pd.DataFrame) -> LoadedComparison:
    """Read a shareable comparison from query parameters.

    Product A and Product B must belong to the requested category. The same slug
    cannot be selected twice.
    """
    page = _PAGE_FROM_QUERY.get(_query_value(params, QUERY_PAGE).lower(), PAGE_EXPLORE)
    goal_text = _query_value(params, QUERY_GOAL)
    goal: Goal = "Higher protein" if goal_text == "Higher protein" else "Lower sugar"

    category_text = _query_value(params, QUERY_CATEGORY)
    known_categories: set[str] = set()
    if not products.empty and "category" in products.columns:
        known_categories = {str(value) for value in products["category"].dropna().tolist()}
    category = category_text if category_text in known_categories else None

    allowed = set(slugs_in_category(products, category))
    slug_a = _query_value(params, QUERY_PRODUCT_A)
    slug_b = _query_value(params, QUERY_PRODUCT_B)
    if slug_a not in allowed:
        slug_a = ""
    if slug_b not in allowed:
        slug_b = ""

    duplicate = bool(slug_a and slug_b and slug_a == slug_b)
    if duplicate:
        slug_b = ""

    return LoadedComparison(
        page=page,
        category=category,
        slug_a=slug_a or None,
        slug_b=slug_b or None,
        goal=goal,
        duplicate_selection=duplicate,
    )


def build_comparison_query(category: str, slug_a: str, slug_b: str, goal: Goal) -> dict[str, str]:
    """Query parameters that recreate one comparison."""
    return {
        QUERY_PAGE: _QUERY_FROM_PAGE[PAGE_COMPARE],
        QUERY_CATEGORY: category,
        QUERY_PRODUCT_A: slug_a,
        QUERY_PRODUCT_B: slug_b,
        QUERY_GOAL: goal,
    }


def comparison_url(base_url: str, category: str, slug_a: str, slug_b: str, goal: Goal) -> str:
    """Absolute or relative URL for a comparison."""
    from urllib.parse import urlencode, urlsplit, urlunsplit

    parts = urlsplit(base_url)
    query = urlencode(build_comparison_query(category, slug_a, slug_b, goal))
    base = urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))
    if not base:
        return f"?{query}"
    return f"{base}?{query}"
