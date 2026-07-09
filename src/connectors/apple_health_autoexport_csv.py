"""HealthAutoExport daily CSV connector."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from pathlib import Path
from typing import Iterable

import pandas as pd

try:
    from ..ingest_apple_health import AppleHealthData, empty_apple_health_data
    from ..utils import LOGGER_NAME, clean_numeric_series, normalize_column_name, parse_date_series
except ImportError:  # pragma: no cover - supports `python src/build_dataset.py`
    from ingest_apple_health import AppleHealthData, empty_apple_health_data
    from utils import LOGGER_NAME, clean_numeric_series, normalize_column_name, parse_date_series


LOGGER = logging.getLogger(LOGGER_NAME)

ACTIVITY_FIELDS = [
    "steps",
    "active_energy_kcal",
    "resting_energy_kcal",
    "apple_exercise_time_min",
    "apple_stand_time_min",
    "walking_running_distance_mi",
    "flights_climbed",
    "vo2_max",
]

SLEEP_FIELDS = [
    "sleep_core_hours",
    "sleep_deep_hours",
    "sleep_rem_hours",
    "sleep_awake_hours",
    "sleep_in_bed_hours",
]

RECOVERY_FIELDS = [
    "resting_hr",
    "hrv_ms",
    "respiratory_rate",
    "blood_oxygen_pct",
    "walking_heart_rate_avg",
    "heart_rate_avg",
    "heart_rate_min",
    "heart_rate_max",
    "wrist_temperature_f",
]

FIELD_ALIASES = {
    "date": ["date", "date_time", "datetime", "day", "calendar_date"],
    "steps": ["step_count_count", "step_count", "steps"],
    "active_energy_kcal": ["active_energy_kcal", "active_energy_burned_kcal"],
    "resting_energy_kcal": ["resting_energy_kcal", "basal_energy_kcal", "basal_energy_burned_kcal"],
    "apple_exercise_time_min": ["apple_exercise_time_min", "exercise_time_min", "apple_exercise_minutes"],
    "apple_stand_time_min": ["apple_stand_time_min", "stand_time_min", "apple_stand_minutes"],
    "walking_running_distance_mi": [
        "walking_running_distance_mi",
        "walking_plus_running_distance_mi",
        "walking_running_distance_miles",
    ],
    "flights_climbed": ["flights_climbed_count", "flights_climbed"],
    "vo2_max": ["vo2_max_ml_kg_min", "vo2_max"],
    "sleep_total_hours": ["sleep_analysis_total_hr", "sleep_analysis_total_hours"],
    "sleep_asleep_hours": ["sleep_analysis_asleep_hr", "sleep_analysis_asleep_hours"],
    "sleep_core_hours": ["sleep_analysis_core_hr", "sleep_analysis_core_hours"],
    "sleep_deep_hours": ["sleep_analysis_deep_hr", "sleep_analysis_deep_hours"],
    "sleep_rem_hours": ["sleep_analysis_rem_hr", "sleep_analysis_rem_hours"],
    "sleep_awake_hours": ["sleep_analysis_awake_hr", "sleep_analysis_awake_hours"],
    "sleep_in_bed_hours": ["sleep_analysis_in_bed_hr", "sleep_analysis_in_bed_hours"],
    "resting_hr": ["resting_heart_rate_count_min", "resting_heart_rate_bpm", "resting_heart_rate"],
    "hrv_ms": ["heart_rate_variability_sdnn_ms", "hrv_sdnn_ms", "hrv_ms"],
    "respiratory_rate": ["respiratory_rate_count_min", "respiratory_rate"],
    "blood_oxygen_pct": ["blood_oxygen_pct", "blood_oxygen_percent", "oxygen_saturation_pct"],
    "walking_heart_rate_avg": ["walking_heart_rate_average_count_min", "walking_heart_rate_avg"],
    "heart_rate_avg": ["heart_rate_average_count_min", "heart_rate_avg_count_min", "heart_rate_avg"],
    "heart_rate_min": ["heart_rate_min_count_min", "heart_rate_minimum_count_min", "heart_rate_min"],
    "heart_rate_max": ["heart_rate_max_count_min", "heart_rate_maximum_count_min", "heart_rate_max"],
    "wrist_temperature_f": ["wrist_temperature_f", "wrist_temperature_degf"],
}

FIELD_TOKEN_GROUPS = {
    "steps": [("step", "count")],
    "active_energy_kcal": [("active", "energy")],
    "resting_energy_kcal": [("resting", "energy"), ("basal", "energy")],
    "apple_exercise_time_min": [("exercise", "time"), ("exercise", "minute")],
    "apple_stand_time_min": [("stand", "time"), ("stand", "minute")],
    "walking_running_distance_mi": [("walking", "running", "distance"), ("walk", "run", "distance")],
    "flights_climbed": [("flights", "climbed")],
    "vo2_max": [("vo2", "max")],
    "sleep_total_hours": [("sleep", "analysis", "total"), ("sleep", "total")],
    "sleep_asleep_hours": [("sleep", "analysis", "asleep"), ("sleep", "asleep")],
    "sleep_core_hours": [("sleep", "analysis", "core"), ("sleep", "core")],
    "sleep_deep_hours": [("sleep", "analysis", "deep"), ("sleep", "deep")],
    "sleep_rem_hours": [("sleep", "analysis", "rem"), ("sleep", "rem")],
    "sleep_awake_hours": [("sleep", "analysis", "awake"), ("sleep", "awake")],
    "sleep_in_bed_hours": [("sleep", "analysis", "in_bed"), ("sleep", "in_bed")],
    "resting_hr": [("resting", "heart", "rate")],
    "hrv_ms": [("heart", "rate", "variability"), ("hrv",)],
    "respiratory_rate": [("respiratory", "rate")],
    "blood_oxygen_pct": [("blood", "oxygen"), ("oxygen", "saturation")],
    "walking_heart_rate_avg": [("walking", "heart", "rate")],
    "heart_rate_avg": [("heart", "rate", "avg"), ("heart", "rate", "average")],
    "heart_rate_min": [("heart", "rate", "min"), ("heart", "rate", "minimum")],
    "heart_rate_max": [("heart", "rate", "max"), ("heart", "rate", "maximum")],
    "wrist_temperature_f": [("wrist", "temperature")],
}

FIELD_EXCLUDES = {
    "heart_rate_avg": ["walking", "resting", "variability"],
    "heart_rate_min": ["walking", "resting", "variability"],
    "heart_rate_max": ["walking", "resting", "variability"],
}


@dataclass(frozen=True)
class AppleHealthAutoExportCsvConnector:
    """Load the extracted HealthAutoExport daily CSV from a local file."""

    export_csv: Path
    use_autoexport_nutrition: bool = False

    name: str = "health_autoexport_daily_csv"
    source_type: str = "manual_export"

    def load(self) -> AppleHealthData:
        export_csv = resolve_autoexport_csv(self.export_csv)
        if export_csv is None:
            LOGGER.warning("HealthAutoExport CSV not found at %s; Apple Health tables will be empty.", self.export_csv)
            return empty_apple_health_data()

        frame = pd.read_csv(export_csv, encoding="utf-8-sig")
        if frame.empty:
            LOGGER.warning("HealthAutoExport CSV at %s is empty.", export_csv)
            return empty_apple_health_data()
        if self.use_autoexport_nutrition:
            LOGGER.warning(
                "USE_AUTOEXPORT_NUTRITION is enabled, but v1 keeps MyFitnessPal as the nutrition source of truth."
            )

        date_column = match_autoexport_column(frame.columns, "date")
        if date_column is None:
            LOGGER.warning("HealthAutoExport CSV has no date column; Apple Health tables will be empty.")
            return empty_apple_health_data()

        activity = build_autoexport_activity(frame, date_column)
        sleep = build_autoexport_sleep(frame, date_column)
        recovery = build_autoexport_recovery(frame, date_column)
        return AppleHealthData(
            daily_activity=activity,
            daily_sleep=sleep,
            daily_body_metrics=pd.DataFrame(columns=["date", "weight_lb"]),
            daily_recovery=recovery,
            records_read=len(frame),
            workouts_read=0,
        )


def resolve_autoexport_csv(configured_path: Path) -> Path | None:
    """Resolve the configured AutoExport CSV, including date-stamped exports."""

    if configured_path.exists():
        return configured_path
    if not configured_path.parent.exists():
        return None
    candidates = sorted(configured_path.parent.glob("HealthAutoExport*.csv"))
    return candidates[0] if candidates else None


def build_autoexport_activity(frame: pd.DataFrame, date_column: str) -> pd.DataFrame:
    output = dated_output_frame(frame, date_column)
    add_mapped_numeric_columns(frame, output, ACTIVITY_FIELDS, "daily_activity")
    if "apple_exercise_time_min" in output:
        output["workout_minutes"] = output["apple_exercise_time_min"]
    return output.dropna(subset=["date"])


def build_autoexport_sleep(frame: pd.DataFrame, date_column: str) -> pd.DataFrame:
    output = dated_output_frame(frame, date_column)
    add_mapped_numeric_columns(frame, output, SLEEP_FIELDS, "daily_sleep")

    total_column = match_autoexport_column(frame.columns, "sleep_total_hours")
    total_sleep = clean_numeric_series(frame[total_column]) if total_column else pd.Series(pd.NA, index=frame.index)
    stage_columns = [column for column in ["sleep_core_hours", "sleep_deep_hours", "sleep_rem_hours"] if column in output]
    stage_sleep = output[stage_columns].sum(axis=1, min_count=1) if stage_columns else pd.Series(pd.NA, index=frame.index)
    output["sleep_hours"] = total_sleep.combine_first(stage_sleep)
    return output.dropna(subset=["date"])


def build_autoexport_recovery(frame: pd.DataFrame, date_column: str) -> pd.DataFrame:
    output = dated_output_frame(frame, date_column)
    add_mapped_numeric_columns(frame, output, RECOVERY_FIELDS, "daily_recovery")
    return output.dropna(subset=["date"])


def dated_output_frame(frame: pd.DataFrame, date_column: str) -> pd.DataFrame:
    return pd.DataFrame({"date": parse_date_series(frame[date_column])})


def add_mapped_numeric_columns(
    source: pd.DataFrame,
    output: pd.DataFrame,
    fields: Iterable[str],
    table_name: str,
) -> None:
    missing = []
    for field in fields:
        source_column = match_autoexport_column(source.columns, field)
        if source_column is None:
            missing.append(field)
            continue
        output[field] = clean_numeric_series(source[source_column])
    if missing:
        LOGGER.info("HealthAutoExport CSV missing optional %s fields: %s", table_name, ", ".join(missing))


def match_autoexport_column(columns: Iterable[object], field: str) -> str | None:
    """Return the best source column for a normalized AutoExport field."""

    normalized_lookup = {normalize_autoexport_column(column): str(column) for column in columns}
    for alias in FIELD_ALIASES.get(field, []):
        if alias in normalized_lookup:
            return normalized_lookup[alias]

    excludes = FIELD_EXCLUDES.get(field, [])
    for tokens in FIELD_TOKEN_GROUPS.get(field, []):
        for normalized, original in normalized_lookup.items():
            if all(token in normalized for token in tokens) and not any(exclude in normalized for exclude in excludes):
                return original
    return None


def normalize_autoexport_column(column: object) -> str:
    return normalize_column_name(column).replace("minutes", "min").replace("bpm", "count_min")

