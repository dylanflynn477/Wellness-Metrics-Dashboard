from __future__ import annotations

from pathlib import Path

import pytest

from src.config import PROJECT_ROOT, PipelineConfig


def test_config_uses_defaults_when_env_is_empty() -> None:
    config = PipelineConfig.from_env(env_file=None, environ={})

    assert config == PipelineConfig()


def test_config_loads_env_file_values(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "APP_ENV=test",
                "USE_SAMPLE_DATA_IF_RAW_MISSING=false",
                "RAW_MFP_DIR=custom/raw/mfp",
                "RAW_APPLE_HEALTH_XML=custom/raw/apple/export.xml",
                "PROCESSED_DIR=custom/processed",
                "CALORIE_TARGET=",
                "PROTEIN_TARGET_G=190",
                "BODYWEIGHT_UNIT_PREFERENCE=kg",
                "START_DATE=2026-01-01",
                "END_DATE=2026-01-31",
                "NUTRIENT_OUTPUT_MODE=long",
                "OUTPUT_MODE=both",
                "DATABASE_URL=sqlite:///custom/processed/test.db",
                "RUN_DATA_VALIDATION=false",
            ]
        ),
        encoding="utf-8",
    )

    config = PipelineConfig.from_env(env_file=env_file, environ={})

    assert config.app_env == "test"
    assert config.use_sample_data_if_raw_missing is False
    assert config.raw_mfp_dir == PROJECT_ROOT / "custom" / "raw" / "mfp"
    assert config.raw_apple_health_xml == PROJECT_ROOT / "custom" / "raw" / "apple" / "export.xml"
    assert config.processed_dir == PROJECT_ROOT / "custom" / "processed"
    assert config.calorie_target is None
    assert config.protein_target_g == 190
    assert config.bodyweight_unit_preference == "kg"
    assert config.start_date == "2026-01-01"
    assert config.end_date == "2026-01-31"
    assert config.nutrient_output_mode == "long"
    assert config.output_mode == "both"
    assert config.sqlite_database_path == PROJECT_ROOT / "custom" / "processed" / "test.db"
    assert config.run_data_validation is False


def test_config_loads_run_data_validation() -> None:
    config = PipelineConfig.from_env(env_file=None, environ={"RUN_DATA_VALIDATION": "true"})

    assert config.run_data_validation is True


def test_process_environment_overrides_env_file(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("OUTPUT_MODE=sqlite\n", encoding="utf-8")

    config = PipelineConfig.from_env(env_file=env_file, environ={"OUTPUT_MODE": "csv"})

    assert config.output_mode == "csv"


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("BODYWEIGHT_UNIT_PREFERENCE", "stone"),
        ("NUTRIENT_OUTPUT_MODE", "pivoted"),
        ("OUTPUT_MODE", "parquet"),
    ],
)
def test_invalid_enum_values_raise_clear_errors(name: str, value: str) -> None:
    with pytest.raises(ValueError, match=name):
        PipelineConfig.from_env(env_file=None, environ={name: value})

