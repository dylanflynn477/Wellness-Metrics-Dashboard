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
- Dashboard-ready CSV outputs
- Future AI-generated insight layer
- Future Power BI dashboard

## Repository Layout

```text
data/
  raw/
    mfp/                 # Put private MyFitnessPal CSV exports here
    apple_health/        # Put private Apple Health export.xml here
  sample/                # Synthetic public-safe sample exports
  processed/             # Generated dashboard-ready CSVs
src/
  config.py
  ingest_mfp.py
  ingest_apple_health.py
  transform_daily.py
  build_dataset.py
  utils.py
docs/
  data_dictionary.md
  etl_notes.md
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

## Run The ETL

```bash
python src/build_dataset.py
```

If `data/raw/` is empty, the command automatically uses the synthetic sample data in `data/sample/` so the project is runnable immediately. To process real exports:

1. Add MyFitnessPal CSV exports to `data/raw/mfp/`.
2. Add Apple Health `export.xml` to `data/raw/apple_health/export.xml`.
3. Run `python src/build_dataset.py`.

Generated outputs are written to `data/processed/`:

- `daily_nutrition.csv`
- `daily_micronutrients.csv`
- `daily_activity.csv`
- `daily_sleep.csv`
- `daily_body_metrics.csv`
- `health_dashboard_fact.csv`

## Configuration

Edit `src/config.py` to change:

- Calorie target
- Protein target
- Bodyweight unit preference for unitless MFP progress files
- Date range filters
- Wide vs. long micronutrient output
- Sample-data fallback behavior

The default modeled output normalizes bodyweight to `weight_lb` because that is the field expected by the first Power BI-ready fact table.

## Data Sources

### MyFitnessPal

The MFP ingestion layer reads local CSV exports for nutrition, exercise, and progress or measurements. Nutrition parsing is flexible: columns are normalized, common names are mapped to stable dashboard fields, and additional numeric nutrient-like columns are preserved instead of being discarded.

### Apple Health

The Apple Health parser reads local `export.xml` files and aggregates daily values for steps, energy burned, body mass, sleep, resting heart rate, HRV, and workouts when available.

## V1 Scope

This project intentionally does not implement web scraping, authenticated scraping, or live API integrations in v1. Future scraping, API, HealthKit bridge, or sync behavior should be implemented as separate adapters so the core daily model remains stable and testable.

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
- Evaluate DuckDB or Postgres storage instead of CSV-only outputs

