<img width="1320" height="742" alt="image" src="https://github.com/user-attachments/assets/957f9d61-ad42-4ccd-8efd-1fe407ac1e3e" />

<img width="1302" height="731" alt="image" src="https://github.com/user-attachments/assets/6f6e49a0-96ff-4e4f-964b-214b1eb737fc" />




# Wellness Metrics Dashboard

Wellness Metrics Dashboard is a portfolio-quality analytics engineering project for turning exported MyFitnessPal and Apple Health data into clean, dashboard-ready daily health tables.

The first version is deliberately local-first: no scraping, no credential handling, and no live sync. The emphasis is reliable ETL, clear data modeling, and outputs that can flow directly into Power BI.

## What It Builds

The pipeline combines nutrition, micronutrients, bodyweight, sleep, activity, workouts, and Apple Health metrics into one daily-grain fact table. Each row represents a calendar day, making the output easy to analyze in Power BI or another BI layer.

Key themes:

- Personal health analytics
- Nutrition and micronutrient tracking
- Wearable data integration
- ETL and data modeling
- Dashboard-ready CSV and optional SQLite outputs
- Future AI-generated insight layer
- Future Power BI dashboard

## Repository Layout

```text
data/
  raw/
    mfp/                 # Put private MyFitnessPal CSV exports here
    apple_health/        # Put private HealthAutoExport CSV or Apple Health XML here
  sample/                # Synthetic public-safe sample exports
  processed/             # Generated dashboard-ready CSVs
src/
  config.py
  connectors/
  ingest_mfp.py
  ingest_apple_health.py
  transform_daily.py
  impute_daily.py
  build_dataset.py
  generate_synthetic_data.py
  validate_outputs.py
  utils.py
docs/
  data_dictionary.md
  etl_notes.md
  power_bi_dashboard_spec.md
  real_data_import_guide.md
  roadmap.md
tests/
dashboard/               # Future Power BI file and screenshots
notebooks/               # Optional exploration
```

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

On macOS or Linux, activate with `source .venv/bin/activate`.

Copy the example environment file if you want local overrides:

```bash
copy .env.example .env
```

On macOS or Linux, use `cp .env.example .env`.

## Run The ETL

```bash
python src/build_dataset.py
```

If `data/raw/` is empty, the command automatically uses the synthetic sample data in `data/sample/` so the project is runnable immediately. To process real exports:

1. Add MyFitnessPal CSV exports to `data/raw/mfp/`.
2. Add the extracted HealthAutoExport daily CSV to `data/raw/apple_health/HealthAutoExport.csv`.
3. Run `python src/build_dataset.py`.

The tracked sample spans `2025-11-27` through `2026-07-06` and models a fictional build-maintain-cut scenario. Regenerate it deterministically at any time:

```bash
python src/generate_synthetic_data.py
python src/build_dataset.py --sample
```

The generator preserves useful export schemas, row density, missingness, and realistic cross-metric relationships. It does not copy private daily values, meal names, workout descriptions, or an exact bodyweight trajectory from the reference exports.

The Power BI project reads the processed fact through the `HealthDashboardCsvPath` parameter. In Power BI Desktop, use **Transform data > Manage parameters** to point it at your local `data/processed/health_dashboard_fact.csv` before refreshing.

For an opt-in, auditable cleanup of high-confidence anomalies and short missing gaps, run:

```bash
python src/build_dataset.py --no-sample-fallback --impute
```

Imputation uses a centered 21-day rolling median and median absolute deviation (MAD), which is less sensitive to extreme values than a mean and standard deviation. It preserves gradual changes such as bulk-to-cut transitions, leaves missing stretches longer than three days untouched, and writes every replacement to `imputation_report.csv`. Raw source exports and source-specific daily tables are never overwritten.

Advanced controls are available through `--impute-window-days`, `--impute-max-gap-days`, and `--impute-z-threshold`. Use an odd window of at least seven days. The defaults are intentionally conservative.

Generated outputs are written to `data/processed/`:

- `daily_nutrition.csv`
- `daily_micronutrients.csv`
- `daily_activity.csv`
- `daily_sleep.csv`
- `daily_recovery.csv`
- `daily_body_metrics.csv`
- `health_dashboard_fact.csv`
- `data_quality_report.md`
- `data_quality_issues.csv`
- `imputation_report.csv` when `--impute` is enabled

## Configuration

Defaults live in `src/config.py`, but local settings should go in `.env`. The `.env` file is ignored by git because it can point to private health exports or local database files.

Common settings:

- `USE_SAMPLE_DATA_IF_RAW_MISSING=true` keeps the repo runnable with synthetic sample data when `data/raw/` is empty.
- `RAW_MFP_DIR=data/raw/mfp` points to local MyFitnessPal CSV exports.
- `APPLE_HEALTH_SOURCE=autoexport_csv` uses the extracted HealthAutoExport daily CSV. Valid values are `autoexport_csv`, `xml`, and `none`.
- `RAW_APPLE_HEALTH_AUTOEXPORT_CSV=data/raw/apple_health/HealthAutoExport.csv` points to the extracted HealthAutoExport daily CSV.
- `RAW_APPLE_HEALTH_XML=data/raw/apple_health/export.xml` points to the optional Apple Health XML export route.
- `USE_AUTOEXPORT_NUTRITION=false` keeps MyFitnessPal as the nutrition source of truth. Enabling this is not recommended in v1.
- `PROCESSED_DIR=data/processed` controls generated output location.
- `CALORIE_TARGET` and `PROTEIN_TARGET_G` drive target deltas in the fact table. Leave either blank to omit that target.
- `BODYWEIGHT_UNIT_PREFERENCE=lb` is used only for unitless MFP progress exports.
- `START_DATE` and `END_DATE` optionally filter the modeled date spine.
- `NUTRIENT_OUTPUT_MODE=wide` can be changed to `long`.
- `OUTPUT_MODE=csv` can be changed to `sqlite` or `both`.
- `DATABASE_URL=sqlite:///data/processed/health_metrics.db` controls the SQLite output path.
- `RUN_DATA_VALIDATION=true` writes a data quality report after each build.

The default modeled output normalizes bodyweight to `weight_lb` because that is the field expected by the first Power BI-ready fact table.

The existing command-line overrides still work:

```bash
python src/build_dataset.py --mfp-dir data/raw/mfp --apple-health-xml data/raw/apple_health/export.xml --processed-dir data/processed
```

For the default HealthAutoExport route:

```bash
python src/build_dataset.py --mfp-dir data/raw/mfp --apple-health-autoexport-csv data/raw/apple_health/HealthAutoExport.csv --processed-dir data/processed
```

## Data Sources

### MyFitnessPal

The MFP ingestion layer reads local CSV exports for nutrition, exercise, and progress or measurements. Nutrition parsing is flexible: columns are normalized, common names are mapped to stable dashboard fields, and additional numeric nutrient-like columns are preserved instead of being discarded.

MyFitnessPal is the source of truth for calories, macros, micronutrients, meal-level nutrition, and nutrition targets. HealthAutoExport nutrition columns are ignored by default and should not be used for the final nutrition outputs in v1.

Authenticated scraping is intentionally not implemented. The official MyFitnessPal API is private and approval-based, so this project treats MyFitnessPal as export-based unless an approved API integration is available later. The project does not store MyFitnessPal credentials, automate login flows, or bypass site restrictions.

### Apple Health

The default Apple Health route reads the extracted HealthAutoExport daily CSV at `data/raw/apple_health/HealthAutoExport.csv`. It captures Apple Health and Apple Watch metrics such as sleep, steps, active energy, resting energy, exercise time, stand time, resting heart rate, HRV, VO2 max, respiratory rate, and blood oxygen when those columns are available.

The full Apple Health XML export remains available with `APPLE_HEALTH_SOURCE=xml`, but it is not required for v1. The full HealthAutoExport ZIP is also not required; place the extracted main daily CSV directly in `data/raw/apple_health/`.

Apple Health live sync is not a Python/Selenium problem in this project. A future live integration should come through a HealthKit/iOS companion app or bridge that exports normalized data into the same connector boundary.

## Output Modes

`OUTPUT_MODE=csv` keeps the original behavior and writes dashboard-ready CSV files to `data/processed/`.

`OUTPUT_MODE=sqlite` writes the processed tables to the SQLite database configured by `DATABASE_URL`.

`OUTPUT_MODE=both` writes both CSV files and SQLite tables.

SQLite tables:

- `daily_nutrition`
- `daily_micronutrients`
- `daily_activity`
- `daily_sleep`
- `daily_recovery`
- `daily_body_metrics`
- `health_dashboard_fact`

Power BI can connect to the CSV files with the folder/text connectors, or to the SQLite database through an SQLite ODBC driver or another approved SQLite connector. CSV remains the simplest default; SQLite is useful when you want one local database file with all processed tables.

## Data Quality

When `RUN_DATA_VALIDATION=true`, the build writes `data_quality_report.md` and `data_quality_issues.csv` to `data/processed/`. The report checks date continuity, duplicate daily rows, missing or all-null fields, suspicious health values, target deltas, and detected micronutrients.

For real exports, start with [docs/real_data_import_guide.md](docs/real_data_import_guide.md). For the report design layer, use [docs/power_bi_dashboard_spec.md](docs/power_bi_dashboard_spec.md).

## V1 Scope

This project intentionally does not implement web scraping, authenticated scraping, or live API integrations in v1. Future scraping, API, HealthKit bridge, or sync behavior should be implemented as separate adapters so the core daily model remains stable and testable.

## Connector Roadmap

The `src/connectors/` package is a lightweight adapter boundary around current local exports. Current connectors wrap:

- MyFitnessPal manual CSV exports
- HealthAutoExport daily CSV exports
- Optional Apple Health XML exports

Future connector candidates:

- MyFitnessPal official API connector, if approved
- Future HealthKit iOS bridge connector
- Future third-party connector
- Manual CSV logs

## Portfolio Positioning

This project is designed to show the practical data engineering behind a strong analytics dashboard: messy export ingestion, schema normalization, daily-grain modeling, target deltas, rolling averages, data documentation, and tests. The next layer is the Power BI report itself, followed by optional AI-generated weekly insights built on top of the modeled fact table.

## Tests

```bash
pytest
```

The test suite covers flexible nutrient parsing, Apple Health XML parsing, daily fact modeling, rolling averages, and target deltas.

## Roadmap

- Build the Power BI dashboard and add screenshots
- Add AI-generated weekly insights from the modeled fact table
- Add automated refresh
- Explore an optional HealthKit bridge
- Explore optional MyFitnessPal API integration if available
- Add a safe connector architecture for future adapters
- Add an optional Streamlit preview app
- Evaluate DuckDB or Postgres storage after CSV and SQLite outputs

