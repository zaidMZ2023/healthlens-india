"""Load, validate, and filter the local product CSV catalog."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import streamlit as st

from compare import nutrition_per_serving

DATA_DIR = Path(__file__).resolve().parent / "data"
PRODUCTION_CSV = DATA_DIR / "products.csv"
SAMPLE_CSV = DATA_DIR / "sample_products.csv"

COLUMNS = [
    "product_id",
    "slug",
    "name",
    "brand",
    "category",
    "variant",
    "pack_size_g",
    "serving_size_g",
    "calories_kcal_100g",
    "protein_g_100g",
    "sugar_g_100g",
    "fibre_g_100g",
    "sodium_mg_100g",
    "label_source_url",
    "last_verified",
    "verification_status",
    "notes",
]

NUMERIC_COLUMNS = [
    "pack_size_g",
    "serving_size_g",
    "calories_kcal_100g",
    "protein_g_100g",
    "sugar_g_100g",
    "fibre_g_100g",
    "sodium_mg_100g",
]

ALLOWED_CATEGORIES = {"Malted drink powders", "Chocolates"}
ALLOWED_VERIFICATION = {"Verified", "Needs review", "Demo"}

DEMO_BANNER = (
    "You are viewing fictional demo data. Add manually verified products to "
    "data/products.csv before publishing."
)


@dataclass(frozen=True)
class Catalog:
    products: pd.DataFrame
    using_demo_data: bool
    errors: tuple[str, ...]
    source_path: str


def empty_catalog(errors: tuple[str, ...] = ()) -> Catalog:
    return Catalog(
        products=pd.DataFrame(columns=COLUMNS),
        using_demo_data=False,
        errors=errors,
        source_path="",
    )


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=COLUMNS)
    frame = pd.read_csv(path, dtype=str, keep_default_na=True)
    if frame.empty and list(frame.columns) == COLUMNS:
        return pd.DataFrame(columns=COLUMNS)
    return frame


def _to_numeric(series: pd.Series) -> pd.Series:
    cleaned = series.astype(str).str.strip()
    cleaned = cleaned.replace({"": pd.NA, "nan": pd.NA, "None": pd.NA})
    return pd.to_numeric(cleaned, errors="coerce")


def validate_products(frame: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    errors: list[str] = []
    if frame.empty:
        return pd.DataFrame(columns=COLUMNS), errors

    missing = [column for column in COLUMNS if column not in frame.columns]
    if missing:
        errors.append(
            "The product file is missing required columns: " + ", ".join(missing) + "."
        )
        return pd.DataFrame(columns=COLUMNS), errors

    cleaned = frame[COLUMNS].copy()
    for column in COLUMNS:
        if cleaned[column].dtype == object:
            cleaned[column] = cleaned[column].astype(str).str.strip()
            cleaned[column] = cleaned[column].replace({"nan": "", "None": ""})

    for column in NUMERIC_COLUMNS:
        cleaned[column] = _to_numeric(cleaned[column])

    cleaned["last_verified"] = cleaned["last_verified"].replace({"": pd.NA})
    parsed_dates = pd.to_datetime(cleaned["last_verified"], errors="coerce")
    invalid_dates = cleaned["last_verified"].notna() & parsed_dates.isna()
    if invalid_dates.any():
        bad_ids = cleaned.loc[invalid_dates, "product_id"].tolist()
        errors.append(
            "Some last_verified dates are not ISO YYYY-MM-DD: " + ", ".join(str(x) for x in bad_ids) + "."
        )
        cleaned = cleaned.loc[~invalid_dates].copy()
    cleaned["last_verified"] = pd.to_datetime(cleaned["last_verified"], errors="coerce").dt.strftime("%Y-%m-%d")

    required_text = ["product_id", "slug", "name", "brand", "category"]
    missing_text = cleaned[required_text].eq("").any(axis=1) | cleaned[required_text].isna().any(axis=1)
    if missing_text.any():
        errors.append("Some rows are missing product_id, slug, name, brand, or category and were skipped.")
        cleaned = cleaned.loc[~missing_text].copy()

    bad_category = ~cleaned["category"].isin(ALLOWED_CATEGORIES)
    if bad_category.any():
        errors.append(
            "Some rows use an unsupported category. Allowed values: "
            + ", ".join(sorted(ALLOWED_CATEGORIES))
            + "."
        )
        cleaned = cleaned.loc[~bad_category].copy()

    cleaned["verification_status"] = cleaned["verification_status"].replace({"": "Needs review"})
    bad_status = ~cleaned["verification_status"].isin(ALLOWED_VERIFICATION)
    if bad_status.any():
        errors.append(
            "Some rows have an unknown verification_status. Use Verified, Needs review, or Demo."
        )
        cleaned = cleaned.loc[~bad_status].copy()

    duplicate_ids = cleaned["product_id"].duplicated(keep=False)
    if duplicate_ids.any():
        errors.append("Duplicate product_id values were found. Only the first of each id was kept.")
        cleaned = cleaned.drop_duplicates(subset=["product_id"], keep="first")

    duplicate_slugs = cleaned["slug"].duplicated(keep=False)
    if duplicate_slugs.any():
        errors.append("Duplicate slug values were found. Only the first of each slug was kept.")
        cleaned = cleaned.drop_duplicates(subset=["slug"], keep="first")

    cleaned = cleaned.reset_index(drop=True)
    return cleaned, errors


def filter_products(
    frame: pd.DataFrame,
    *,
    category: str | None = None,
    brand_query: str = "",
    verified_only: bool = False,
) -> pd.DataFrame:
    filtered = frame.copy()
    if category and category != "All categories":
        filtered = filtered.loc[filtered["category"] == category]
    if brand_query.strip():
        needle = brand_query.strip().lower()
        filtered = filtered.loc[filtered["brand"].fillna("").str.lower().str.contains(needle, regex=False)]
    if verified_only:
        filtered = filtered.loc[filtered["verification_status"] == "Verified"]
    return filtered.reset_index(drop=True)


def serving_values(row: pd.Series) -> dict[str, float | None]:
    serving = row.get("serving_size_g")
    return {
        "calories_kcal": nutrition_per_serving(row.get("calories_kcal_100g"), serving),
        "protein_g": nutrition_per_serving(row.get("protein_g_100g"), serving),
        "sugar_g": nutrition_per_serving(row.get("sugar_g_100g"), serving),
        "fibre_g": nutrition_per_serving(row.get("fibre_g_100g"), serving),
        "sodium_mg": nutrition_per_serving(row.get("sodium_mg_100g"), serving),
    }


@st.cache_data(show_spinner=False)
def load_catalog() -> Catalog:
    production = _read_csv(PRODUCTION_CSV)
    production, production_errors = validate_products(production)
    if not production.empty:
        return Catalog(
            products=production,
            using_demo_data=False,
            errors=tuple(production_errors),
            source_path=str(PRODUCTION_CSV),
        )

    sample = _read_csv(SAMPLE_CSV)
    sample, sample_errors = validate_products(sample)
    errors = list(production_errors)
    if production.empty:
        errors.append(DEMO_BANNER)
    errors.extend(sample_errors)
    if sample.empty:
        errors.append("No usable products were found in data/products.csv or data/sample_products.csv.")
        return empty_catalog(tuple(errors))
    return Catalog(
        products=sample,
        using_demo_data=True,
        errors=tuple(dict.fromkeys(errors)),
        source_path=str(SAMPLE_CSV),
    )
