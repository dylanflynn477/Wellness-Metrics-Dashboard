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

- Keep MyFitnessPal export-based unless the private/approval-based official API becomes available.
- Add a MyFitnessPal official API connector only if approved.
- Add a HealthKit/iOS bridge connector for Apple Health live sync.
- Add future third-party connectors that emit the same normalized daily tables.
- Add manual CSV log connectors for data not covered by MFP or Apple Health.
- Do not add authenticated scraping, credential storage, Selenium login flows, or site-restriction bypasses.

## Storage And App Options

- Optional Streamlit preview app for quick local review.
- Use CSV as the default local output.
- Use SQLite when a single local database file is easier for Power BI or downstream analysis.
- Evaluate DuckDB or Postgres only after the CSV and SQLite path is stable.

