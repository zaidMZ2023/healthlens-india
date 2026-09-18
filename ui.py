"""Reusable Streamlit UI helpers."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from data import DEMO_BANNER


def inject_styles() -> None:
    st.markdown(
        """
        <style>
        .block-container { padding-top: 1.4rem; padding-bottom: 3rem; max-width: 1100px; }
        h1 { font-weight: 700; letter-spacing: -0.03em; }
        .hl-subtitle { color: #425466; font-size: 1.05rem; margin-top: -0.4rem; margin-bottom: 1.2rem; }
        .hl-card {
            border: 1px solid #e6eaf0;
            border-radius: 14px;
            padding: 1rem 1.1rem;
            background: #ffffff;
        }
        .hl-muted { color: #5b6b7c; font-size: 0.92rem; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def demo_banner(using_demo_data: bool) -> None:
    if using_demo_data:
        st.warning(DEMO_BANNER)


def comparison_disclaimer() -> None:
    st.info(
        "Comparisons use label values per 100g. Check the pack before buying, "
        "as formulations and serving sizes can change."
    )


def empty_state(message: str) -> None:
    st.info(message)


def format_grams(value: object) -> str:
    return _format_number(value, "g")


def format_mg(value: object) -> str:
    return _format_number(value, "mg")


def format_kcal(value: object) -> str:
    return _format_number(value, "kcal")


def _format_number(value: object, unit: str) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "—"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "—"
    if pd.isna(number):
        return "—"
    if abs(number - round(number)) < 1e-9:
        return f"{int(round(number))} {unit}"
    return f"{number:.1f} {unit}"


def source_markdown(row: pd.Series) -> str:
    url = str(row.get("label_source_url") or "").strip()
    verified = str(row.get("last_verified") or "").strip()
    status = str(row.get("verification_status") or "").strip()
    parts: list[str] = []
    if url and url.lower() not in {"nan", "none"}:
        parts.append(f"[Label source]({url})")
    else:
        parts.append("Label source not listed")
    if verified and verified.lower() not in {"nan", "none"}:
        parts.append(f"Last verified: {verified}")
    else:
        parts.append("Last verified: not listed")
    if status:
        parts.append(f"Status: {status}")
    return " · ".join(parts)


def render_source_line(row: pd.Series) -> None:
    st.markdown(source_markdown(row))
