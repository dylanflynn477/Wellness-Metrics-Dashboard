from __future__ import annotations

from pathlib import Path

import pytest

from src.ingest_apple_health import load_apple_health_data


def test_apple_health_xml_parses_daily_metrics(tmp_path: Path) -> None:
    export_xml = tmp_path / "export.xml"
    export_xml.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<HealthData locale="en_US">
  <Record type="HKQuantityTypeIdentifierStepCount" unit="count" startDate="2026-01-01 08:00:00 -0500" endDate="2026-01-01 12:00:00 -0500" value="1200"/>
  <Record type="HKQuantityTypeIdentifierActiveEnergyBurned" unit="kJ" startDate="2026-01-01 08:00:00 -0500" endDate="2026-01-01 12:00:00 -0500" value="418.4"/>
  <Record type="HKQuantityTypeIdentifierBodyMass" unit="kg" startDate="2026-01-01 07:00:00 -0500" endDate="2026-01-01 07:00:00 -0500" value="82"/>
  <Record type="HKQuantityTypeIdentifierRestingHeartRate" unit="count/min" startDate="2026-01-01 00:00:00 -0500" endDate="2026-01-01 23:59:59 -0500" value="56"/>
  <Record type="HKQuantityTypeIdentifierHeartRateVariabilitySDNN" unit="ms" startDate="2026-01-01 07:00:00 -0500" endDate="2026-01-01 07:05:00 -0500" value="67"/>
  <Record type="HKCategoryTypeIdentifierSleepAnalysis" value="HKCategoryValueSleepAnalysisAsleepCore" startDate="2026-01-01 23:00:00 -0500" endDate="2026-01-02 07:00:00 -0500"/>
  <Workout workoutActivityType="HKWorkoutActivityTypeWalking" duration="45" durationUnit="min" startDate="2026-01-01 18:00:00 -0500" endDate="2026-01-01 18:45:00 -0500"/>
</HealthData>
""",
        encoding="utf-8",
    )

    result = load_apple_health_data(export_xml)

    activity = result.daily_activity.set_index("date")
    sleep = result.daily_sleep.set_index("date")
    body = result.daily_body_metrics.set_index("date")
    recovery = result.daily_recovery.set_index("date")

    assert activity.iloc[0]["steps"] == 1200
    assert activity.iloc[0]["active_energy_kcal"] == pytest.approx(100, rel=0.01)
    assert activity.iloc[0]["apple_exercise_time_min"] == 45
    assert activity.iloc[0]["workout_minutes"] == 45
    assert sleep.iloc[0]["sleep_hours"] == 8
    assert body.iloc[0]["weight_lb"] == pytest.approx(180.78, rel=0.01)
    assert recovery.iloc[0]["resting_hr"] == 56
    assert recovery.iloc[0]["hrv_ms"] == 67
