"""Transform source-specific daily tables into dashboard-ready models."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

try:
    from .config import PipelineConfig
    from .ingest_mfp import CORE_NUTRITION_FIELDS
except ImportError:  # pragma: no cover
    from config import PipelineConfig
    from ingest_mfp import CORE_NUTRITION_FIELDS


FACT_BASE_COLUMNS = [
    "date",
    "calories",
    "protein_g",
    "carbs_g",
    "fat_g",
    "fiber_g",
    "sugar_g",
    "sodium_mg",
    "potassium_mg",
    "cholesterol_mg",
    "weight_lb",
    "steps",
    "active_energy_kcal",
    "resting_energy_kcal",
    "sleep_hours",
    "resting_hr",
    "hrv_ms",
    "workout_minutes",
]

FACT_PREFERRED_ORDER = [
    "date",
    "calories",
    "protein_g",
    "carbs_g",
    "fat_g",
    "saturated_fat_g",
    "trans_fat_g",
    "fiber_g",
    "sugar_g",
    "sodium_mg",
    "potassium_mg",
    "cholesterol_mg",
    "weight_lb",
    "steps",
    "active_energy_kcal",
    "resting_energy_kcal",
    "apple_exercise_time_min",
    "apple_stand_time_min",
    "walking_running_distance_mi",
    "flights_climbed",
    "vo2_max",
    "sleep_hours",
    "sleep_core_hours",
    "sleep_deep_hours",
    "sleep_rem_hours",
    "sleep_awake_hours",
    "sleep_in_bed_hours",
    "resting_hr",
    "hrv_ms",
    "respiratory_rate",
    "blood_oxygen_pct",
    "walking_heart_rate_avg",
    "heart_rate_avg",
    "heart_rate_min",
    "heart_rate_max",
    "wrist_temperature_f",
    "alcohol_consumption_count",
    "workout_minutes",
    "mfp_exercise_calories",
]


@dataclass
class DailyModels:
    daily_nutrition: pd.DataFrame
    daily_micronutrients: pd.DataFrame
    daily_activity: pd.DataFrame
    daily_sleep: pd.DataFrame
    daily_recovery: pd.DataFrame
    daily_body_metrics: pd.DataFrame
    dashboard_fact: pd.DataFrame
    missing_fields: list[str]


def build_daily_models(
    mfp_nutrition: pd.DataFrame,
    mfp_micronutrients: pd.DataFrame,
    mfp_activity: pd.DataFrame,
    mfp_body_metrics: pd.DataFrame,
    apple_activity: pd.DataFrame,
    apple_sleep: pd.DataFrame,
    apple_body_metrics: pd.DataFrame,
    config: PipelineConfig,
    apple_recovery: pd.DataFrame | None = None,
) -> DailyModels:
    daily_nutrition = normalize_daily_frame(mfp_nutrition)
    daily_micronutrients = normalize_daily_frame(mfp_micronutrients)
    daily_activity = combine_activity(apple_activity, mfp_activity)
    daily_sleep = normalize_daily_frame(apple_sleep)
    daily_recovery = normalize_daily_frame(apple_recovery)
    daily_body_metrics = combine_body_metrics(apple_body_metrics, mfp_body_metrics)

    dashboard_fact = build_dashboard_fact(
        daily_nutrition=daily_nutrition,
        daily_micronutrients=daily_micronutrients,
        daily_activity=daily_activity,
        daily_sleep=daily_sleep,
        daily_recovery=daily_recovery,
        daily_body_metrics=daily_body_metrics,
        config=config,
    )
    missing_fields = summarize_missing_fields(dashboard_fact, FACT_BASE_COLUMNS)
    return DailyModels(
        daily_nutrition=daily_nutrition,
        daily_micronutrients=daily_micronutrients,
        daily_activity=daily_activity,
        daily_sleep=daily_sleep,
        daily_recovery=daily_recovery,
        daily_body_metrics=daily_body_metrics,
        dashboard_fact=dashboard_fact,
        missing_fields=missing_fields,
    )


def combine_activity(apple_activity: pd.DataFrame, mfp_activity: pd.DataFrame) -> pd.DataFrame:
    apple = normalize_daily_frame(apple_activity)
    mfp = normalize_daily_frame(mfp_activity)
    combined = merge_on_date([apple, mfp], suffixes=("_apple", "_mfp"))
    if combined.empty:
        return pd.DataFrame(columns=["date", "steps", "active_energy_kcal", "resting_energy_kcal", "workout_minutes"])

    output = pd.DataFrame({"date": combined["date"]})
    for column in [
        "steps",
        "active_energy_kcal",
        "resting_energy_kcal",
        "apple_stand_time_min",
        "walking_running_distance_mi",
        "flights_climbed",
        "vo2_max",
        "mfp_exercise_calories",
    ]:
        output[column] = combined[column] if column in combined else pd.NA

    apple_workout = combined["apple_exercise_time_min"] if "apple_exercise_time_min" in combined else None
    if apple_workout is None:
        apple_workout = combined["workout_minutes_apple"] if "workout_minutes_apple" in combined else combined.get("workout_minutes")
    mfp_workout = combined["workout_minutes_mfp"] if "workout_minutes_mfp" in combined else pd.Series(pd.NA, index=combined.index)
    output["apple_exercise_time_min"] = apple_workout if apple_workout is not None else pd.Series(pd.NA, index=combined.index)
    output["workout_minutes"] = combine_first_nonempty(apple_workout, mfp_workout, combined.index)
    return output.sort_values("date")


def combine_body_metrics(apple_body: pd.DataFrame, mfp_body: pd.DataFrame) -> pd.DataFrame:
    apple = normalize_daily_frame(apple_body)
    mfp = normalize_daily_frame(mfp_body)
    combined = merge_on_date([apple, mfp], suffixes=("_apple", "_mfp"))
    if combined.empty:
        return pd.DataFrame(columns=["date", "weight_lb"])

    output = pd.DataFrame({"date": combined["date"]})
    apple_weight = combined["weight_lb_apple"] if "weight_lb_apple" in combined else combined.get("weight_lb")
    mfp_weight = combined["weight_lb_mfp"] if "weight_lb_mfp" in combined else pd.Series(pd.NA, index=combined.index)
    output["weight_lb"] = combine_first_nonempty(apple_weight, mfp_weight, combined.index)
    return output.sort_values("date")


def combine_first_nonempty(
    primary: pd.Series | None,
    fallback: pd.Series | None,
    index: pd.Index,
) -> pd.Series:
    """Combine two optional series without triggering pandas all-empty concat warnings."""

    empty = pd.Series(pd.NA, index=index)
    if primary is None:
        return fallback if fallback is not None else empty
    if fallback is None or fallback.isna().all():
        return primary
    if primary.isna().all():
        return fallback
    return primary.combine_first(fallback)


def build_dashboard_fact(
    daily_nutrition: pd.DataFrame,
    daily_micronutrients: pd.DataFrame,
    daily_activity: pd.DataFrame,
    daily_sleep: pd.DataFrame,
    daily_body_metrics: pd.DataFrame,
    config: PipelineConfig,
    daily_recovery: pd.DataFrame | None = None,
) -> pd.DataFrame:
    frames = [
        normalize_daily_frame(daily_nutrition),
        normalize_daily_frame(pivot_micronutrients_if_needed(daily_micronutrients)),
        normalize_daily_frame(daily_activity),
        normalize_daily_frame(daily_sleep),
        normalize_daily_frame(daily_recovery),
        normalize_daily_frame(daily_body_metrics),
    ]
    date_spine = build_date_spine(frames, config)
    if date_spine.empty:
        columns = FACT_BASE_COLUMNS + [
            "calories_7d_avg",
            "protein_7d_avg",
            "weight_7d_avg",
            "sleep_7d_avg",
            "resting_hr_7d_avg",
            "hrv_7d_avg",
            "weight_measurement_flag",
        ]
        return pd.DataFrame(columns=columns)

    fact = merge_on_date([date_spine] + frames)
    fact = apply_date_filters(fact, config).sort_values("date").reset_index(drop=True)

    for column in FACT_BASE_COLUMNS:
        if column not in fact:
            fact[column] = pd.NA

    if "alcohol_consumption_count" not in fact:
        fact["alcohol_consumption_count"] = pd.NA

    fact["calories_7d_avg"] = pd.to_numeric(fact["calories"], errors="coerce").rolling(7, min_periods=1).mean()
    fact["protein_7d_avg"] = pd.to_numeric(fact["protein_g"], errors="coerce").rolling(7, min_periods=1).mean()
    fact["weight_7d_avg"] = pd.to_numeric(fact["weight_lb"], errors="coerce").rolling(7, min_periods=1).mean()
    fact["sleep_7d_avg"] = pd.to_numeric(fact["sleep_hours"], errors="coerce").rolling(7, min_periods=1).mean()
    fact["resting_hr_7d_avg"] = pd.to_numeric(fact["resting_hr"], errors="coerce").rolling(7, min_periods=1).mean()
    fact["hrv_7d_avg"] = pd.to_numeric(fact["hrv_ms"], errors="coerce").rolling(7, min_periods=1).mean()
    fact["weight_measurement_flag"] = pd.to_numeric(fact["weight_lb"], errors="coerce").notna().astype("int8")

    if config.calorie_target is not None:
        fact["calorie_delta_from_target"] = pd.to_numeric(fact["calories"], errors="coerce") - config.calorie_target
    if config.protein_target_g is not None:
        fact["protein_delta_from_target"] = pd.to_numeric(fact["protein_g"], errors="coerce") - config.protein_target_g

    return order_fact_columns(fact)


def normalize_daily_frame(frame: pd.DataFrame | None) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame(columns=["date"])
    output = frame.copy()
    if "date" not in output:
        return pd.DataFrame(columns=["date"])
    output["date"] = pd.to_datetime(output["date"], errors="coerce").dt.date
    output = output.dropna(subset=["date"])
    return output


def merge_on_date(frames: list[pd.DataFrame], suffixes: tuple[str, str] = ("_x", "_y")) -> pd.DataFrame:
    valid_frames = [frame for frame in frames if frame is not None and not frame.empty]
    if not valid_frames:
        return pd.DataFrame(columns=["date"])

    merged = valid_frames[0]
    for frame in valid_frames[1:]:
        overlapping = [column for column in merged.columns if column in frame.columns and column != "date"]
        merged = merged.merge(frame, on="date", how="outer", suffixes=suffixes if overlapping else ("", ""))
    return merged.sort_values("date")


def build_date_spine(frames: list[pd.DataFrame], config: PipelineConfig) -> pd.DataFrame:
    dates: list[object] = []
    for frame in frames:
        if frame is not None and not frame.empty and "date" in frame:
            dates.extend(frame["date"].dropna().tolist())

    start = pd.to_datetime(config.start_date).date() if config.start_date else None
    end = pd.to_datetime(config.end_date).date() if config.end_date else None

    if not dates and (start is None or end is None):
        return pd.DataFrame(columns=["date"])
    start = start or min(dates)
    end = end or max(dates)
    return pd.DataFrame({"date": pd.date_range(start, end, freq="D").date})


def apply_date_filters(frame: pd.DataFrame, config: PipelineConfig) -> pd.DataFrame:
    output = frame.copy()
    if config.start_date:
        output = output[output["date"] >= pd.to_datetime(config.start_date).date()]
    if config.end_date:
        output = output[output["date"] <= pd.to_datetime(config.end_date).date()]
    return output


def pivot_micronutrients_if_needed(frame: pd.DataFrame) -> pd.DataFrame:
    if frame is None or frame.empty or "nutrient" not in frame or "value" not in frame:
        return frame
    return frame.pivot_table(index="date", columns="nutrient", values="value", aggfunc="sum").reset_index()


def wide_to_long_nutrients(frame: pd.DataFrame) -> pd.DataFrame:
    normalized = normalize_daily_frame(frame)
    value_columns = [column for column in normalized.columns if column != "date"]
    if not value_columns:
        return pd.DataFrame(columns=["date", "nutrient", "value"])
    return normalized.melt(id_vars="date", value_vars=value_columns, var_name="nutrient", value_name="value").dropna(subset=["value"])


def order_fact_columns(fact: pd.DataFrame) -> pd.DataFrame:
    rolling_columns = [
        "calories_7d_avg",
        "protein_7d_avg",
        "weight_7d_avg",
        "sleep_7d_avg",
        "resting_hr_7d_avg",
        "hrv_7d_avg",
        "weight_measurement_flag",
    ]
    target_columns = [column for column in ["calorie_delta_from_target", "protein_delta_from_target"] if column in fact]
    known = FACT_PREFERRED_ORDER + rolling_columns + target_columns
    extra_columns = sorted([column for column in fact.columns if column not in known])
    return fact[[column for column in known + extra_columns if column in fact]]


def summarize_missing_fields(fact: pd.DataFrame, expected_fields: list[str]) -> list[str]:
    missing = []
    for field in expected_fields:
        if field not in fact.columns or fact[field].isna().all():
            missing.append(field)
    return missing
