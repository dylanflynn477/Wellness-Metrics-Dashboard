# Real Data Import Guide

This project is local-first and export-based. Real health exports stay on your machine, run through the ETL locally, and should not be committed to git.

## Where To Put MyFitnessPal Exports

Place exported MyFitnessPal CSV files in:

```text
data/raw/mfp/
```

The ETL can classify common nutrition, exercise, and progress or measurement exports. File names such as `nutrition.csv`, `food_diary.csv`, `exercise.csv`, and `progress.csv` are helpful but not required; the parser also looks at column names.

## Where To Put Apple Health Export

Place the Apple Health XML export here:

```text
data/raw/apple_health/export.xml
```

Apple Health exports are usually delivered as a zip. Unzip it locally and copy the `export.xml` file into the folder above.

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

The `.gitignore` is configured to keep raw exports, processed outputs, local databases, and `.env` out of git.

## Troubleshooting Weird Exports

If columns are missing or values look strange:

- Open the source CSV and confirm it has a date-like column.
- Check whether nutrient names include units in unexpected formats.
- Confirm decimal and thousands separators are standard, such as `1,250` or `1250.5`.
- Run with sample data to confirm the pipeline itself is working.
- Inspect `data_quality_issues.csv` for missing fields or all-null columns.
- If a MyFitnessPal export uses a new naming pattern, add a synonym in `src/ingest_mfp.py` rather than hard-coding a one-off transformation.

Keep future API, scraping, or live-sync work separate from this import flow. The v1 contract is exported files in, modeled dashboard tables out.

