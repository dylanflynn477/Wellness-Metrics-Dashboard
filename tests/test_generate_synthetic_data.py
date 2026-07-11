from __future__ import annotations

import csv
from datetime import date
from pathlib import Path

from src.config import PipelineConfig
from src.connectors.apple_health_autoexport_csv import AppleHealthAutoExportCsvConnector
from src.generate_synthetic_data import generate_synthetic_dataset
from src.ingest_mfp import load_mfp_data
from src.transform_daily import build_daily_models


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_synthetic_generator_is_deterministic_and_matches_reference_coverage(tmp_path: Path) -> None:
    first = generate_synthetic_dataset(tmp_path / "first")
    second = generate_synthetic_dataset(tmp_path / "second")

    for key in first:
        assert first[key].read_bytes() == second[key].read_bytes()

    assert len(read_rows(first["mfp_nutrition"])) == 583
    assert len(read_rows(first["mfp_exercise"])) == 296
    assert len(read_rows(first["mfp_progress"])) == 19
    apple_rows = read_rows(first["apple_health_autoexport"])
    assert len(apple_rows) == 222
    assert apple_rows[0]["Date/Time"] == "2025-11-27"
    assert apple_rows[-1]["Date/Time"] == "2026-07-06"


def test_synthetic_sources_build_a_complete_private_value_free_fact(tmp_path: Path) -> None:
    outputs = generate_synthetic_dataset(tmp_path)
    config = PipelineConfig(
        sample_mfp_dir=tmp_path / "mfp",
        sample_apple_health_autoexport_csv=outputs["apple_health_autoexport"],
    )
    mfp = load_mfp_data(config.sample_mfp_dir, config)
    apple = AppleHealthAutoExportCsvConnector(config.sample_apple_health_autoexport_csv).load()
    models = build_daily_models(
        mfp_nutrition=mfp.daily_nutrition,
        mfp_micronutrients=mfp.daily_micronutrients,
        mfp_activity=mfp.daily_activity,
        mfp_body_metrics=mfp.daily_body_metrics,
        apple_activity=apple.daily_activity,
        apple_sleep=apple.daily_sleep,
        apple_body_metrics=apple.daily_body_metrics,
        apple_recovery=apple.daily_recovery,
        config=config,
    )

    fact = models.dashboard_fact
    assert len(fact) == 222
    assert fact["date"].min() == date(2025, 11, 27)
    assert fact["date"].max() == date(2026, 7, 6)
    assert fact["weight_measurement_flag"].sum() == 19
    assert fact["resting_hr_7d_avg"].notna().all()
    assert fact["hrv_7d_avg"].notna().all()
    assert fact["calories"].max() < 9999
    assert fact["protein_g"].max() < 999
