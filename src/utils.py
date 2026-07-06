"""Shared utility functions for parsing and modeling health exports."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Iterable

import pandas as pd


LOGGER_NAME = "wellness_etl"


def setup_logging(level: str = "INFO") -> logging.Logger:
    """Configure consistent console logging for the ETL."""

    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(levelname)s %(name)s - %(message)s",
    )
    return logging.getLogger(LOGGER_NAME)


def ensure_directories(paths: Iterable[Path]) -> None:
    for path in paths:
        path.mkdir(parents=True, exist_ok=True)


def normalize_column_name(value: object) -> str:
    """Normalize an export column into a stable snake_case identifier."""

    text = str(value).strip().lower()
    text = text.replace("%", " pct ")
    text = text.replace("&", " and ")
    text = text.replace("+", " plus ")
    text = text.replace("/", " ")
    text = text.replace("\\", " ")
    text = re.sub(r"[\(\)\[\]\{\}]", " ", text)
    text = re.sub(r"[^a-z0-9]+", "_", text)
    text = re.sub(r"_+", "_", text)
    return text.strip("_")


def strip_unit_text(value: str) -> str:
    """Remove common unit fragments before matching a semantic metric name."""

    text = str(value)
    text = re.sub(r"\([^)]*\)", " ", text)
    text = re.sub(r"\b(kcal|calories|cals|grams|gram|g|milligrams|milligram|mg|mcg|ug|iu)\b", " ", text, flags=re.I)
    text = re.sub(r"%\s*(dv|daily value)?", " ", text, flags=re.I)
    return normalize_column_name(text)


def detect_unit_suffix(value: str) -> str | None:
    """Return a conservative unit suffix found in a source column name."""

    text = str(value).lower()
    if "%dv" in text or "% daily value" in text or "pct daily value" in text or "percent daily value" in text:
        return "pct_dv"
    if re.search(r"\b(kcal|calories|cals)\b", text):
        return "kcal"
    if re.search(r"\b(mcg|ug|microgram|micrograms)\b", text):
        return "mcg"
    if re.search(r"\b(mg|milligram|milligrams)\b", text):
        return "mg"
    if re.search(r"\b(g|gram|grams)\b", text):
        return "g"
    if re.search(r"\biu\b", text):
        return "iu"
    return None


def clean_numeric_series(series: pd.Series) -> pd.Series:
    """Coerce messy export values like ``1,200 mg`` into numeric values."""

    if pd.api.types.is_numeric_dtype(series):
        return pd.to_numeric(series, errors="coerce")
    cleaned = (
        series.astype(str)
        .str.strip()
        .str.replace(",", "", regex=False)
        .str.replace(r"[^0-9.\-]+", "", regex=True)
    )
    cleaned = cleaned.mask(cleaned.isin(["", "-", ".", "nan", "None", "none"]))
    return pd.to_numeric(cleaned, errors="coerce")


def parse_date_series(series: pd.Series) -> pd.Series:
    """Parse dates from common CSV and Apple Health formats."""

    parsed = pd.to_datetime(series, errors="coerce", utc=False)
    return parsed.dt.date


def read_csv_flex(path: Path) -> pd.DataFrame:
    """Read a CSV export with a small amount of encoding tolerance."""

    try:
        return pd.read_csv(path, encoding="utf-8-sig")
    except UnicodeDecodeError:
        return pd.read_csv(path, encoding="latin1")


def empty_daily_frame(columns: list[str] | None = None) -> pd.DataFrame:
    columns = ["date"] + (columns or [])
    return pd.DataFrame(columns=columns)


def convert_weight_to_lb(value: float, unit: str | None) -> float:
    normalized = (unit or "lb").strip().lower()
    if normalized in {"kg", "kilogram", "kilograms"}:
        return value * 2.2046226218
    if normalized in {"stone", "st"}:
        return value * 14.0
    return value


def convert_energy_to_kcal(value: float, unit: str | None) -> float:
    normalized = (unit or "kcal").strip().lower()
    if normalized in {"kj", "kilojoule", "kilojoules"}:
        return value * 0.239005736
    return value


def coalesce_columns(df: pd.DataFrame, primary: str, fallback: str, output: str) -> pd.Series:
    left = df[primary] if primary in df else pd.Series(pd.NA, index=df.index)
    right = df[fallback] if fallback in df else pd.Series(pd.NA, index=df.index)
    return left.combine_first(right).rename(output)

