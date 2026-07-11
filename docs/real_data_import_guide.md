# Real Data Import Guide

This project is local-first and export-based. Real health exports stay on your machine, run through the ETL locally, and should not be committed to git.

## Where To Put MyFitnessPal Exports

Place exported MyFitnessPal CSV files in:

```text
data/raw/mfp/
```

The ETL can classify common nutrition, exercise, and progress or measurement exports. File names such as `nutrition.csv`, `food_diary.csv`, `exercise.csv`, and `progress.csv` are helpful but not required; the parser also looks at column names.

## Where To Put HealthAutoExport Data

For v1, use the extracted main HealthAutoExport daily CSV directly. Place it here:

```text
data/raw/apple_health/HealthAutoExport.csv
```

The full HealthAutoExport ZIP is not needed for v1. Extract the daily CSV locally and copy only that CSV into `data/raw/apple_health/`.

The optional Apple Health XML route is still available for later comparison or fallback:

```text
data/raw/apple_health/export.xml
```

Switch sources with:

```text
APPLE_HEALTH_SOURCE=autoexport_csv
APPLE_HEALTH_SOURCE=xml
APPLE_HEALTH_SOURCE=none
```

`autoexport_csv` is the default.

## Nutrition Source Of Truth

MyFitnessPal CSV exports are the source of truth for calories, macros, micronutrients, meal-level nutrition, and nutrition targets.

HealthAutoExport is the source of truth for Apple Health and Apple Watch metrics such as sleep, steps, active energy, resting energy, resting heart rate, HRV, VO2 max, exercise time, stand time, respiratory rate, and blood oxygen when available.

Do not use HealthAutoExport nutrition columns for the final nutrition outputs in v1. `USE_AUTOEXPORT_NUTRITION=false` is the default and recommended setting.

## Run The ETL

```bash
python src/build_dataset.py
```

By default, outputs are written to:

```text
data/processed/
```

The normal build writes dashboard-ready tables and, when `RUN_DATA_VALIDATION=true`, a data quality report.

## Run With Sample Data

Use the synthetic public-safe sample data when you want to test the pipeline without real exports:

```bash
python src/build_dataset.py --sample
```

To recreate the full 222-day fictional sample first:

```bash
python src/generate_synthetic_data.py
python src/build_dataset.py --sample
```

The generated sample covers `2025-11-27` through `2026-07-06` and intentionally includes changing nutrition phases, sparse weight measurements, daily wearable metrics, and correlated recovery signals. It is independently simulated rather than anonymized row-by-row from a private export.

The default config also falls back to sample data when no real raw files exist and `USE_SAMPLE_DATA_IF_RAW_MISSING=true`.

## Run With Real Data Only

To require real files and avoid sample fallback:

```bash
python src/build_dataset.py --no-sample-fallback
```

If the raw folders are empty, the ETL will produce empty or limited outputs instead of silently using sample data.

## Data Quality Report

After a validated run, inspect:

```text
data/processed/data_quality_report.md
data/processed/data_quality_issues.csv
```

The report checks for missing dates, duplicate dates, missing core fields, all-null columns, suspicious values, missing target deltas, and detected micronutrients. The CSV file is useful for filtering and tracking issues over time.

Common interpretation:

- `error` means the output may break dashboard assumptions or hide important data.
- `warning` means the value may be valid but deserves review.
- `micronutrients_not_detected` often means the MFP export did not include micronutrient columns, or the column names need review.

## Files That Should Never Be Committed

Do not commit:

- Real files under `data/raw/`
- Generated files under `data/processed/`
- `.env`
- SQLite databases such as `health_metrics.db`
- Power BI files or screenshots that expose private health data
- Power BI `.pbi/cache.abf` files or `.pbi/localSettings.json`

The `.gitignore` is configured to keep raw exports, processed outputs, local databases, `.env`, and PBIP local caches out of git. Commit PBIP report and semantic-model definitions only after checking that source paths and parameters do not reveal private locations.

## Troubleshooting Weird Exports

If columns are missing or values look strange:

- Open the source CSV and confirm it has a date-like column.
- Check whether nutrient names include units in unexpected formats.
- For HealthAutoExport, confirm the extracted daily CSV has columns like `Step Count (count)`, `Active Energy (kcal)`, `Resting Heart Rate (count/min)`, or `Sleep Analysis [Total] (hr)`.
- If `Sleep Analysis [Asleep] (hr)` is zero, check whether `Core`, `Deep`, and `REM` stage columns are populated. The parser uses total sleep first, then stage totals.
- Confirm decimal and thousands separators are standard, such as `1,250` or `1250.5`.
- Run with sample data to confirm the pipeline itself is working.
- Inspect `data_quality_issues.csv` for missing fields or all-null columns.
- If a MyFitnessPal export uses a new naming pattern, add a synonym in `src/ingest_mfp.py` rather than hard-coding a one-off transformation.
- If a HealthAutoExport column uses a new naming pattern, add a mapping in `src/connectors/apple_health_autoexport_csv.py`.

Keep future API, scraping, or live-sync work separate from this import flow. The v1 contract is exported files in, modeled dashboard tables out.
