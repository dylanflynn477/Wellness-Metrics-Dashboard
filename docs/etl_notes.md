# ETL Notes

## V1 Design

The v1 pipeline is local-first and export-driven. It reads files that the user manually places under `data/raw/`, builds daily aggregates, and writes dashboard-ready CSV files or SQLite tables to `data/processed/`.

No web scraping, authenticated scraping, credential storage, browser automation, or live sync is included in v1.

## Configuration

Runtime settings are loaded in this order:

1. Defaults in `src/config.py`.
2. Local `.env` values copied from `.env.example`.
3. Process environment variables.
4. Existing command-line overrides such as `--mfp-dir`, `--apple-health-xml`, `--processed-dir`, and `--no-sample-fallback`.

The `.env` file is ignored by git. Use it for local export paths, target values, output mode, and the SQLite database URL.

## MyFitnessPal Parsing

The MFP parser scans CSV files in `data/raw/mfp/` and classifies them as nutrition, exercise, or progress exports based on file names and columns.

Nutrition columns are normalized to stable snake_case names. Common columns such as calories, protein, carbohydrates, fat, fiber, sugar, sodium, potassium, and cholesterol are mapped to dashboard fields. Additional numeric nutrient-like columns are preserved, which makes the parser resilient when MFP export schemas vary.

## Apple Health Parsing

The Apple Health parser streams `export.xml` with `xml.etree.ElementTree.iterparse`, which avoids loading the full XML tree into memory. It extracts supported daily metrics from `Record` and `Workout` elements.

Sleep hours are assigned to the calendar date of the sleep record start time. This is a practical first-pass convention for dashboarding and can be refined later if the report needs a different sleep-night model.

## Data Modeling

The transform layer builds a complete date spine between the first and last observed date, merges source-specific daily tables, and adds rolling averages and target deltas. This keeps the Power BI model simple: the primary grain is one row per calendar day.

## Output Modes

`OUTPUT_MODE=csv` preserves the original behavior and writes six CSV files:

- `daily_nutrition.csv`
- `daily_micronutrients.csv`
- `daily_activity.csv`
- `daily_sleep.csv`
- `daily_body_metrics.csv`
- `health_dashboard_fact.csv`

`OUTPUT_MODE=sqlite` writes the same modeled tables to the SQLite database configured by `DATABASE_URL`.

`OUTPUT_MODE=both` writes both CSV and SQLite outputs.

Power BI can load the generated CSV files directly. For SQLite, connect through an SQLite ODBC driver or approved SQLite connector and import the processed tables.

## Future Adapter Boundary

Scraping, APIs, HealthKit bridges, or automated sync should be added as separate source adapters that output the same normalized daily tables. Keeping adapters separate from the core model protects the dashboard layer from upstream source changes.

The current connector package wraps local exports only:

- MyFitnessPal manual CSV export connector.
- Apple Health XML export connector.

Future connector candidates include a MyFitnessPal official API connector if approved, a HealthKit/iOS bridge connector, third-party connectors, and manual CSV logs. Authenticated scraping, credential capture, and browser automation are out of scope for this milestone.

