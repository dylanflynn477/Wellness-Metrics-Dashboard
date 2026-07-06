"""Lightweight connector interfaces for future data-source adapters.

Expected adapter types include manual MyFitnessPal exports, Apple Health XML
exports, an approved MyFitnessPal API connector, a future HealthKit/iOS bridge,
third-party connectors, and manual CSV logs. Authenticated scraping and browser
automation are intentionally outside this boundary.
"""

from __future__ import annotations

from typing import Generic, Protocol, TypeVar


T = TypeVar("T")


class DataConnector(Protocol, Generic[T]):
    """Small interface shared by export, API, bridge, and manual-log adapters."""

    name: str
    source_type: str

    def load(self) -> T:
        """Load source data into the normalized ingestion return type."""
        ...
