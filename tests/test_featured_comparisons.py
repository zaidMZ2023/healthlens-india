import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data import COLUMNS, filter_products, validate_products
from featured import eligible_featured_comparisons, load_featured_entries


def _row(**overrides: str) -> dict[str, str]:
    base = {
        "product_id": "HL-1",
        "slug": "cereal-a",
        "name": "Cereal A",
        "brand": "Brand",
        "category": "Breakfast cereals and muesli",
        "variant": "Original",
        "pack_size_g": "500",
        "serving_size_g": "30",
        "calories_kcal_100g": "370",
        "protein_g_100g": "8",
        "sugar_g_100g": "18",
        "fibre_g_100g": "6",
        "sodium_mg_100g": "200",
        "label_source_url": "https://example.com/label",
        "last_verified": "2026-09-19",
        "verification_status": "Verified",
        "notes": "",
    }
    base.update(overrides)
    return base


def _products(*rows: dict[str, str]) -> pd.DataFrame:
    return pd.DataFrame(list(rows))


def test_breakfast_cereal_category_is_accepted() -> None:
    cleaned, errors = validate_products(pd.DataFrame([_row()]))
    assert errors == []
    assert cleaned["category"].tolist() == ["Breakfast cereals and muesli"]


def test_breakfast_cereal_category_passes_cli_rules() -> None:
    from validate_products import collect_issues

    assert collect_issues(pd.DataFrame([_row()])) == []


def test_filter_products_keeps_the_cereal_category() -> None:
    frame = _products(
        _row(),
        _row(product_id="HL-2", slug="chocolate", name="Chocolate", category="Chocolates"),
    )
    filtered = filter_products(frame, category="Breakfast cereals and muesli")
    assert filtered["slug"].tolist() == ["cereal-a"]


def test_featured_pair_is_visible_when_both_products_are_verified() -> None:
    products = _products(
        _row(slug="cereal-a", name="Cereal A"),
        _row(product_id="HL-2", slug="cereal-b", name="Cereal B", variant="Muesli"),
    )
    entries = [{"product_a": "cereal-a", "product_b": "cereal-b", "goal": "Lower sugar"}]
    visible = eligible_featured_comparisons(entries, products)
    assert len(visible) == 1
    assert visible[0].name_a == "Cereal A (Original)"
    assert visible[0].name_b == "Cereal B (Muesli)"
    assert visible[0].goal == "Lower sugar"
    assert visible[0].category == "Breakfast cereals and muesli"


def test_featured_pair_is_hidden_when_one_product_is_not_verified() -> None:
    products = _products(
        _row(slug="cereal-a"),
        _row(product_id="HL-2", slug="cereal-b", verification_status="Needs review"),
    )
    entries = [{"product_a": "cereal-a", "product_b": "cereal-b", "goal": "Higher protein"}]
    assert eligible_featured_comparisons(entries, products) == []


def test_featured_pair_is_hidden_when_a_product_is_missing() -> None:
    products = _products(_row(slug="cereal-a"))
    entries = [{"product_a": "cereal-a", "product_b": "missing", "goal": "Lower sugar"}]
    assert eligible_featured_comparisons(entries, products) == []


def test_featured_pair_is_hidden_across_categories() -> None:
    products = _products(
        _row(slug="cereal-a"),
        _row(product_id="HL-2", slug="chocolate", category="Chocolates"),
    )
    entries = [{"product_a": "cereal-a", "product_b": "chocolate", "goal": "Lower sugar"}]
    assert eligible_featured_comparisons(entries, products) == []


def test_featured_config_rejects_an_unknown_goal(tmp_path: Path) -> None:
    path = tmp_path / "featured.json"
    path.write_text(
        json.dumps({"comparisons": [{"product_a": "a", "product_b": "b", "goal": "Lower calories"}]}),
        encoding="utf-8",
    )
    entries, errors = load_featured_entries(path)
    assert entries == []
    assert errors


def test_cereal_template_has_the_catalogue_header_and_no_products() -> None:
    template = ROOT / "data" / "breakfast_cereals_template.csv"
    frame = pd.read_csv(template)
    assert list(frame.columns) == COLUMNS
    assert frame.empty


def test_shipped_featured_comparisons_use_verified_products() -> None:
    entries, errors = load_featured_entries(ROOT / "data" / "featured_comparisons.json")
    assert errors == []
    assert entries
    products = pd.read_csv(ROOT / "data" / "products.csv", dtype=str)
    visible = eligible_featured_comparisons(entries, products)
    assert len(visible) == len(entries)
    verified = set(products.loc[products["verification_status"] == "Verified", "slug"])
    for item in visible:
        assert item.slug_a in verified
        assert item.slug_b in verified
        assert item.slug_a != item.slug_b
        assert item.goal in {"Lower sugar", "Higher protein"}
