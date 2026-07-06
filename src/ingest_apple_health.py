"""Parse Apple Health XML exports into daily dashboard tables."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import xml.etree.ElementTree as ET

import pandas as pd

try:
    from .utils import convert_energy_to_kcal, convert_weight_to_lb, empty_daily_frame
except ImportError:  # pragma: no cover
    from utils import convert_energy_to_kcal, convert_weight_to_lb, empty_daily_frame


QUANTITY_TYPES = {
    "HKQuantityTypeIdentifierStepCount": ("steps", "sum"),
    "HKQuantityTypeIdentifierActiveEnergyBurned": ("active_energy_kcal", "sum"),
    "HKQuantityTypeIdentifierBasalEnergyBurned": ("basal_energy_kcal", "sum"),
    "HKQuantityTypeIdentifierBodyMass": ("weight_lb", "mean"),
    "HKQuantityTypeIdentifierRestingHeartRate": ("resting_hr", "mean"),
    "HKQuantityTypeIdentifierHeartRateVariabilitySDNN": ("hrv_ms", "mean"),
    "HKQuantityTypeIdentifierAppleExerciseTime": ("workout_minutes", "sum"),
}

SLEEP_ASLEEP_VALUES = {
    "HKCategoryValueSleepAnalysisAsleep",
    "HKCategoryValueSleepAnalysisAsleepCore",
    "HKCategoryValueSleepAnalysisAsleepDeep",
    "HKCategoryValueSleepAnalysisAsleepREM",
}


@dataclass
class AppleHealthData:
    daily_activity: pd.DataFrame
    daily_sleep: pd.DataFrame
    daily_body_metrics: pd.DataFrame
    records_read: int
    workouts_read: int


def load_apple_health_data(export_xml: Path) -> AppleHealthData:
    """Parse an Apple Health ``export.xml`` file if it exists."""

    if not Path(export_xml).exists():
        return AppleHealthData(
            daily_activity=empty_daily_frame(["steps", "active_energy_kcal", "basal_energy_kcal", "workout_minutes"]),
            daily_sleep=empty_daily_frame(["sleep_hours", "in_bed_hours"]),
            daily_body_metrics=empty_daily_frame(["weight_lb", "resting_hr", "hrv_ms"]),
            records_read=0,
            workouts_read=0,
        )

    quantity_rows: list[dict[str, Any]] = []
    sleep_rows: list[dict[str, Any]] = []
    workout_rows: list[dict[str, Any]] = []
    records_read = 0
    workouts_read = 0

    for _, element in ET.iterparse(export_xml, events=("end",)):
        if element.tag == "Record":
            records_read += 1
            record_type = element.attrib.get("type")
            if record_type in QUANTITY_TYPES:
                row = parse_quantity_record(element.attrib)
                if row:
                    quantity_rows.append(row)
            elif record_type == "HKCategoryTypeIdentifierSleepAnalysis":
                row = parse_sleep_record(element.attrib)
                if row:
                    sleep_rows.append(row)
            element.clear()
        elif element.tag == "Workout":
            workouts_read += 1
            row = parse_workout(element.attrib)
            if row:
                workout_rows.append(row)
            element.clear()

    activity = build_activity_frame(quantity_rows, workout_rows)
    sleep = build_sleep_frame(sleep_rows)
    body_metrics = build_body_metrics_frame(quantity_rows)
    return AppleHealthData(activity, sleep, body_metrics, records_read, workouts_read)


def parse_quantity_record(attrs: dict[str, str]) -> dict[str, Any] | None:
    metric, _ = QUANTITY_TYPES[attrs["type"]]
    date = apple_record_date(attrs)
    if date is None:
        return None

    value = numeric_value(attrs.get("value"))
    if value is None:
        return None

    unit = attrs.get("unit")
    if metric in {"active_energy_kcal", "basal_energy_kcal"}:
        value = convert_energy_to_kcal(value, unit)
    elif metric == "weight_lb":
        value = convert_weight_to_lb(value, unit)

    return {"date": date, "metric": metric, "value": value}


def parse_sleep_record(attrs: dict[str, str]) -> dict[str, Any] | None:
    start = parse_apple_datetime(attrs.get("startDate"))
    end = parse_apple_datetime(attrs.get("endDate"))
    if start is None or end is None or end <= start:
        return None

    hours = (end - start).total_seconds() / 3600
    value = attrs.get("value", "")
    metric = "sleep_hours" if value in SLEEP_ASLEEP_VALUES else "in_bed_hours"
    return {"date": start.date(), "metric": metric, "value": hours}


def parse_workout(attrs: dict[str, str]) -> dict[str, Any] | None:
    date = apple_record_date(attrs)
    if date is None:
        return None

    duration = numeric_value(attrs.get("duration"))
    if duration is None:
        start = parse_apple_datetime(attrs.get("startDate"))
        end = parse_apple_datetime(attrs.get("endDate"))
        if start is None or end is None or end <= start:
            return None
        duration = (end - start).total_seconds() / 60
    else:
        duration = convert_duration_to_minutes(duration, attrs.get("durationUnit"))

    return {"date": date, "metric": "workout_minutes", "value": duration}


def build_activity_frame(quantity_rows: list[dict[str, Any]], workout_rows: list[dict[str, Any]]) -> pd.DataFrame:
    rows = [row for row in quantity_rows if row["metric"] in {"steps", "active_energy_kcal", "basal_energy_kcal", "workout_minutes"}]
    rows.extend(workout_rows)
    if not rows:
        return empty_daily_frame(["steps", "active_energy_kcal", "basal_energy_kcal", "workout_minutes"])
    frame = pd.DataFrame(rows)
    daily = frame.pivot_table(index="date", columns="metric", values="value", aggfunc="sum").reset_index()
    for column in ["steps", "active_energy_kcal", "basal_energy_kcal", "workout_minutes"]:
        if column not in daily:
            daily[column] = pd.NA
    return daily[["date", "steps", "active_energy_kcal", "basal_energy_kcal", "workout_minutes"]].sort_values("date")


def build_sleep_frame(sleep_rows: list[dict[str, Any]]) -> pd.DataFrame:
    if not sleep_rows:
        return empty_daily_frame(["sleep_hours", "in_bed_hours"])
    frame = pd.DataFrame(sleep_rows)
    daily = frame.pivot_table(index="date", columns="metric", values="value", aggfunc="sum").reset_index()
    for column in ["sleep_hours", "in_bed_hours"]:
        if column not in daily:
            daily[column] = pd.NA
    daily["sleep_hours"] = daily["sleep_hours"].combine_first(daily["in_bed_hours"])
    return daily[["date", "sleep_hours", "in_bed_hours"]].sort_values("date")


def build_body_metrics_frame(quantity_rows: list[dict[str, Any]]) -> pd.DataFrame:
    rows = [row for row in quantity_rows if row["metric"] in {"weight_lb", "resting_hr", "hrv_ms"}]
    if not rows:
        return empty_daily_frame(["weight_lb", "resting_hr", "hrv_ms"])
    frame = pd.DataFrame(rows)
    daily = frame.pivot_table(index="date", columns="metric", values="value", aggfunc="mean").reset_index()
    for column in ["weight_lb", "resting_hr", "hrv_ms"]:
        if column not in daily:
            daily[column] = pd.NA
    return daily[["date", "weight_lb", "resting_hr", "hrv_ms"]].sort_values("date")


def apple_record_date(attrs: dict[str, str]) -> object | None:
    timestamp = parse_apple_datetime(attrs.get("startDate") or attrs.get("creationDate"))
    return timestamp.date() if timestamp is not None else None


def parse_apple_datetime(value: str | None) -> pd.Timestamp | None:
    if not value:
        return None
    timestamp = pd.to_datetime(value, errors="coerce")
    if pd.isna(timestamp):
        return None
    return timestamp


def numeric_value(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        return float(str(value).replace(",", ""))
    except ValueError:
        return None


def convert_duration_to_minutes(value: float, unit: str | None) -> float:
    normalized = (unit or "min").strip().lower()
    if normalized in {"hr", "hour", "hours"}:
        return value * 60
    if normalized in {"s", "sec", "second", "seconds"}:
        return value / 60
    return value

