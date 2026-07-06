"""Apple Health XML export connector."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

try:
    from ..ingest_apple_health import AppleHealthData, load_apple_health_data
except ImportError:  # pragma: no cover - supports `python src/build_dataset.py`
    from ingest_apple_health import AppleHealthData, load_apple_health_data


@dataclass(frozen=True)
class AppleHealthExportConnector:
    """Load Apple Health XML exports from a local export.xml file."""

    export_xml: Path

    name: str = "apple_health_xml_export"
    source_type: str = "manual_export"

    def load(self) -> AppleHealthData:
        return load_apple_health_data(self.export_xml)

