from __future__ import annotations

import pandas as pd

from src.config import PipelineConfig
from src.transform_daily import build_dashboard_fact, wide_to_long_nutrients


def test_dashboard_fact_adds_rolling_averages_and_target_deltas() -> None:
    dates = pd.date_range("2026-01-01", periods=2, freq="D").date
    nutrition = pd.DataFrame(
        {
            "date": dates,
            "calories": [2000, 2200],
            "protein_g": [150, 170],
            "carbs_g": [210, 240],
            "fat_g": [70, 75],
        }
    )
    micronutrients = pd.DataFrame({"date": dates, "vitamin_c_mg": [80, 95]})
    activity = pd.DataFrame({"date": dates, "steps": [8000, 9000], "active_energy_kcal": [500, 600]})
    sleep = pd.DataFrame({"date": dates, "sleep_hours": [7.5, 8.0]})
    recovery = pd.DataFrame({"date": dates, "resting_hr": [58, 57], "hrv_ms": [65, 70]})
    body = pd.DataFrame({"date": dates, "weight_lb": [182.0, 181.5]})

    fact = build_dashboard_fact(
        daily_nutrition=nutrition,
        daily_micronutrients=micronutrients,
        daily_activity=activity,
        daily_sleep=sleep,
        daily_body_metrics=body,
        daily_recovery=recovery,
        config=PipelineConfig(calorie_target=2100, protein_target_g=160),
    )

    assert list(fact["date"]) == list(dates)
    assert fact.loc[1, "calories_7d_avg"] == 2100
    assert fact.loc[1, "protein_7d_avg"] == 160
    assert fact.loc[1, "resting_hr_7d_avg"] == 57.5
    assert fact.loc[1, "hrv_7d_avg"] == 67.5
    assert list(fact["weight_measurement_flag"]) == [1, 1]
    assert fact.loc[1, "calorie_delta_from_target"] == 100
    assert fact.loc[1, "protein_delta_from_target"] == 10
    assert fact.loc[1, "resting_hr"] == 57
    assert "vitamin_c_mg" in fact.columns


def test_weight_measurement_flag_preserves_sparse_weight_logging() -> None:
    dates = pd.date_range("2026-01-01", periods=9, freq="D").date
    body = pd.DataFrame({"date": [dates[0], dates[8]], "weight_lb": [182.0, 181.0]})

    fact = build_dashboard_fact(
        daily_nutrition=pd.DataFrame({"date": dates, "calories": [2200] * 9, "protein_g": [175] * 9}),
        daily_micronutrients=pd.DataFrame(),
        daily_activity=pd.DataFrame(),
        daily_sleep=pd.DataFrame(),
        daily_body_metrics=body,
        daily_recovery=pd.DataFrame(),
        config=PipelineConfig(),
    )

    assert list(fact["weight_measurement_flag"]) == [1, 0, 0, 0, 0, 0, 0, 0, 1]
    assert pd.isna(fact.loc[7, "weight_7d_avg"])
    assert fact.loc[8, "weight_7d_avg"] == 181.0


def test_wide_micronutrients_can_be_written_long() -> None:
    frame = pd.DataFrame({"date": ["2026-01-01"], "iron_mg": [5.2], "zinc_mg": [3.1]})

    long = wide_to_long_nutrients(frame)

    assert set(long["nutrient"]) == {"iron_mg", "zinc_mg"}
    assert set(long.columns) == {"date", "nutrient", "value"}
