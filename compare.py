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
