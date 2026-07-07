# Raw Data

Place private exports here when running the ETL locally.

- `data/raw/mfp/`: MyFitnessPal nutrition, exercise, and progress CSV exports.
- `data/raw/apple_health/HealthAutoExport.csv`: Extracted main HealthAutoExport daily CSV for Apple Health and Apple Watch metrics.
- `data/raw/apple_health/export.xml`: Optional Apple Health XML export if `APPLE_HEALTH_SOURCE=xml`.

Raw files are ignored by git because they can contain sensitive personal health data. The public demo uses synthetic files from `data/sample/`.

Copy `.env.example` to `.env` if you want to point the pipeline at different local export paths.

