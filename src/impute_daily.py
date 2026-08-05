"""Conservative, auditable imputation for the dashboard fact table."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

try:
    from .config import PipelineConfig
    from .transform_daily import IMPUTATION_FLAG_FIELDS, order_fact_columns, refresh_fact_calculations
except ImportError:  # pragma: no cover - supports direct script execution imports
    from config import PipelineConfig
    from transform_daily import IMPUTATION_FLAG_FIELDS, order_fact_columns, refresh_fact_calculations


REPORT_COLUMNS = [
    "date",
    "field",
    "observed_value",
    "imputed_value",
    "reason",
    "method",
    "local_median",
    "robust_z",
    "window_days",
]

LINKED_NUTRITION_FIELDS = ["protein_g", "carbs_g", "fat_g"]


@dataclass(frozen=True)
class ImputationOptions:
    """Runtime controls for robust local imputation."""

    window_days: int = 21
    min_periods: int = 7
    max_gap_days: int = 3
    robust_z_threshold: float = 4.0

    def __post_init__(self) -> None:
        if self.window_days < 7 or self.window_days % 2 == 0:
            raise ValueError("Imputation window must be an odd number of at least 7 days.")
        if self.min_periods < 3 or self.min_periods > self.window_days:
            raise ValueError("Imputation minimum periods must be between 3 and the window size.")
        if self.max_gap_days < 0:
            raise ValueError("Imputation maximum gap days cannot be negative.")
        if self.robust_z_threshold <= 0:
            raise ValueError("Imputation robust z threshold must be positive.")


@dataclass(frozen=True)
class MetricRule:
    field: str
    hard_min: float | None
    hard_max: float | None
    detect_local_outliers: bool
    relative_deviation: float
    absolute_deviation: float
    minimum_scale: float
    fill_short_gaps: bool
    round_digits: int


@dataclass(frozen=True)
class ImputationResult:
    dashboard_fact: pd.DataFrame
    report: pd.DataFrame

    @property
    def changed_values(self) -> int:
        return len(self.report)

    @property
    def changed_days(self) -> int:
        return self.report["date"].nunique() if not self.report.empty else 0

    @property
    def field_counts(self) -> dict[str, int]:
        if self.report.empty:
            return {}
        return self.report["field"].value_counts().sort_index().to_dict()


DEFAULT_RULES = [
    MetricRule("calories", 500, 7000, True, 0.45, 1000, 50, True, 1),
    MetricRule("sleep_hours", 2, 14, True, 0.35, 3, 0.1, True, 2),
    MetricRule("steps", 0, 50000, False, 0, 0, 250, False, 0),
    MetricRule("resting_hr", 35, 120, False, 0, 0, 1, False, 1),
    MetricRule("hrv_ms", 5, 250, False, 0, 0, 2, False, 1),
]


def impute_dashboard_fact(
    fact: pd.DataFrame,
    pipeline_config: PipelineConfig,
    options: ImputationOptions | None = None,
) -> ImputationResult:
    """Replace only high-confidence anomalies and return a cell-level audit report."""

    options = options or ImputationOptions()
    output = fact.copy().sort_values("date").reset_index(drop=True)
    report_rows: list[dict[str, object]] = []
    imputed_masks: dict[str, pd.Series] = {}

    for rule in DEFAULT_RULES:
        changed = apply_metric_rule(output, rule, options, report_rows)
        imputed_masks[rule.field] = changed

        if rule.field == "calories" and changed.any():
            for field in LINKED_NUTRITION_FIELDS:
                linked_changed = impute_linked_field(output, field, changed, options, report_rows)
                imputed_masks[field] = linked_changed

    for field in IMPUTATION_FLAG_FIELDS:
        imputed_masks.setdefault(field, pd.Series(False, index=output.index))

    add_imputation_markers(output, imputed_masks)
    output = refresh_fact_calculations(output, pipeline_config)
    output = order_fact_columns(output)
    report = pd.DataFrame(report_rows, columns=REPORT_COLUMNS)
    if not report.empty:
        report = report.sort_values(["date", "field"]).reset_index(drop=True)
    return ImputationResult(dashboard_fact=output, report=report)


def apply_metric_rule(
    frame: pd.DataFrame,
    rule: MetricRule,
    options: ImputationOptions,
    report_rows: list[dict[str, object]],
) -> pd.Series:
    changed = pd.Series(False, index=frame.index)
    if rule.field not in frame:
        return changed

    values = pd.to_numeric(frame[rule.field], errors="coerce")
    local_median, robust_z = rolling_context(values, rule, options)
    reasons = pd.Series(pd.NA, index=frame.index, dtype="object")

    if rule.fill_short_gaps and options.max_gap_days > 0:
        missing = values.isna()
        gap_groups = missing.ne(missing.shift()).cumsum()
        gap_sizes = missing.groupby(gap_groups).transform("sum")
        reasons.loc[missing & gap_sizes.le(options.max_gap_days)] = "missing_short_gap"

    observed = values.notna()
    if rule.hard_min is not None:
        reasons.loc[observed & values.lt(rule.hard_min)] = "below_hard_minimum"
    if rule.hard_max is not None:
        reasons.loc[observed & values.gt(rule.hard_max)] = "above_hard_maximum"

    if rule.detect_local_outliers:
        absolute_difference = values.sub(local_median).abs()
        relative_difference = absolute_difference.div(local_median.abs().replace(0, pd.NA))
        local_outlier = (
            observed
            & robust_z.ge(options.robust_z_threshold)
            & relative_difference.ge(rule.relative_deviation)
            & absolute_difference.ge(rule.absolute_deviation)
        )
        reasons.loc[local_outlier & reasons.isna()] = "robust_local_outlier"

    candidates = reasons.notna() & local_median.notna()
    replacements = local_median.round(rule.round_digits)
    for index in frame.index[candidates]:
        report_rows.append(
            audit_row(
                frame=frame,
                index=index,
                field=rule.field,
                observed_value=values.loc[index],
                imputed_value=replacements.loc[index],
                reason=str(reasons.loc[index]),
                local_median=local_median.loc[index],
                robust_z=robust_z.loc[index],
                window_days=options.window_days,
            )
        )

    frame.loc[candidates, rule.field] = replacements.loc[candidates]
    changed.loc[candidates] = True
    return changed


def impute_linked_field(
    frame: pd.DataFrame,
    field: str,
    calorie_days: pd.Series,
    options: ImputationOptions,
    report_rows: list[dict[str, object]],
) -> pd.Series:
    changed = pd.Series(False, index=frame.index)
    if field not in frame:
        return changed

    values = pd.to_numeric(frame[field], errors="coerce")
    local_median = values.rolling(
        options.window_days,
        center=True,
        min_periods=options.min_periods,
    ).median()
    candidates = calorie_days & local_median.notna()
    replacements = local_median.round(1)

    for index in frame.index[candidates]:
        report_rows.append(
            audit_row(
                frame=frame,
                index=index,
                field=field,
                observed_value=values.loc[index],
                imputed_value=replacements.loc[index],
                reason="calorie_day_adjustment",
                local_median=local_median.loc[index],
                robust_z=pd.NA,
                window_days=options.window_days,
            )
        )

    frame.loc[candidates, field] = replacements.loc[candidates]
    changed.loc[candidates] = True
    return changed


def rolling_context(
    values: pd.Series,
    rule: MetricRule,
    options: ImputationOptions,
) -> tuple[pd.Series, pd.Series]:
    rolling = values.rolling(options.window_days, center=True, min_periods=options.min_periods)
    local_median = rolling.median()
    local_mad = rolling.apply(median_absolute_deviation, raw=False)
    robust_scale = local_mad.mul(1.4826).clip(lower=rule.minimum_scale)
    robust_z = values.sub(local_median).abs().div(robust_scale)
    return local_median, robust_z


def median_absolute_deviation(values: pd.Series) -> float:
    clean = values.dropna()
    if clean.empty:
        return float("nan")
    median = clean.median()
    return float(clean.sub(median).abs().median())


def add_imputation_markers(frame: pd.DataFrame, imputed_masks: dict[str, pd.Series]) -> None:
    tracked_fields = sorted(imputed_masks)
    for field in tracked_fields:
        frame[f"{field}_imputed_flag"] = imputed_masks[field].astype("int8")

    flag_columns = [f"{field}_imputed_flag" for field in tracked_fields]
    if flag_columns:
        frame["imputation_count"] = frame[flag_columns].sum(axis=1).astype("int16")
        frame["has_imputed_values"] = frame["imputation_count"].gt(0).astype("int8")
        frame["imputed_fields"] = [
            ";".join(field for field in tracked_fields if bool(imputed_masks[field].loc[index]))
            for index in frame.index
        ]


def audit_row(
    frame: pd.DataFrame,
    index: int,
    field: str,
    observed_value: object,
    imputed_value: object,
    reason: str,
    local_median: object,
    robust_z: object,
    window_days: int,
) -> dict[str, object]:
    return {
        "date": frame.at[index, "date"],
        "field": field,
        "observed_value": observed_value,
        "imputed_value": imputed_value,
        "reason": reason,
        "method": "centered_rolling_median_mad",
        "local_median": local_median,
        "robust_z": robust_z,
        "window_days": window_days,
    }
