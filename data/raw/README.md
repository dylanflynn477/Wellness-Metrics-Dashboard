# Raw Data

Place private exports here when running the ETL locally.

- `data/raw/mfp/`: MyFitnessPal nutrition, exercise, and progress CSV exports.
- `data/raw/apple_health/export.xml`: Apple Health XML export.

Raw files are ignored by git because they can contain sensitive personal health data. The public demo uses synthetic files from `data/sample/`.

Copy `.env.example` to `.env` if you want to point the pipeline at different local export paths.

