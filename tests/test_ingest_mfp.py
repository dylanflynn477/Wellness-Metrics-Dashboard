from __future__ import annotations

from pathlib import Path

from src.config import PipelineConfig
from src.ingest_mfp import load_mfp_data


def test_mfp_nutrition_preserves_flexible_nutrient_columns(tmp_path: Path) -> None:
    mfp_dir = tmp_path / "mfp"
    mfp_dir.mkdir()
    (mfp_dir / "nutrition_export.csv").write_text(
        "\n".join(
            [
                "Entry Date,Meal Name,Food Name,Calories,Protein,Carbohydrates (g),Total Fat (g),Vitamin D (mcg),Magnesium (mg)",
                "2026-01-01,Breakfast,Oats,450,32,55,12,4.5,80",
                "2026-01-01,Dinner,Chicken bowl,800,62,88,18,3.0,110",
            ]
        ),
        encoding="utf-8",
    )

    result = load_mfp_data(mfp_dir, PipelineConfig())

    nutrition = result.daily_nutrition.set_index("date")
    micronutrients = result.daily_micronutrients.set_index("date")

    assert nutrition.loc[nutrition.index[0], "calories"] == 1250
    assert nutrition.loc[nutrition.index[0], "protein_g"] == 94
    assert "vitamin_d_mcg" in micronutrients.columns
    assert "magnesium_mg" in micronutrients.columns
    assert micronutrients.loc[micronutrients.index[0], "vitamin_d_mcg"] == 7.5


def test_mfp_progress_uses_configured_unit_for_unitless_weight(tmp_path: Path) -> None:
    mfp_dir = tmp_path / "mfp"
    mfp_dir.mkdir()
    (mfp_dir / "progress.csv").write_text(
        "\n".join(["Date,Weight", "2026-01-01,82"]),
        encoding="utf-8",
    )

    result = load_mfp_data(mfp_dir, PipelineConfig(bodyweight_unit_preference="kg"))

    assert round(result.daily_body_metrics.loc[0, "weight_lb"], 1) == 180.8

