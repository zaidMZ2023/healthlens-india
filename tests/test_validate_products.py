import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data import data_coverage, verified_products
from validate_products import collect_issues, validate_file


def _row(**overrides: str) -> dict[str, str]:
    base = {
        "product_id": "HL-1",
        "slug": "product-one",
        "name": "Product One",
        "brand": "Brand",
        "category": "Chocolates",
        "variant": "Milk",
        "pack_size_g": "50",
        "serving_size_g": "20",
        "calories_kcal_100g": "500",
        "protein_g_100g": "6",
        "sugar_g_100g": "40",
        "fibre_g_100g": "",
        "sodium_mg_100g": "",
        "label_source_url": "https://example.com/label",
        "last_verified": "2026-09-19",
        "verification_status": "Verified",
        "notes": "",
    }
    base.update(overrides)
    return base


def _issues(**overrides: str) -> list[str]:
    return collect_issues(pd.DataFrame([_row(**overrides)]))


def test_valid_verified_row_has_no_issues() -> None:
    assert collect_issues(pd.DataFrame([_row()])) == []


def test_missing_required_field() -> None:
    issues = _issues(name="")
    assert any("missing required field name" in issue for issue in issues)


def test_missing_required_column() -> None:
    frame = pd.DataFrame([_row()]).drop(columns=["slug"])
    issues = collect_issues(frame)
    assert issues == ["Missing required field: slug"]


def test_duplicate_product_id_and_slug() -> None:
    rows = [
        _row(),
        _row(product_id="HL-1", slug="product-one", name="Other"),
    ]
    issues = collect_issues(pd.DataFrame(rows))
    assert any(issue.startswith("Duplicate product_id: HL-1") for issue in issues)
    assert any(issue.startswith("Duplicate slug: product-one") for issue in issues)


def test_invalid_category() -> None:
    issues = _issues(category="Snacks")
    assert any("invalid category 'Snacks'" in issue for issue in issues)


def test_invalid_numeric_value() -> None:
    issues = _issues(protein_g_100g="lots")
    assert any("invalid numeric value protein_g_100g" in issue for issue in issues)


def test_negative_numeric_value() -> None:
    issues = _issues(sugar_g_100g="-1")
    assert any("sugar_g_100g is negative" in issue for issue in issues)


def test_invalid_date() -> None:
    issues = _issues(last_verified="19-09-2026")
    assert any("invalid date last_verified" in issue for issue in issues)


def test_missing_source_url() -> None:
    issues = _issues(label_source_url="")
    assert any("missing source URL" in issue for issue in issues)


def test_verified_product_missing_core_nutrition() -> None:
    issues = _issues(sugar_g_100g="", calories_kcal_100g="")
    assert any("Verified product is missing sugar_g_100g" in issue for issue in issues)
    assert any("Verified product is missing calories_kcal_100g" in issue for issue in issues)


def test_needs_review_may_omit_core_nutrition() -> None:
    issues = collect_issues(
        pd.DataFrame(
            [
                _row(
                    verification_status="Needs review",
                    sugar_g_100g="",
                    calories_kcal_100g="",
                    protein_g_100g="",
                    serving_size_g="",
                )
            ]
        )
    )
    assert issues == []


def test_validate_file_reports_missing_path(tmp_path: Path) -> None:
    missing = tmp_path / "missing.csv"
    issues = validate_file(missing)
    assert issues == [f"Missing product file: {missing}"]


def test_production_catalog_passes_validation() -> None:
    issues = validate_file(ROOT / "data" / "products.csv")
    assert issues == []


def test_public_catalogue_keeps_only_verified_rows() -> None:
    frame = pd.DataFrame(
        [
            _row(product_id="V", slug="verified"),
            _row(product_id="R", slug="review", verification_status="Needs review"),
            _row(product_id="D", slug="demo", verification_status="Demo"),
        ]
    )
    public = verified_products(frame)
    assert public["product_id"].tolist() == ["V"]


def test_data_coverage_uses_verified_rows_only() -> None:
    frame = pd.DataFrame(
        [
            _row(product_id="V1", slug="v1", category="Chocolates", last_verified="2026-01-02"),
            _row(
                product_id="V2",
                slug="v2",
                category="Malted drink powders",
                last_verified="2026-09-19",
            ),
            _row(
                product_id="R",
                slug="review",
                verification_status="Needs review",
                category="Chocolates",
                last_verified="2026-12-01",
            ),
        ]
    )
    coverage = data_coverage(frame)
    assert coverage == {
        "verified_products": 2,
        "categories": 2,
        "most_recent": "2026-09-19",
    }


def test_data_coverage_when_nothing_is_verified() -> None:
    frame = pd.DataFrame([_row(verification_status="Demo")])
    coverage = data_coverage(frame)
    assert coverage == {
        "verified_products": 0,
        "categories": 0,
        "most_recent": "—",
    }
