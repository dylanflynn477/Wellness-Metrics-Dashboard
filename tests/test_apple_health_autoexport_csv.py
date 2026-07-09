from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.config import PipelineConfig
from src.connectors.apple_health_autoexport_csv import (
    AppleHealthAutoExportCsvConnector,
    match_autoexport_column,
    resolve_autoexport_csv,
)
from src.ingest_mfp import load_mfp_data
from src.transform_daily import build_daily_models


def test_match_autoexport_column_handles_likely_variants() -> None:
    columns = [
        "Date/Time",
        "Step Count (count)",
        "Active Energy (kcal)",
        "Resting Heart Rate (count/min)",
        "Heart Rate Variability SDNN (ms)",
        "Sleep Analysis [Total] (hr)",
    ]

    assert match_autoexport_column(columns, "date") == "Date/Time"
    assert match_autoexport_column(columns, "steps") == "Step Count (count)"
    assert match_autoexport_column(columns, "active_energy_kcal") == "Active Energy (kcal)"
    assert match_autoexport_column(columns, "resting_hr") == "Resting Heart Rate (count/min)"
    assert match_autoexport_column(columns, "hrv_ms") == "Heart Rate Variability SDNN (ms)"
    assert match_autoexport_column(columns, "sleep_total_hours") == "Sleep Analysis [Total] (hr)"


def test_resolve_autoexport_csv_falls_back_to_date_stamped_file(tmp_path: Path) -> None:
    dated_file = tmp_path / "HealthAutoExport-2025-11-27-2026-07-06.csv"
    dated_file.write_text("Date/Time,Step Count (steps)\n2026-01-01,1000\n", encoding="utf-8")

    assert resolve_autoexport_csv(tmp_path / "HealthAutoExport.csv") == dated_file


def test_autoexport_csv_loads_activity_sleep_and_recovery_sample() -> None:
    config = PipelineConfig()

    result = AppleHealthAutoExportCsvConnector(config.sample_apple_health_autoexport_csv).load()

    assert result.records_read == 7
    assert result.daily_activity.loc[0, "steps"] == 8420
    assert result.daily_activity.loc[0, "resting_energy_kcal"] == 1830
    assert result.daily_sleep.loc[0, "sleep_hours"] == 7.75
    assert result.daily_recovery.loc[0, "resting_hr"] == 58
    assert result.daily_recovery.loc[0, "blood_oxygen_pct"] == 97


def test_autoexport_sleep_uses_stages_when_asleep_is_zero_and_total_missing(tmp_path: Path) -> None:
    csv_path = tmp_path / "HealthAutoExport.csv"
    pd.DataFrame(
        {
            "Date": ["2026-01-01"],
            "Sleep Analysis [Asleep] (hr)": [0],
            "Sleep Analysis [Core] (hr)": [4.5],
            "Sleep Analysis [Deep] (hr)": [1.2],
            "Sleep Analysis [REM] (hr)": [1.8],
        }
    ).to_csv(csv_path, index=False)

    result = AppleHealthAutoExportCsvConnector(csv_path).load()

    assert result.daily_sleep.loc[0, "sleep_hours"] == 7.5


def test_autoexport_nutrition_columns_are_ignored_by_default() -> None:
    config = PipelineConfig()
    mfp_data = load_mfp_data(config.sample_mfp_dir, config)
    apple_data = AppleHealthAutoExportCsvConnector(config.sample_apple_health_autoexport_csv).load()

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

    assert models.dashboard_fact.loc[0, "calories"] == 1380
    assert models.dashboard_fact.loc[0, "protein_g"] == 100
    assert 9999 not in set(models.daily_nutrition["calories"])
