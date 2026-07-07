"""Pipeline configuration for the wellness metrics ETL."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Literal
from urllib.parse import unquote

try:
    from dotenv import dotenv_values
except ImportError:  # pragma: no cover - requirements.txt installs python-dotenv
    dotenv_values = None


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ENV_FILE = PROJECT_ROOT / ".env"

BodyweightUnit = Literal["lb", "kg"]
NutrientOutputMode = Literal["wide", "long"]
OutputMode = Literal["csv", "sqlite", "both"]
AppleHealthSource = Literal["autoexport_csv", "xml", "none"]

BODYWEIGHT_UNIT_VALUES = {"lb", "kg"}
NUTRIENT_OUTPUT_MODE_VALUES = {"wide", "long"}
OUTPUT_MODE_VALUES = {"csv", "sqlite", "both"}
APPLE_HEALTH_SOURCE_VALUES = {"autoexport_csv", "xml", "none"}

TRUE_VALUES = {"1", "true", "t", "yes", "y", "on"}
FALSE_VALUES = {"0", "false", "f", "no", "n", "off"}


@dataclass(frozen=True)
class PipelineConfig:
    """Runtime options used by the local ETL pipeline."""

    app_env: str = "development"

    raw_mfp_dir: Path = PROJECT_ROOT / "data" / "raw" / "mfp"
    raw_apple_health_autoexport_csv: Path = PROJECT_ROOT / "data" / "raw" / "apple_health" / "HealthAutoExport.csv"
    raw_apple_health_xml: Path = PROJECT_ROOT / "data" / "raw" / "apple_health" / "export.xml"
    sample_mfp_dir: Path = PROJECT_ROOT / "data" / "sample" / "mfp"
    sample_apple_health_autoexport_csv: Path = PROJECT_ROOT / "data" / "sample" / "apple_health" / "HealthAutoExport.csv"
    sample_apple_health_xml: Path = PROJECT_ROOT / "data" / "sample" / "apple_health" / "export.xml"
    processed_dir: Path = PROJECT_ROOT / "data" / "processed"

    calorie_target: float | None = 2400.0
    protein_target_g: float | None = 175.0

    # Used for unitless MFP progress exports. The modeled output is normalized to weight_lb.
    bodyweight_unit_preference: BodyweightUnit = "lb"

    start_date: str | None = None
    end_date: str | None = None

    nutrient_output_mode: NutrientOutputMode = "wide"
    output_mode: OutputMode = "csv"
    database_url: str = "sqlite:///data/processed/health_metrics.db"
    run_data_validation: bool = True
    apple_health_source: AppleHealthSource = "autoexport_csv"
    use_autoexport_nutrition: bool = False
    use_sample_data_if_raw_missing: bool = True

    @classmethod
    def from_env(
        cls,
        env_file: Path | str | None = DEFAULT_ENV_FILE,
        environ: Mapping[str, str] | None = None,
    ) -> "PipelineConfig":
        """Build config from defaults, optional .env values, and environment variables."""

        defaults = cls()
        values = read_environment(env_file=env_file, environ=environ)
        return cls(
            app_env=env_string(values, "APP_ENV", defaults.app_env),
            raw_mfp_dir=env_path(values, "RAW_MFP_DIR", defaults.raw_mfp_dir),
            raw_apple_health_autoexport_csv=env_path(
                values,
                "RAW_APPLE_HEALTH_AUTOEXPORT_CSV",
                defaults.raw_apple_health_autoexport_csv,
            ),
            raw_apple_health_xml=env_path(values, "RAW_APPLE_HEALTH_XML", defaults.raw_apple_health_xml),
            sample_mfp_dir=defaults.sample_mfp_dir,
            sample_apple_health_autoexport_csv=defaults.sample_apple_health_autoexport_csv,
            sample_apple_health_xml=defaults.sample_apple_health_xml,
            processed_dir=env_path(values, "PROCESSED_DIR", defaults.processed_dir),
            calorie_target=parse_optional_float(values.get("CALORIE_TARGET"), defaults.calorie_target, "CALORIE_TARGET"),
            protein_target_g=parse_optional_float(values.get("PROTEIN_TARGET_G"), defaults.protein_target_g, "PROTEIN_TARGET_G"),
            bodyweight_unit_preference=validate_enum(
                values.get("BODYWEIGHT_UNIT_PREFERENCE"),
                defaults.bodyweight_unit_preference,
                BODYWEIGHT_UNIT_VALUES,
                "BODYWEIGHT_UNIT_PREFERENCE",
            ),
            start_date=parse_optional_string(values.get("START_DATE"), defaults.start_date),
            end_date=parse_optional_string(values.get("END_DATE"), defaults.end_date),
            nutrient_output_mode=validate_enum(
                values.get("NUTRIENT_OUTPUT_MODE"),
                defaults.nutrient_output_mode,
                NUTRIENT_OUTPUT_MODE_VALUES,
                "NUTRIENT_OUTPUT_MODE",
            ),
            output_mode=validate_enum(values.get("OUTPUT_MODE"), defaults.output_mode, OUTPUT_MODE_VALUES, "OUTPUT_MODE"),
            database_url=env_string(values, "DATABASE_URL", defaults.database_url),
            run_data_validation=parse_bool(
                values.get("RUN_DATA_VALIDATION"),
                defaults.run_data_validation,
                "RUN_DATA_VALIDATION",
            ),
            apple_health_source=validate_enum(
                values.get("APPLE_HEALTH_SOURCE"),
                defaults.apple_health_source,
                APPLE_HEALTH_SOURCE_VALUES,
                "APPLE_HEALTH_SOURCE",
            ),
            use_autoexport_nutrition=parse_bool(
                values.get("USE_AUTOEXPORT_NUTRITION"),
                defaults.use_autoexport_nutrition,
                "USE_AUTOEXPORT_NUTRITION",
            ),
            use_sample_data_if_raw_missing=parse_bool(
                values.get("USE_SAMPLE_DATA_IF_RAW_MISSING"),
                defaults.use_sample_data_if_raw_missing,
                "USE_SAMPLE_DATA_IF_RAW_MISSING",
            ),
        )

    @property
    def sqlite_database_path(self) -> Path:
        """Return the local SQLite file path from DATABASE_URL."""

        return sqlite_path_from_database_url(self.database_url)


def read_environment(env_file: Path | str | None, environ: Mapping[str, str] | None = None) -> dict[str, str]:
    """Read .env values first, then overlay process environment values."""

    values: dict[str, str] = {}
    if env_file is not None:
        path = Path(env_file)
        if path.exists():
            if dotenv_values is not None:
                values.update({key: value for key, value in dotenv_values(path).items() if value is not None})
            else:
                values.update(read_simple_env_file(path))

    source = os.environ if environ is None else environ
    values.update({key: str(value) for key, value in source.items() if value is not None})
    return values


def read_simple_env_file(path: Path) -> dict[str, str]:
    """Parse simple KEY=value lines when python-dotenv is not installed yet."""

    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        if key:
            values[key] = value
    return values


def env_string(values: Mapping[str, str], name: str, default: str) -> str:
    value = values.get(name)
    if value is None or str(value).strip() == "":
        return default
    return str(value).strip()


def env_path(values: Mapping[str, str], name: str, default: Path) -> Path:
    value = values.get(name)
    if value is None or str(value).strip() == "":
        return default
    return resolve_project_path(value)


def parse_bool(value: object | None, default: bool, name: str = "value") -> bool:
    if value is None or str(value).strip() == "":
        return default
    normalized = str(value).strip().lower()
    if normalized in TRUE_VALUES:
        return True
    if normalized in FALSE_VALUES:
        return False
    raise ValueError(f"{name} must be a boolean value such as true/false, yes/no, or 1/0.")


def parse_optional_float(value: object | None, default: float | None, name: str = "value") -> float | None:
    if value is None:
        return default
    text = str(value).strip()
    if text == "":
        return None
    try:
        return float(text)
    except ValueError as exc:
        raise ValueError(f"{name} must be blank or a numeric value.") from exc


def parse_optional_string(value: object | None, default: str | None = None) -> str | None:
    if value is None:
        return default
    text = str(value).strip()
    return text or None


def resolve_project_path(value: Path | str) -> Path:
    path = Path(value).expanduser()
    if path.is_absolute():
        return path
    return (PROJECT_ROOT / path).resolve()


def validate_enum(value: object | None, default: str, allowed: set[str], name: str) -> str:
    if value is None or str(value).strip() == "":
        return default
    normalized = str(value).strip().lower()
    if normalized not in allowed:
        allowed_text = ", ".join(sorted(allowed))
        raise ValueError(f"{name} must be one of: {allowed_text}.")
    return normalized


def sqlite_path_from_database_url(database_url: str) -> Path:
    """Resolve sqlite:/// URLs to a project-relative database file path."""

    prefix = "sqlite:///"
    if not database_url.startswith(prefix):
        raise ValueError("DATABASE_URL must use sqlite:/// for local SQLite output.")

    raw_path = unquote(database_url[len(prefix) :]).strip()
    if raw_path in {"", ":memory:"}:
        raise ValueError("DATABASE_URL must point to a SQLite database file.")
    return resolve_project_path(raw_path)


def default_config() -> PipelineConfig:
    """Return the config used by ``python src/build_dataset.py``."""

    return PipelineConfig.from_env()

