"""Command-line entry point for building dashboard-ready health datasets."""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

import pandas as pd

try:
    from .config import PipelineConfig, default_config
    from .connectors import AppleHealthExportConnector, MfpExportConnector
    from .transform_daily import DailyModels, build_daily_models, wide_to_long_nutrients
    from .utils import ensure_directories, setup_logging
except ImportError:  # pragma: no cover - supports `python src/build_dataset.py`
    from config import PipelineConfig, default_config
    from connectors import AppleHealthExportConnector, MfpExportConnector
    from transform_daily import DailyModels, build_daily_models, wide_to_long_nutrients
    from utils import ensure_directories, setup_logging


OUTPUT_FILES = {
    "daily_nutrition": "daily_nutrition.csv",
    "daily_micronutrients": "daily_micronutrients.csv",
    "daily_activity": "daily_activity.csv",
    "daily_sleep": "daily_sleep.csv",
    "daily_body_metrics": "daily_body_metrics.csv",
    "dashboard_fact": "health_dashboard_fact.csv",
}

SQLITE_TABLES = {
    "daily_nutrition": "daily_nutrition",
    "daily_micronutrients": "daily_micronutrients",
    "daily_activity": "daily_activity",
    "daily_sleep": "daily_sleep",
    "daily_body_metrics": "daily_body_metrics",
    "dashboard_fact": "health_dashboard_fact",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build wellness dashboard datasets from exported MFP and Apple Health data.")
    parser.add_argument("--mfp-dir", type=Path, default=None, help="Folder containing MyFitnessPal CSV exports.")
    parser.add_argument("--apple-health-xml", type=Path, default=None, help="Path to Apple Health export.xml.")
    parser.add_argument("--processed-dir", type=Path, default=None, help="Output folder for processed CSV files.")
    parser.add_argument("--sample", action="store_true", help="Force use of synthetic sample data.")
    parser.add_argument("--no-sample-fallback", action="store_true", help="Do not use sample data when raw folders are empty.")
    parser.add_argument("--log-level", default="INFO", help="Logging level.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    logger = setup_logging(args.log_level)
    config = default_config()
    config = PipelineConfig(
        app_env=config.app_env,
        raw_mfp_dir=args.mfp_dir or config.raw_mfp_dir,
        raw_apple_health_xml=args.apple_health_xml or config.raw_apple_health_xml,
        sample_mfp_dir=config.sample_mfp_dir,
        sample_apple_health_xml=config.sample_apple_health_xml,
        processed_dir=args.processed_dir or config.processed_dir,
        calorie_target=config.calorie_target,
        protein_target_g=config.protein_target_g,
        bodyweight_unit_preference=config.bodyweight_unit_preference,
        start_date=config.start_date,
        end_date=config.end_date,
        nutrient_output_mode=config.nutrient_output_mode,
        output_mode=config.output_mode,
        database_url=config.database_url,
        use_sample_data_if_raw_missing=False if args.no_sample_fallback else config.use_sample_data_if_raw_missing,
    )

    ensure_directories([config.raw_mfp_dir, config.raw_apple_health_xml.parent, config.processed_dir])
    mfp_dir, apple_xml, using_sample = resolve_input_paths(config, force_sample=args.sample)
    if using_sample:
        logger.info("Using synthetic sample data. Add real exports under data/raw/ to process personal data.")

    logger.info("Loading MyFitnessPal exports from %s", mfp_dir)
    mfp_data = MfpExportConnector(mfp_dir=mfp_dir, config=config).load()
    logger.info("Loading Apple Health export from %s", apple_xml)
    apple_data = AppleHealthExportConnector(export_xml=apple_xml).load()

    models = build_daily_models(
        mfp_nutrition=mfp_data.daily_nutrition,
        mfp_micronutrients=mfp_data.daily_micronutrients,
        mfp_activity=mfp_data.daily_activity,
        mfp_body_metrics=mfp_data.daily_body_metrics,
        apple_activity=apple_data.daily_activity,
        apple_sleep=apple_data.daily_sleep,
        apple_body_metrics=apple_data.daily_body_metrics,
        config=config,
    )

    outputs = write_outputs(models, config)
    print_summary(
        models=models,
        outputs=outputs,
        mfp_files=len(mfp_data.files_read),
        mfp_rows=mfp_data.rows_read,
        apple_records=apple_data.records_read,
        apple_workouts=apple_data.workouts_read,
        using_sample=using_sample,
    )


def resolve_input_paths(config: PipelineConfig, force_sample: bool = False) -> tuple[Path, Path, bool]:
    raw_has_mfp = config.raw_mfp_dir.exists() and any(config.raw_mfp_dir.glob("*.csv"))
    raw_has_apple = config.raw_apple_health_xml.exists()
    use_sample = force_sample or (config.use_sample_data_if_raw_missing and not raw_has_mfp and not raw_has_apple)
    if use_sample:
        return config.sample_mfp_dir, config.sample_apple_health_xml, True
    return config.raw_mfp_dir, config.raw_apple_health_xml, False


def write_outputs(models: DailyModels, config: PipelineConfig) -> dict[str, Path]:
    ensure_directories([config.processed_dir])
    micronutrients = models.daily_micronutrients
    if config.nutrient_output_mode == "long":
        micronutrients = wide_to_long_nutrients(micronutrients)

    frames: dict[str, pd.DataFrame] = {
        "daily_nutrition": models.daily_nutrition,
        "daily_micronutrients": micronutrients,
        "daily_activity": models.daily_activity,
        "daily_sleep": models.daily_sleep,
        "daily_body_metrics": models.daily_body_metrics,
        "dashboard_fact": models.dashboard_fact,
    }

    output_paths: dict[str, Path] = {}
    if config.output_mode in {"csv", "both"}:
        output_paths.update(write_csv_outputs(frames, config))
    if config.output_mode in {"sqlite", "both"}:
        output_paths["sqlite_database"] = write_sqlite_outputs(frames, config)
    return output_paths


def write_csv_outputs(frames: dict[str, pd.DataFrame], config: PipelineConfig) -> dict[str, Path]:
    output_paths = {}
    for key, frame in frames.items():
        path = config.processed_dir / OUTPUT_FILES[key]
        frame.to_csv(path, index=False)
        output_paths[key] = path
    return output_paths


def write_sqlite_outputs(frames: dict[str, pd.DataFrame], config: PipelineConfig) -> Path:
    database_path = config.sqlite_database_path
    ensure_directories([database_path.parent])
    with sqlite3.connect(database_path) as connection:
        for key, frame in frames.items():
            prepare_sqlite_frame(frame).to_sql(SQLITE_TABLES[key], connection, if_exists="replace", index=False)
    return database_path


def prepare_sqlite_frame(frame: pd.DataFrame) -> pd.DataFrame:
    output = frame.copy()
    if "date" in output:
        output["date"] = pd.to_datetime(output["date"], errors="coerce").dt.strftime("%Y-%m-%d")
    return output


def print_summary(
    models: DailyModels,
    outputs: dict[str, Path],
    mfp_files: int,
    mfp_rows: int,
    apple_records: int,
    apple_workouts: int,
    using_sample: bool,
) -> None:
    fact = models.dashboard_fact
    if fact.empty:
        date_range = "no modeled dates"
    else:
        date_range = f"{fact['date'].min()} to {fact['date'].max()}"

    missing = ", ".join(models.missing_fields) if models.missing_fields else "none"
    source = "synthetic sample data" if using_sample else "raw exports"
    print("\nWellness ETL summary")
    print(f"- Source: {source}")
    print(f"- MyFitnessPal: {mfp_files} file(s), {mfp_rows} row(s)")
    print(f"- Apple Health: {apple_records} record(s), {apple_workouts} workout(s)")
    print(f"- Dashboard fact rows: {len(fact)}")
    print(f"- Date range: {date_range}")
    print(f"- Missing/all-null expected fields: {missing}")
    print("- Outputs:")
    for label, path in outputs.items():
        print(f"  - {label}: {path}")


if __name__ == "__main__":
    main()

