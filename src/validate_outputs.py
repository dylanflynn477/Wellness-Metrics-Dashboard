"""Data quality checks for processed wellness dashboard outputs."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sqlite3
from typing import Any

import pandas as pd

try:
    from .config import PipelineConfig
    from .utils import ensure_directories
except ImportError:  # pragma: no cover - supports direct script execution imports
    from config import PipelineConfig
    from utils import ensure_directories


OUTPUT_FILES = {
    "daily_nutrition": "daily_nutrition.csv",
    "daily_micronutrients": "daily_micronutrients.csv",
    "daily_activity": "daily_activity.csv",
    "daily_sleep": "daily_sleep.csv",
    "daily_body_metrics": "daily_body_metrics.csv",
    "dashboard_fact": "health_dashboard_fact.csv",
}

SQLITE_TABLES = {
    "daily_nutrition": "daily_nutrition",
    "daily_micronutrients": "daily_micronutrients",
    "daily_activity": "daily_activity",
    "daily_sleep": "daily_sleep",
    "daily_body_metrics": "daily_body_metrics",
    "dashboard_fact": "health_dashboard_fact",
}

ISSUE_COLUMNS = ["severity", "table", "check", "column", "date", "value", "message"]

CORE_FACT_FIELDS = [
    "date",
    "calories",
    "protein_g",
    "carbs_g",
    "fat_g",
    "fiber_g",
    "sugar_g",
    "sodium_mg",
    "potassium_mg",
    "cholesterol_mg",
    "weight_lb",
    "steps",
    "active_energy_kcal",
    "basal_energy_kcal",
    "sleep_hours",
    "resting_hr",
    "hrv_ms",
    "workout_minutes",
]

NON_MICRONUTRIENT_FACT_FIELDS = set(
    CORE_FACT_FIELDS
    + [
        "saturated_fat_g",
        "trans_fat_g",
        "in_bed_hours",
        "calories_7d_avg",
        "protein_7d_avg",
        "weight_7d_avg",
        "sleep_7d_avg",
        "calorie_delta_from_target",
        "protein_delta_from_target",
    ]
)


@dataclass(frozen=True)
class ValidationSummary:
    """Summary of one processed-output validation run."""

    issue_count: int
    error_count: int
    warning_count: int
    micronutrient_count: int
    micronutrient_columns: list[str]
    report_path: Path
    issues_path: Path


def validate_processed_outputs(config: PipelineConfig, outputs: dict[str, Path] | None = None) -> ValidationSummary:
    """Inspect processed outputs and write markdown/CSV data quality reports."""

    ensure_directories([config.processed_dir])
    tables = load_processed_tables(config=config, outputs=outputs)
    micronutrient_columns = detect_micronutrients(tables)
    issues = run_validation_checks(tables=tables, config=config, micronutrient_columns=micronutrient_columns)

    issues_path = config.processed_dir / "data_quality_issues.csv"
    report_path = config.processed_dir / "data_quality_report.md"
    write_issues_csv(issues, issues_path)
    write_markdown_report(
        issues=issues,
        micronutrient_columns=micronutrient_columns,
        tables=tables,
        report_path=report_path,
        issues_path=issues_path,
    )

    error_count = sum(1 for issue in issues if issue["severity"] == "error")
    warning_count = sum(1 for issue in issues if issue["severity"] == "warning")
    return ValidationSummary(
        issue_count=len(issues),
        error_count=error_count,
        warning_count=warning_count,
        micronutrient_count=len(micronutrient_columns),
        micronutrient_columns=micronutrient_columns,
        report_path=report_path,
        issues_path=issues_path,
    )


def load_processed_tables(config: PipelineConfig, outputs: dict[str, Path] | None = None) -> dict[str, pd.DataFrame]:
    """Load the processed tables from CSV files, falling back to SQLite output."""

    output_paths = outputs or {}
    tables: dict[str, pd.DataFrame] = {}
    sqlite_path = output_paths.get("sqlite_database") or config.sqlite_database_path

    for key, filename in OUTPUT_FILES.items():
        csv_path = output_paths.get(key) or config.processed_dir / filename
        if csv_path.exists():
            tables[key] = pd.read_csv(csv_path)
        elif sqlite_path.exists():
            tables[key] = read_sqlite_table(sqlite_path, SQLITE_TABLES[key])
    return tables


def read_sqlite_table(database_path: Path, table_name: str) -> pd.DataFrame:
    with sqlite3.connect(database_path) as connection:
        return pd.read_sql_query(f"select * from {table_name}", connection)


def run_validation_checks(
    tables: dict[str, pd.DataFrame],
    config: PipelineConfig,
    micronutrient_columns: list[str],
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    fact = normalize_dates(tables.get("dashboard_fact", pd.DataFrame()))

    if fact.empty:
        add_issue(issues, "error", "dashboard_fact", "missing_table_or_rows", "date", None, None, "Dashboard fact table is missing or empty.")
    else:
        check_missing_dates(fact, issues)
        check_core_fields(fact, issues)
        check_metric_ranges(fact, issues)
        check_target_deltas(fact, config, issues)

    for table_name, frame in tables.items():
        normalized = normalize_dates(frame)
        check_duplicate_dates(table_name, normalized, issues)
        check_all_null_columns(table_name, normalized, issues)

    if not micronutrient_columns:
        add_issue(
            issues,
            "warning",
            "daily_micronutrients",
            "micronutrients_not_detected",
            None,
            None,
            None,
            "No micronutrient columns or long-form nutrient values were detected.",
        )

    return issues


def check_missing_dates(fact: pd.DataFrame, issues: list[dict[str, Any]]) -> None:
    dates = pd.to_datetime(fact["date"], errors="coerce").dropna()
    if dates.empty:
        add_issue(issues, "error", "dashboard_fact", "invalid_date_spine", "date", None, None, "Dashboard fact table has no parseable dates.")
        return

    actual = set(dates.dt.date)
    expected = pd.date_range(dates.min().date(), dates.max().date(), freq="D").date
    for missing_date in sorted(set(expected) - actual):
        add_issue(
            issues,
            "error",
            "dashboard_fact",
            "missing_date",
            "date",
            missing_date,
            None,
            f"Date {missing_date} is missing from the dashboard fact date spine.",
        )


def check_duplicate_dates(table_name: str, frame: pd.DataFrame, issues: list[dict[str, Any]]) -> None:
    if frame.empty or "date" not in frame:
        return

    subset = ["date", "nutrient"] if table_name == "daily_micronutrients" and "nutrient" in frame else ["date"]
    duplicates = frame[frame.duplicated(subset=subset, keep=False)]
    for _, row in duplicates.iterrows():
        column = ",".join(subset)
        value = row["nutrient"] if "nutrient" in subset else None
        message = f"Duplicate row for {column} in {table_name}."
        add_issue(issues, "error", table_name, "duplicate_date", column, row.get("date"), value, message)


def check_all_null_columns(table_name: str, frame: pd.DataFrame, issues: list[dict[str, Any]]) -> None:
    if frame.empty:
        return

    for column in frame.columns:
        if column == "date":
            continue
        series = frame[column].replace("", pd.NA)
        if series.isna().all():
            add_issue(
                issues,
                "warning",
                table_name,
                "all_null_column",
                column,
                None,
                None,
                f"Column {column} in {table_name} is present but entirely null.",
            )


def check_core_fields(fact: pd.DataFrame, issues: list[dict[str, Any]]) -> None:
    for field in CORE_FACT_FIELDS:
        if field not in fact.columns:
            add_issue(
                issues,
                "error",
                "dashboard_fact",
                "missing_core_field",
                field,
                None,
                None,
                f"Core field {field} is missing from health_dashboard_fact.",
            )


def check_metric_ranges(fact: pd.DataFrame, issues: list[dict[str, Any]]) -> None:
    checks = [
        ("calories", "negative_calories", lambda value: value < 0, "Calories should not be negative."),
        ("protein_g", "negative_macro", lambda value: value < 0, "Protein should not be negative."),
        ("carbs_g", "negative_macro", lambda value: value < 0, "Carbohydrates should not be negative."),
        ("fat_g", "negative_macro", lambda value: value < 0, "Fat should not be negative."),
        ("weight_lb", "suspicious_bodyweight", lambda value: value < 70 or value > 700, "Bodyweight is outside the expected 70-700 lb range."),
        ("sleep_hours", "suspicious_sleep", lambda value: value < 2 or value > 14, "Sleep hours are outside the expected 2-14 hour range."),
        ("steps", "suspicious_steps", lambda value: value > 50000, "Step count is above 50,000."),
        ("resting_hr", "suspicious_resting_hr", lambda value: value < 35 or value > 120, "Resting heart rate is outside the expected 35-120 bpm range."),
        ("hrv_ms", "suspicious_hrv", lambda value: value < 5 or value > 250, "HRV is outside the expected 5-250 ms range."),
    ]

    for column, check_name, predicate, message in checks:
        if column not in fact:
            continue
        values = pd.to_numeric(fact[column], errors="coerce")
        for index, value in values.dropna().items():
            if predicate(value):
                add_issue(
                    issues,
                    "warning",
                    "dashboard_fact",
                    check_name,
                    column,
                    fact.loc[index, "date"] if "date" in fact else None,
                    value,
                    message,
                )


def check_target_deltas(fact: pd.DataFrame, config: PipelineConfig, issues: list[dict[str, Any]]) -> None:
    target_checks = [
        (config.calorie_target, "calorie_delta_from_target", "CALORIE_TARGET"),
        (config.protein_target_g, "protein_delta_from_target", "PROTEIN_TARGET_G"),
    ]
    for target, column, env_name in target_checks:
        if target is None:
            continue
        if column not in fact.columns or fact[column].replace("", pd.NA).isna().all():
            add_issue(
                issues,
                "error",
                "dashboard_fact",
                "missing_target_delta",
                column,
                None,
                None,
                f"{column} is missing or all-null even though {env_name} is configured.",
            )


def detect_micronutrients(tables: dict[str, pd.DataFrame]) -> list[str]:
    nutrients: set[str] = set()
    micronutrients = tables.get("daily_micronutrients", pd.DataFrame())
    if "nutrient" in micronutrients and "value" in micronutrients:
        nutrients.update(str(value) for value in micronutrients["nutrient"].dropna().unique())
    else:
        nutrients.update(column for column in micronutrients.columns if column != "date")

    fact = tables.get("dashboard_fact", pd.DataFrame())
    nutrients.update(column for column in fact.columns if column not in NON_MICRONUTRIENT_FACT_FIELDS)
    return sorted(nutrients)


def normalize_dates(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty or "date" not in frame:
        return frame.copy()
    output = frame.copy()
    output["date"] = pd.to_datetime(output["date"], errors="coerce").dt.date
    return output


def add_issue(
    issues: list[dict[str, Any]],
    severity: str,
    table: str,
    check: str,
    column: str | None,
    date: object | None,
    value: object | None,
    message: str,
) -> None:
    issues.append(
        {
            "severity": severity,
            "table": table,
            "check": check,
            "column": column,
            "date": date,
            "value": value,
            "message": message,
        }
    )


def write_issues_csv(issues: list[dict[str, Any]], issues_path: Path) -> None:
    frame = pd.DataFrame(issues, columns=ISSUE_COLUMNS)
    frame.to_csv(issues_path, index=False)


def write_markdown_report(
    issues: list[dict[str, Any]],
    micronutrient_columns: list[str],
    tables: dict[str, pd.DataFrame],
    report_path: Path,
    issues_path: Path,
) -> None:
    error_count = sum(1 for issue in issues if issue["severity"] == "error")
    warning_count = sum(1 for issue in issues if issue["severity"] == "warning")
    lines = [
        "# Data Quality Report",
        "",
        "## Summary",
        "",
        f"- Tables inspected: {len(tables)}",
        f"- Total issues: {len(issues)}",
        f"- Error-level issues: {error_count}",
        f"- Warning-level issues: {warning_count}",
        f"- Micronutrient fields detected: {len(micronutrient_columns)}",
        f"- Issue detail CSV: `{issues_path.name}`",
        "",
        "## Table Rows",
        "",
    ]

    for table_name in sorted(tables):
        lines.append(f"- `{table_name}`: {len(tables[table_name])} rows")

    lines.extend(["", "## Micronutrients Detected", ""])
    if micronutrient_columns:
        lines.extend(f"- `{column}`" for column in micronutrient_columns)
    else:
        lines.append("- None detected")

    lines.extend(["", "## Issues", ""])
    if not issues:
        lines.append("No data quality issues detected.")
    else:
        lines.append("| Severity | Table | Check | Column | Date | Value | Message |")
        lines.append("|---|---|---|---|---|---|---|")
        for issue in issues:
            lines.append(
                "| {severity} | {table} | {check} | {column} | {date} | {value} | {message} |".format(
                    severity=markdown_cell(issue["severity"]),
                    table=markdown_cell(issue["table"]),
                    check=markdown_cell(issue["check"]),
                    column=markdown_cell(issue.get("column")),
                    date=markdown_cell(issue.get("date")),
                    value=markdown_cell(issue.get("value")),
                    message=markdown_cell(issue["message"]),
                )
            )

    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def markdown_cell(value: object | None) -> str:
    if value is None or pd.isna(value):
        return ""
    return str(value).replace("|", "\\|")

