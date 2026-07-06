"""Pipeline configuration for the wellness metrics ETL."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal


PROJECT_ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class PipelineConfig:
    """Runtime options used by the local ETL pipeline."""

    raw_mfp_dir: Path = PROJECT_ROOT / "data" / "raw" / "mfp"
    raw_apple_health_xml: Path = PROJECT_ROOT / "data" / "raw" / "apple_health" / "export.xml"
    sample_mfp_dir: Path = PROJECT_ROOT / "data" / "sample" / "mfp"
    sample_apple_health_xml: Path = PROJECT_ROOT / "data" / "sample" / "apple_health" / "export.xml"
    processed_dir: Path = PROJECT_ROOT / "data" / "processed"

    calorie_target: float | None = 2400.0
    protein_target_g: float | None = 175.0

    # Used for unitless MFP progress exports. The modeled output is normalized to weight_lb.
    bodyweight_unit_preference: Literal["lb", "kg"] = "lb"

    start_date: str | None = None
    end_date: str | None = None

    nutrient_output_mode: Literal["wide", "long"] = "wide"
    use_sample_data_if_raw_missing: bool = True


def default_config() -> PipelineConfig:
    """Return the default config used by ``python src/build_dataset.py``."""

    return PipelineConfig()

