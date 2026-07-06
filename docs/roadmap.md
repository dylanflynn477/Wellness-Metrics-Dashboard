# Roadmap

## Next Build

- Build the Power BI dashboard using `health_dashboard_fact.csv`.
- Add dashboard screenshots to `dashboard/`.
- Add a lightweight exploratory notebook for QA checks.

## Insight Layer

- Generate weekly summaries from the modeled fact table.
- Flag trends in calories, protein, sleep, weight, steps, HRV, and resting heart rate.
- Keep AI-generated insights separate from the ETL so model output can be audited.

## Automation

- Add an automated refresh workflow for local exports.
- Add validation checks for missing dates, duplicate records, and unusual outliers.

## Optional Connectors

- Optional HealthKit bridge.
- Optional MyFitnessPal API integration if a stable and permitted API is available.
- Optional safe connector architecture so live adapters cannot break the daily model.

## Storage And App Options

- Optional Streamlit preview app for quick local review.
- Optional DuckDB or Postgres storage instead of CSV-only outputs.

