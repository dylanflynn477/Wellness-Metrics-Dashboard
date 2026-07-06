"""MyFitnessPal manual-export connector."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

try:
    from ..config import PipelineConfig
    from ..ingest_mfp import MfpData, load_mfp_data
except ImportError:  # pragma: no cover - supports `python src/build_dataset.py`
    from config import PipelineConfig
    from ingest_mfp import MfpData, load_mfp_data


@dataclass(frozen=True)
class MfpExportConnector:
    """Load MyFitnessPal CSV exports without credentials or browser automation."""

    mfp_dir: Path
    config: PipelineConfig

    name: str = "myfitnesspal_manual_export"
    source_type: str = "manual_export"

    def load(self) -> MfpData:
        return load_mfp_data(self.mfp_dir, self.config)

