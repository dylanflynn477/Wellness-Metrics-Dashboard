"""Ingest exported MyFitnessPal CSV files."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

try:
    from .config import PipelineConfig
    from .utils import (
        clean_numeric_series,
        convert_weight_to_lb,
        detect_unit_suffix,
        empty_daily_frame,
        normalize_column_name,
        parse_date_series,
        read_csv_flex,
        strip_unit_text,
    )
except ImportError:  # pragma: no cover - supports `python src/build_dataset.py`
    from config import PipelineConfig
    from utils import (
        clean_numeric_series,
        convert_weight_to_lb,
        detect_unit_suffix,
        empty_daily_frame,
        normalize_column_name,
        parse_date_series,
        read_csv_flex,
        strip_unit_text,
    )


CORE_NUTRITION_FIELDS = [
    "calories",
    "protein_g",
    "carbs_g",
    "fat_g",
    "saturated_fat_g",
    "trans_fat_g",
    "cholesterol_mg",
    "sodium_mg",
    "potassium_mg",
    "fiber_g",
    "sugar_g",
]

TEXT_DIMENSIONS = {
    "date",
    "day",
    "meal",
    "meal_name",
    "food",
    "food_name",
    "description",
    "brand",
    "notes",
    "note",
    "time",
    "serving",
    "serving_size",
    "quantity",
    "qty",
    "unit",
}

NUTRIENT_SYNONYMS = {
    "calorie": "calories",
    "calories": "calories",
    "energy": "calories",
    "protein": "protein_g",
    "total_protein": "protein_g",
    "carb": "carbs_g",
    "carbs": "carbs_g",
    "carbohydrate": "carbs_g",
    "carbohydrates": "carbs_g",
    "total_carbohydrate": "carbs_g",
    "total_carbohydrates": "carbs_g",
    "fat": "fat_g",
    "total_fat": "fat_g",
    "saturated_fat": "saturated_fat_g",
    "sat_fat": "saturated_fat_g",
    "trans_fat": "trans_fat_g",
    "cholesterol": "cholesterol_mg",
    "sodium": "sodium_mg",
    "potassium": "potassium_mg",
    "fiber": "fiber_g",
    "fibre": "fiber_g",
    "dietary_fiber": "fiber_g",
    "dietary_fibre": "fiber_g",
    "sugar": "sugar_g",
    "sugars": "sugar_g",
    "total_sugars": "sugar_g",
}


@dataclass
class MfpData:
    daily_nutrition: pd.DataFrame
    daily_micronutrients: pd.DataFrame
    daily_activity: pd.DataFrame
    daily_body_metrics: pd.DataFrame
    files_read: list[Path]
    rows_read: int


def load_mfp_data(mfp_dir: Path, config: PipelineConfig) -> MfpData:
    """Load and aggregate all supported MyFitnessPal CSV exports in a folder."""

    csv_files = sorted(Path(mfp_dir).glob("*.csv")) if Path(mfp_dir).exists() else []
    nutrition_frames: list[pd.DataFrame] = []
    exercise_frames: list[pd.DataFrame] = []
    progress_frames: list[pd.DataFrame] = []
    files_read: list[Path] = []
    rows_read = 0

    for path in csv_files:
        frame = read_csv_flex(path)
        category = classify_mfp_csv(path, frame)
        files_read.append(path)
        rows_read += len(frame)
        if category == "nutrition":
            nutrition_frames.append(standardize_nutrition_frame(frame))
        elif category == "exercise":
            exercise_frames.append(standardize_exercise_frame(frame))
        elif category == "progress":
            progress_frames.append(standardize_progress_frame(frame, config))

    nutrition = aggregate_nutrition(nutrition_frames)
    activity = aggregate_exercise(exercise_frames)
    body_metrics = aggregate_progress(progress_frames)

    return MfpData(
        daily_nutrition=nutrition[0],
        daily_micronutrients=nutrition[1],
        daily_activity=activity,
        daily_body_metrics=body_metrics,
        files_read=files_read,
        rows_read=rows_read,
    )


def classify_mfp_csv(path: Path, frame: pd.DataFrame) -> str:
    name = path.name.lower()
    columns = {normalize_column_name(col) for col in frame.columns}

    if any(token in name for token in ["exercise", "workout", "activity"]):
        return "exercise"
    if any(token in name for token in ["progress", "measurement", "weight", "body"]):
        return "progress"
    if any(token in name for token in ["nutrition", "food", "diary", "meal"]):
        return "nutrition"

    if columns.intersection({"food", "food_name", "meal", "meal_name"}) and columns.intersection({"calories", "calorie"}):
        return "nutrition"
    if columns.intersection({"exercise", "workout", "duration", "minutes", "calories_burned"}):
        return "exercise"
    if columns.intersection({"weight", "weight_lb", "weight_lbs", "body_weight"}):
        return "progress"
    return "nutrition"


def standardize_nutrition_frame(frame: pd.DataFrame) -> pd.DataFrame:
    date_column = find_first_column(frame, ["date", "day", "entry_date", "log_date"])
    if date_column is None:
        return pd.DataFrame()

    output = pd.DataFrame({"date": parse_date_series(frame[date_column])})
    for raw_column in frame.columns:
        normalized = normalize_column_name(raw_column)
        if raw_column == date_column or normalized in TEXT_DIMENSIONS:
            continue
        numeric = clean_numeric_series(frame[raw_column])
        if numeric.notna().sum() == 0:
            continue
        metric_name = nutrient_metric_name(raw_column)
        if metric_name in TEXT_DIMENSIONS:
            continue
        output[metric_name] = numeric

    output = output.dropna(subset=["date"])
    return output


def standardize_exercise_frame(frame: pd.DataFrame) -> pd.DataFrame:
    date_column = find_first_column(frame, ["date", "day", "entry_date", "log_date"])
    if date_column is None:
        return pd.DataFrame()

    output = pd.DataFrame({"date": parse_date_series(frame[date_column])})
    minutes_column = find_first_column(frame, ["minutes", "duration", "duration_minutes", "time_minutes", "exercise_minutes"])
    calories_column = find_first_column(frame, ["calories_burned", "exercise_calories", "calories", "energy_burned"])

    if minutes_column is not None:
        output["workout_minutes"] = clean_numeric_series(frame[minutes_column])
    if calories_column is not None:
        output["mfp_exercise_calories"] = clean_numeric_series(frame[calories_column])

    return output.dropna(subset=["date"])


def standardize_progress_frame(frame: pd.DataFrame, config: PipelineConfig) -> pd.DataFrame:
    date_column = find_first_column(frame, ["date", "day", "entry_date", "log_date"])
    weight_column = find_first_column(frame, ["weight_lb", "weight_lbs", "weight", "body_weight", "body_mass"])
    if date_column is None or weight_column is None:
        return pd.DataFrame()

    output = pd.DataFrame({"date": parse_date_series(frame[date_column])})
    values = clean_numeric_series(frame[weight_column])
    unit = infer_weight_unit(weight_column, config.bodyweight_unit_preference)
    output["weight_lb"] = values.map(lambda value: convert_weight_to_lb(value, unit) if pd.notna(value) else pd.NA)
    return output.dropna(subset=["date"])


def aggregate_nutrition(frames: list[pd.DataFrame]) -> tuple[pd.DataFrame, pd.DataFrame]:
    valid_frames = [frame for frame in frames if not frame.empty]
    if not valid_frames:
        return empty_daily_frame(CORE_NUTRITION_FIELDS), empty_daily_frame([])

    combined = pd.concat(valid_frames, ignore_index=True)
    nutrient_columns = [col for col in combined.columns if col != "date"]
    daily = combined.groupby("date", as_index=False)[nutrient_columns].sum(min_count=1)

    for column in CORE_NUTRITION_FIELDS:
        if column not in daily:
            daily[column] = pd.NA

    daily_nutrition = daily[["date"] + CORE_NUTRITION_FIELDS].sort_values("date")
    micronutrient_columns = sorted([col for col in nutrient_columns if col not in CORE_NUTRITION_FIELDS])
    daily_micronutrients = daily[["date"] + micronutrient_columns].sort_values("date") if micronutrient_columns else empty_daily_frame([])
    return daily_nutrition, daily_micronutrients


def aggregate_exercise(frames: list[pd.DataFrame]) -> pd.DataFrame:
    valid_frames = [frame for frame in frames if not frame.empty]
    if not valid_frames:
        return empty_daily_frame(["workout_minutes", "mfp_exercise_calories"])
    combined = pd.concat(valid_frames, ignore_index=True)
    metric_columns = [col for col in combined.columns if col != "date"]
    return combined.groupby("date", as_index=False)[metric_columns].sum(min_count=1).sort_values("date")


def aggregate_progress(frames: list[pd.DataFrame]) -> pd.DataFrame:
    valid_frames = [frame for frame in frames if not frame.empty]
    if not valid_frames:
        return empty_daily_frame(["weight_lb"])
    combined = pd.concat(valid_frames, ignore_index=True)
    return combined.groupby("date", as_index=False).agg(weight_lb=("weight_lb", "mean")).sort_values("date")


def find_first_column(frame: pd.DataFrame, candidates: list[str]) -> str | None:
    normalized_lookup = {normalize_column_name(column): column for column in frame.columns}
    for candidate in candidates:
        if candidate in normalized_lookup:
            return normalized_lookup[candidate]
    return None


def nutrient_metric_name(raw_column: object) -> str:
    raw_text = str(raw_column)
    full_name = normalize_column_name(raw_text)
    if full_name in NUTRIENT_SYNONYMS:
        return NUTRIENT_SYNONYMS[full_name]

    semantic_name = strip_unit_text(raw_text)
    if semantic_name in NUTRIENT_SYNONYMS:
        return NUTRIENT_SYNONYMS[semantic_name]

    unit = detect_unit_suffix(raw_text)
    if semantic_name.startswith("total_"):
        semantic_name = semantic_name.removeprefix("total_")
    if unit and not semantic_name.endswith(f"_{unit}"):
        return f"{semantic_name}_{unit}"
    return semantic_name


def infer_weight_unit(column_name: object, default_unit: str) -> str:
    normalized = normalize_column_name(column_name)
    if any(token in normalized for token in ["kg", "kilogram"]):
        return "kg"
    if any(token in normalized for token in ["lb", "lbs", "pound"]):
        return "lb"
    return default_unit
