from __future__ import annotations

import pandas as pd

from src.config import PipelineConfig
from src.impute_daily import ImputationOptions, impute_dashboard_fact


def test_imputation_corrects_local_anomalies_and_preserves_phase_shift() -> None:
    dates = pd.date_range("2026-01-01", periods=42, freq="D").date
    calories = [4000.0] * 21 + [2500.0] * 21
    protein = [210.0] * 21 + [180.0] * 21
    carbs = [500.0] * 21 + [260.0] * 21
    fat = [120.0] * 21 + [80.0] * 21
    calories[8] = 400.0
    protein[8] = 25.0
    carbs[8] = 30.0
    fat[8] = 12.0

    fact = pd.DataFrame(
        {
            "date": dates,
            "calories": calories,
            "protein_g": protein,
            "carbs_g": carbs,
            "fat_g": fat,
            "sleep_hours": [8.0] * 42,
            "steps": [9000] * 42,
            "resting_hr": [60] * 42,
            "hrv_ms": [65] * 42,
            "weight_lb": [180.0] * 42,
        }
    )
    original = fact.copy(deep=True)

    result = impute_dashboard_fact(fact, PipelineConfig())

    assert result.dashboard_fact.loc[8, "calories"] == 4000
    assert result.dashboard_fact.loc[8, "protein_g"] == 210
    assert result.dashboard_fact.loc[25, "calories"] == 2500
    assert result.dashboard_fact.loc[8, "imputation_count"] == 4
    assert result.dashboard_fact.loc[8, "imputed_fields"] == "calories;carbs_g;fat_g;protein_g"
    assert set(result.report[result.report["date"] == dates[8]]["reason"]) == {
        "below_hard_minimum",
        "calorie_day_adjustment",
    }
    pd.testing.assert_frame_equal(fact, original)


def test_imputation_fills_short_gaps_but_preserves_long_gaps() -> None:
    dates = pd.date_range("2026-01-01", periods=35, freq="D").date
    calories = pd.Series([3000.0] * 35)
    calories.loc[5:6] = pd.NA
    calories.loc[20:24] = pd.NA
    fact = pd.DataFrame(
        {
            "date": dates,
            "calories": calories,
            "protein_g": [190.0] * 35,
            "carbs_g": [350.0] * 35,
            "fat_g": [90.0] * 35,
            "sleep_hours": [8.0] * 35,
        }
    )

    result = impute_dashboard_fact(
        fact,
        PipelineConfig(),
        ImputationOptions(max_gap_days=3),
    )

    assert result.dashboard_fact.loc[5:6, "calories"].eq(3000).all()
    assert result.dashboard_fact.loc[20:24, "calories"].isna().all()
    assert set(result.report[result.report["field"] == "calories"]["reason"]) == {"missing_short_gap"}


def test_imputation_corrects_implausible_sleep_and_wearable_values() -> None:
    dates = pd.date_range("2026-01-01", periods=25, freq="D").date
    sleep = [8.0] * 25
    steps = [9000] * 25
    resting_hr = [60.0] * 25
    hrv = [65.0] * 25
    sleep[10] = 16.5
    steps[11] = 60000
    resting_hr[12] = 140
    hrv[13] = 2
    fact = pd.DataFrame(
        {
            "date": dates,
            "calories": [2800.0] * 25,
            "protein_g": [180.0] * 25,
            "carbs_g": [320.0] * 25,
            "fat_g": [85.0] * 25,
            "sleep_hours": sleep,
            "steps": steps,
            "resting_hr": resting_hr,
            "hrv_ms": hrv,
        }
    )

    result = impute_dashboard_fact(fact, PipelineConfig())
    output = result.dashboard_fact

    assert output.loc[10, "sleep_hours"] == 8
    assert output.loc[11, "steps"] == 9000
    assert output.loc[12, "resting_hr"] == 60
    assert output.loc[13, "hrv_ms"] == 65
    assert result.changed_days == 4
    assert result.changed_values == 4
