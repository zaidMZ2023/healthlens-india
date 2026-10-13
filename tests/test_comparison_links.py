import sys
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from compare import (
    build_comparison_query,
    compare_products,
    comparison_url,
    dropdown_slugs,
    load_comparison_query,
)


def _products() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "product_id": "BV",
                "slug": "bournvita",
                "name": "Bournvita",
                "category": "Malted drink powders",
                "sugar_g_100g": 46.0,
                "protein_g_100g": 7.0,
            },
            {
                "product_id": "HK",
                "slug": "horlicks",
                "name": "Horlicks",
                "category": "Malted drink powders",
                "sugar_g_100g": 46.0,
                "protein_g_100g": 11.0,
            },
            {
                "product_id": "KK",
                "slug": "kitkat",
                "name": "KitKat",
                "category": "Chocolates",
                "sugar_g_100g": 35.1,
                "protein_g_100g": 6.4,
            },
            {
                "product_id": "DM",
                "slug": "dairy-milk",
                "name": "Dairy Milk",
                "category": "Chocolates",
                "sugar_g_100g": 57.0,
                "protein_g_100g": 7.8,
            },
        ]
    )


def _row(**overrides: object) -> pd.Series:
    base = {
        "product_id": "A",
        "name": "Product A",
        "sugar_g_100g": 20.0,
        "protein_g_100g": 8.0,
    }
    base.update(overrides)
    return pd.Series(base)


def test_query_parameter_loading_restores_comparison() -> None:
    params = {
        "page": "compare",
        "category": "Malted drink powders",
        "a": "bournvita",
        "b": "horlicks",
        "goal": "Higher protein",
    }
    loaded = load_comparison_query(params, _products())
    assert loaded.page == "Compare products"
    assert loaded.category == "Malted drink powders"
    assert loaded.slug_a == "bournvita"
    assert loaded.slug_b == "horlicks"
    assert loaded.goal == "Higher protein"
    assert loaded.duplicate_selection is False


def test_query_parameter_loading_ignores_slug_from_another_category() -> None:
    params = {
        "page": "compare",
        "category": "Chocolates",
        "a": "kitkat",
        "b": "horlicks",
        "goal": "Lower sugar",
    }
    loaded = load_comparison_query(params, _products())
    assert loaded.slug_a == "kitkat"
    assert loaded.slug_b is None


def test_comparison_url_round_trip() -> None:
    url = comparison_url(
        "https://healthlens.example/",
        "Chocolates",
        "kitkat",
        "dairy-milk",
        "Lower sugar",
    )
    assert url.startswith("https://healthlens.example/?")
    parsed = parse_qs(urlsplit(url).query)
    query = {key: values[0] for key, values in parsed.items()}
    loaded = load_comparison_query(query, _products())
    assert loaded.category == "Chocolates"
    assert loaded.slug_a == "kitkat"
    assert loaded.slug_b == "dairy-milk"
    assert loaded.goal == "Lower sugar"
    assert build_comparison_query("Chocolates", "kitkat", "dairy-milk", "Lower sugar")["page"] == "compare"


def test_duplicate_product_selection_is_rejected() -> None:
    loaded = load_comparison_query(
        {
            "page": "compare",
            "category": "Chocolates",
            "a": "kitkat",
            "b": "kitkat",
            "goal": "Lower sugar",
        },
        _products(),
    )
    assert loaded.duplicate_selection is True
    assert loaded.slug_a == "kitkat"
    assert loaded.slug_b is None
    options = dropdown_slugs(_products(), "Chocolates", exclude_slug="kitkat")
    assert "kitkat" not in options
    assert options == ["dairy-milk"]


def test_dropdowns_are_restricted_to_the_selected_category() -> None:
    chocolates = dropdown_slugs(_products(), "Chocolates")
    malted = dropdown_slugs(_products(), "Malted drink powders")
    assert chocolates == ["kitkat", "dairy-milk"]
    assert malted == ["bournvita", "horlicks"]
    assert set(chocolates).isdisjoint(malted)


def test_lower_sugar_verdict_uses_less_sugar() -> None:
    lower = _row(product_id="LOW", name="Product A", sugar_g_100g=20.0, protein_g_100g=8.0)
    higher = _row(product_id="HIGH", name="Product B", sugar_g_100g=24.2, protein_g_100g=12.0)
    result = compare_products(lower, higher, "Lower sugar")
    assert result.winner_id == "LOW"
    assert "less sugar per 100g" in result.verdict
    assert "healthier" not in result.verdict.lower()
    assert "healthy" not in result.verdict.lower()


def test_higher_protein_verdict_uses_more_protein() -> None:
    lower = _row(product_id="LOW", name="Product A", sugar_g_100g=10.0, protein_g_100g=8.0)
    higher = _row(product_id="HIGH", name="Product B", sugar_g_100g=12.0, protein_g_100g=14.5)
    result = compare_products(lower, higher, "Higher protein")
    assert result.winner_id == "HIGH"
    assert "more protein per 100g" in result.verdict
    assert "healthier" not in result.verdict.lower()
    assert "healthy" not in result.verdict.lower()
