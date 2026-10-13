"""Check data/products.csv for catalogue problems.

Run from the project root:

    python validate_products.py
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

from data import ALLOWED_CATEGORIES, COLUMNS, NUMERIC_COLUMNS

CORE_VERIFIED_FIELDS = (
    "name",
    "brand",
    "category",
    "serving_size_g",
    "calories_kcal_100g",
    "protein_g_100g",
    "sugar_g_100g",
    "label_source_url",
    "last_verified",
)

REQUIRED_ROW_FIELDS = (
    "product_id",
    "slug",
    "name",
    "brand",
    "category",
    "verification_status",
)

DEFAULT_CSV = Path(__file__).resolve().parent / "data" / "products.csv"


def _blank(value: object) -> bool:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return True
    text = str(value).strip()
    return text == "" or text.lower() in {"nan", "none"}


def _text(value: object) -> str:
    if _blank(value):
        return ""
    return str(value).strip()


def _row_label(row: pd.Series, index: int) -> str:
    product_id = _text(row["product_id"]) if "product_id" in row.index else ""
    if product_id:
        return product_id
    return f"row {index + 2}"


def _numeric_issue(value: object) -> str | None:
    if _blank(value):
        return None
    try:
        number = float(str(value).strip())
    except ValueError:
        return "is not a number"
    if pd.isna(number):
        return "is not a number"
    if number < 0:
        return "is negative"
    return None


def _date_issue(value: object) -> str | None:
    if _blank(value):
        return None
    text = str(value).strip()
    try:
        parsed = datetime.strptime(text, "%Y-%m-%d")
    except ValueError:
        return "is not YYYY-MM-DD"
    if parsed.strftime("%Y-%m-%d") != text:
        return "is not YYYY-MM-DD"
    return None


def collect_issues(frame: pd.DataFrame) -> list[str]:
    """Return human-readable problems. An empty list means the table passed."""
    issues: list[str] = []
    missing_columns = [column for column in COLUMNS if column not in frame.columns]
    for column in missing_columns:
        issues.append(f"Missing required field: {column}")
    if missing_columns:
        return issues

    cleaned = frame.copy()
    for column in COLUMNS:
        cleaned[column] = cleaned[column].map(_text)

    id_counts = cleaned.loc[cleaned["product_id"] != "", "product_id"].value_counts()
    for product_id, count in id_counts.items():
        if count > 1:
            issues.append(f"Duplicate product_id: {product_id} ({count} rows)")

    slug_counts = cleaned.loc[cleaned["slug"] != "", "slug"].value_counts()
    for slug, count in slug_counts.items():
        if count > 1:
            issues.append(f"Duplicate slug: {slug} ({count} rows)")

    for index, row in cleaned.iterrows():
        label = _row_label(row, int(index))
        for field in REQUIRED_ROW_FIELDS:
            if row[field] == "":
                issues.append(f"{label}: missing required field {field}")

        category = row["category"]
        if category and category not in ALLOWED_CATEGORIES:
            allowed = ", ".join(sorted(ALLOWED_CATEGORIES))
            issues.append(f"{label}: invalid category '{category}'. Allowed values: {allowed}")

        for field in NUMERIC_COLUMNS:
            problem = _numeric_issue(row[field])
            if problem:
                issues.append(f"{label}: invalid numeric value {field} {problem}")

        date_problem = _date_issue(row["last_verified"])
        if date_problem:
            issues.append(f"{label}: invalid date last_verified {date_problem}")

        if row["label_source_url"] == "":
            issues.append(f"{label}: missing source URL")

        if row["verification_status"] == "Verified":
            for field in CORE_VERIFIED_FIELDS:
                if row[field] == "":
                    issues.append(f"{label}: Verified product is missing {field}")

    return issues


def load_table(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, dtype=str, keep_default_na=False)


def validate_file(path: Path) -> list[str]:
    if not path.exists():
        return [f"Missing product file: {path}"]
    try:
        frame = load_table(path)
    except pd.errors.EmptyDataError:
        return [f"Missing required field: product file {path} is empty"]
    except pd.errors.ParserError as exc:
        return [f"Could not read {path}: {exc}"]
    return collect_issues(frame)


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    path = Path(args[0]) if args else DEFAULT_CSV
    issues = validate_file(path)
    product_count = 0
    if path.exists():
        try:
            product_count = len(load_table(path))
        except (pd.errors.EmptyDataError, pd.errors.ParserError):
            product_count = 0
    print(f"HealthLens product validation: {path}")
    print(f"Products: {product_count}")
    if not issues:
        print("No issues found.")
        return 0
    print(f"Issues: {len(issues)}")
    for issue in issues:
        print(f"- {issue}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
