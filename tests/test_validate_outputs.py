from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.config import PipelineConfig
from src.validate_outputs import validate_processed_outputs


def write_fact(path: Path, rows: list[dict[str, object]]) -> None:
    pd.DataFrame(rows).to_csv(path / "health_dashboard_fact.csv", index=False)


def write_micronutrients(path: Path) -> None:
    pd.DataFrame({"date": ["2026-01-01"], "iron_mg": [8.5]}).to_csv(
        path / "daily_micronutrients.csv",
        index=False,
    )


def complete_fact_row(date: str, **overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "date": date,
        "calories": 2200,
        "protein_g": 180,
        "carbs_g": 240,
        "fat_g": 70,
        "fiber_g": 30,
        "sugar_g": 50,
        "sodium_mg": 2300,
        "potassium_mg": 3500,
        "cholesterol_mg": 180,
        "weight_lb": 182,
        "steps": 9000,
        "active_energy_kcal": 650,
        "resting_energy_kcal": 1800,
        "sleep_hours": 7.5,
        "resting_hr": 58,
        "hrv_ms": 65,
        "workout_minutes": 45,
        "calorie_delta_from_target": -200,
        "protein_delta_from_target": 5,
        "iron_mg": 8.5,
    }
    row.update(overrides)
    return row


def test_validation_catches_duplicate_dates(tmp_path: Path) -> None:
    write_fact(
        tmp_path,
        [
            complete_fact_row("2026-01-01"),
            complete_fact_row("2026-01-01", calories=2300),
        ],
    )
    write_micronutrients(tmp_path)

    summary = validate_processed_outputs(PipelineConfig(processed_dir=tmp_path))
    issues = pd.read_csv(summary.issues_path)

    assert "duplicate_date" in set(issues["check"])


def test_validation_catches_impossible_values(tmp_path: Path) -> None:
    write_fact(
        tmp_path,
        [
            complete_fact_row(
                "2026-01-01",
                calories=-10,
                protein_g=-5,
                carbs_g=-1,
                fat_g=-2,
                weight_lb=35,
                sleep_hours=16,
                steps=60000,
                resting_hr=130,
                hrv_ms=2,
                alcohol_consumption_count=-1,
            )
        ],
    )
    write_micronutrients(tmp_path)

    summary = validate_processed_outputs(PipelineConfig(processed_dir=tmp_path))
    checks = set(pd.read_csv(summary.issues_path)["check"])

    assert {
        "negative_calories",
        "negative_macro",
        "suspicious_bodyweight",
        "suspicious_sleep",
        "suspicious_steps",
        "suspicious_resting_hr",
        "suspicious_hrv",
        "negative_alcohol_consumption",
    }.issubset(checks)


def test_validation_produces_report_files_and_micronutrient_summary(tmp_path: Path) -> None:
    write_fact(tmp_path, [complete_fact_row("2026-01-01", imputed_fields="")])
    write_micronutrients(tmp_path)

    summary = validate_processed_outputs(PipelineConfig(processed_dir=tmp_path))

    assert summary.report_path.exists()
    assert summary.issues_path.exists()
    assert summary.micronutrient_columns == ["iron_mg"]
    assert "Data Quality Report" in summary.report_path.read_text(encoding="utf-8")
    issues = pd.read_csv(summary.issues_path)
    assert not ((issues["check"] == "all_null_column") & (issues["column"] == "imputed_fields")).any()
