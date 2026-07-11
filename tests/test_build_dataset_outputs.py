from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pandas as pd

from src.build_dataset import OUTPUT_FILES, SQLITE_TABLES, load_apple_health_source, resolve_input_paths, write_outputs
from src.config import PROJECT_ROOT, PipelineConfig
from src.ingest_mfp import load_mfp_data
from src.transform_daily import DailyModels, build_daily_models


def minimal_models() -> DailyModels:
    date = pd.Timestamp("2026-01-01").date()
    return DailyModels(
        daily_nutrition=pd.DataFrame({"date": [date], "calories": [2100], "protein_g": [180]}),
        daily_micronutrients=pd.DataFrame({"date": [date], "iron_mg": [8.5]}),
        daily_activity=pd.DataFrame({"date": [date], "steps": [9000]}),
        daily_sleep=pd.DataFrame({"date": [date], "sleep_hours": [7.5]}),
        daily_recovery=pd.DataFrame({"date": [date], "resting_hr": [58], "hrv_ms": [65]}),
        daily_body_metrics=pd.DataFrame({"date": [date], "weight_lb": [182.0]}),
        dashboard_fact=pd.DataFrame({"date": [date], "calories": [2100], "protein_g": [180]}),
        missing_fields=[],
    )


def test_csv_output_mode_preserves_existing_output_files(tmp_path: Path) -> None:
    config = PipelineConfig(processed_dir=tmp_path)

    outputs = write_outputs(minimal_models(), config)

    assert set(outputs) == set(OUTPUT_FILES)
    for key, filename in OUTPUT_FILES.items():
        assert outputs[key] == tmp_path / filename
        assert outputs[key].exists()
    assert "sqlite_database" not in outputs


def test_sqlite_output_mode_writes_expected_tables(tmp_path: Path) -> None:
    database_path = tmp_path / "health_metrics.db"
    config = PipelineConfig(
        processed_dir=tmp_path,
        output_mode="sqlite",
        database_url=f"sqlite:///{database_path.as_posix()}",
    )

    outputs = write_outputs(minimal_models(), config)

    assert outputs == {"sqlite_database": database_path}
    assert not list(tmp_path.glob("*.csv"))

    with sqlite3.connect(database_path) as connection:
        table_names = {
            row[0]
            for row in connection.execute("select name from sqlite_master where type = 'table'").fetchall()
        }
        assert table_names == set(SQLITE_TABLES.values())
        fact_row = connection.execute("select date, calories from health_dashboard_fact").fetchone()

    assert fact_row == ("2026-01-01", 2100)


def test_sample_etl_still_writes_dashboard_csv_outputs(tmp_path: Path) -> None:
    config = PipelineConfig(processed_dir=tmp_path)
    mfp_dir, apple_autoexport_csv, apple_xml, using_sample = resolve_input_paths(config, force_sample=True)

    mfp_data = load_mfp_data(mfp_dir, config)
    apple_data = load_apple_health_source(config, apple_autoexport_csv, apple_xml)
    models = build_daily_models(
        mfp_nutrition=mfp_data.daily_nutrition,
        mfp_micronutrients=mfp_data.daily_micronutrients,
        mfp_activity=mfp_data.daily_activity,
        mfp_body_metrics=mfp_data.daily_body_metrics,
        apple_activity=apple_data.daily_activity,
        apple_sleep=apple_data.daily_sleep,
        apple_body_metrics=apple_data.daily_body_metrics,
        apple_recovery=apple_data.daily_recovery,
        config=config,
    )

    outputs = write_outputs(models, config)
    fact = pd.read_csv(outputs["dashboard_fact"])

    assert using_sample is True
    assert set(outputs) == set(OUTPUT_FILES)
    assert not fact.empty
    assert "calories_7d_avg" in fact.columns
    assert "resting_hr_7d_avg" in fact.columns
    assert "hrv_7d_avg" in fact.columns
    assert "weight_measurement_flag" in fact.columns
    assert "daily_recovery" in outputs
    assert "respiratory_rate" in fact.columns
    assert fact.loc[0, "calories"] != 9999


def test_build_command_still_produces_core_outputs(tmp_path: Path) -> None:
    env = {
        **os.environ,
        "OUTPUT_MODE": "csv",
        "RUN_DATA_VALIDATION": "true",
        "USE_SAMPLE_DATA_IF_RAW_MISSING": "true",
    }

    result = subprocess.run(
        [
            sys.executable,
            "src/build_dataset.py",
            "--sample",
            "--processed-dir",
            str(tmp_path),
        ],
        cwd=PROJECT_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )

    for filename in OUTPUT_FILES.values():
        assert (tmp_path / filename).exists()
    assert (tmp_path / "data_quality_report.md").exists()
    assert (tmp_path / "data_quality_issues.csv").exists()
    assert "Data quality" in result.stdout


def test_apple_health_source_routing_uses_autoexport_sample() -> None:
    config = PipelineConfig(apple_health_source="autoexport_csv")
    _, autoexport_csv, apple_xml, _ = resolve_input_paths(config, force_sample=True)

    apple_data = load_apple_health_source(config, autoexport_csv, apple_xml)

    assert apple_data.records_read == 222
    assert "respiratory_rate" in apple_data.daily_recovery.columns


def test_apple_health_source_routing_can_disable_apple_health() -> None:
    config = PipelineConfig(apple_health_source="none")
    _, autoexport_csv, apple_xml, _ = resolve_input_paths(config, force_sample=True)

    apple_data = load_apple_health_source(config, autoexport_csv, apple_xml)

    assert apple_data.records_read == 0
    assert apple_data.daily_activity.empty


def test_apple_health_source_routing_can_use_xml_sample() -> None:
    config = PipelineConfig(apple_health_source="xml")
    _, autoexport_csv, apple_xml, _ = resolve_input_paths(config, force_sample=True)

    apple_data = load_apple_health_source(config, autoexport_csv, apple_xml)

    assert apple_data.records_read == 49
    assert "resting_hr" in apple_data.daily_recovery.columns

