"""Featured comparisons stored outside the app code."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from compare import GOALS, Goal

DATA_DIR = Path(__file__).resolve().parent / "data"
FEATURED_CONFIG = DATA_DIR / "featured_comparisons.json"


@dataclass(frozen=True)
class FeaturedComparison:
    slug_a: str
    slug_b: str
    name_a: str
    name_b: str
    category: str
    goal: Goal


def _display_name(row: pd.Series) -> str:
    name = str(row.get("name") or "").strip()
    variant = str(row.get("variant") or "").strip()
    if variant and variant.lower() not in {"nan", "none"}:
        return f"{name} ({variant})"
    return name


def load_featured_entries(path: Path | None = None) -> tuple[list[dict[str, str]], list[str]]:
    """Read featured comparison entries from the local JSON config."""
    config_path = FEATURED_CONFIG if path is None else path
    if not config_path.exists():
        return [], [f"Featured comparisons file was not found: {config_path}"]
    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return [], [f"Featured comparisons file is not valid JSON: {config_path}"]

    entries = payload.get("comparisons") if isinstance(payload, dict) else None
    if not isinstance(entries, list):
        return [], ["Featured comparisons file must contain a comparisons list."]

    cleaned: list[dict[str, str]] = []
    errors: list[str] = []
    for index, entry in enumerate(entries, start=1):
        if not isinstance(entry, dict):
            errors.append(f"Featured comparison {index} is not an object.")
            continue
        slug_a = str(entry.get("product_a", "")).strip()
        slug_b = str(entry.get("product_b", "")).strip()
        goal = str(entry.get("goal", "")).strip()
        if not slug_a or not slug_b or goal not in GOALS:
            errors.append(
                f"Featured comparison {index} needs product_a, product_b, and a goal of "
                + " or ".join(GOALS)
                + "."
            )
            continue
        cleaned.append({"product_a": slug_a, "product_b": slug_b, "goal": goal})
    return cleaned, errors


def eligible_featured_comparisons(
    entries: list[dict[str, str]],
    products: pd.DataFrame,
) -> list[FeaturedComparison]:
    """Keep a featured pair only when both products are Verified and in one category."""
    if products.empty or "slug" not in products.columns:
        return []

    by_slug: dict[str, pd.Series] = {}
    for _, row in products.iterrows():
        slug = str(row.get("slug") or "").strip()
        if slug:
            by_slug[slug] = row

    visible: list[FeaturedComparison] = []
    for entry in entries:
        row_a = by_slug.get(entry["product_a"])
        row_b = by_slug.get(entry["product_b"])
        if row_a is None or row_b is None:
            continue
        if entry["product_a"] == entry["product_b"]:
            continue
        if str(row_a.get("verification_status") or "").strip() != "Verified":
            continue
        if str(row_b.get("verification_status") or "").strip() != "Verified":
            continue
        category_a = str(row_a.get("category") or "").strip()
        category_b = str(row_b.get("category") or "").strip()
        if not category_a or category_a != category_b:
            continue
        goal: Goal = entry["goal"]  # type: ignore[assignment]
        visible.append(
            FeaturedComparison(
                slug_a=entry["product_a"],
                slug_b=entry["product_b"],
                name_a=_display_name(row_a),
                name_b=_display_name(row_b),
                category=category_a,
                goal=goal,
            )
        )
    return visible
