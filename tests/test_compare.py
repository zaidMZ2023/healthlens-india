import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from compare import compare_products, nutrition_per_serving, sort_products_for_goal


def _row(**overrides: object) -> pd.Series:
    base = {
        "product_id": "A",
        "name": "Product A",
        "sugar_g_100g": 10.0,
        "protein_g_100g": 5.0,
        "serving_size_g": 30.0,
    }
    base.update(overrides)
    return pd.Series(base)


def test_lower_sugar_selects_lower_sugar_product() -> None:
    lower = _row(product_id="LOW", name="Product A", sugar_g_100g=20.0, protein_g_100g=8.0)
    higher = _row(product_id="HIGH", name="Product B", sugar_g_100g=24.2, protein_g_100g=12.0)
    result = compare_products(lower, higher, "Lower sugar")
    assert result.winner_id == "LOW"
    assert result.is_tie is False
    assert "healthier" not in result.verdict.lower()
    assert result.verdict == (
        "Product A is the better fit for lower sugar because it has 4.2g less sugar per 100g."
    )


def test_higher_protein_selects_higher_protein_product() -> None:
    lower = _row(product_id="LOW", name="Product A", sugar_g_100g=10.0, protein_g_100g=8.0)
    higher = _row(product_id="HIGH", name="Product B", sugar_g_100g=12.0, protein_g_100g=14.5)
    result = compare_products(lower, higher, "Higher protein")
    assert result.winner_id == "HIGH"
    assert result.verdict == (
        "Product B is the better fit for higher protein because it has 6.5g more protein per 100g."
    )


def test_sugar_tie_prefers_higher_protein() -> None:
    first = _row(product_id="A", name="Product A", sugar_g_100g=32.0, protein_g_100g=10.0)
    second = _row(product_id="B", name="Product B", sugar_g_100g=32.0, protein_g_100g=14.0)
    result = compare_products(first, second, "Lower sugar")
    assert result.winner_id == "B"
    assert "sugar is tied" in result.verdict
    assert "more protein" in result.verdict


def test_protein_tie_prefers_lower_sugar() -> None:
    first = _row(product_id="A", name="Product A", sugar_g_100g=40.0, protein_g_100g=12.0)
    second = _row(product_id="B", name="Product B", sugar_g_100g=28.0, protein_g_100g=12.0)
    result = compare_products(first, second, "Higher protein")
    assert result.winner_id == "B"
    assert "protein is tied" in result.verdict
    assert "less sugar" in result.verdict


def test_full_tie_is_neutral() -> None:
    first = _row(product_id="A", name="Product A", sugar_g_100g=20.0, protein_g_100g=10.0)
    second = _row(product_id="B", name="Product B", sugar_g_100g=20.0, protein_g_100g=10.0)
    sugar_tie = compare_products(first, second, "Lower sugar")
    protein_tie = compare_products(first, second, "Higher protein")
    assert sugar_tie.is_tie and sugar_tie.winner_id is None
    assert protein_tie.is_tie and protein_tie.winner_id is None
    assert "healthier" not in sugar_tie.verdict.lower()


def test_per_serving_calculation() -> None:
    assert nutrition_per_serving(20.0, 30.0) == 6.0
    assert nutrition_per_serving(42.0, 20.0) == 8.4
    assert nutrition_per_serving(None, 30.0) is None
    assert nutrition_per_serving(10.0, 0) is None


def test_sort_lower_sugar_uses_protein_tie_breaker() -> None:
    frame = pd.DataFrame(
        [
            {"product_id": "A", "sugar_g_100g": 32.0, "protein_g_100g": 10.0},
            {"product_id": "B", "sugar_g_100g": 32.0, "protein_g_100g": 14.0},
            {"product_id": "C", "sugar_g_100g": 20.0, "protein_g_100g": 8.0},
        ]
    )
    ranked = sort_products_for_goal(frame, "Lower sugar")
    assert ranked["product_id"].tolist() == ["C", "B", "A"]
