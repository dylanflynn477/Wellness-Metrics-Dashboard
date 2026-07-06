# ETL Notes

## V1 Design

The v1 pipeline is local-first and export-driven. It reads files that the user manually places under `data/raw/`, builds daily aggregates, and writes dashboard-ready CSV files to `data/processed/`.

No web scraping, authenticated scraping, credential storage, browser automation, or live sync is included in v1.

## MyFitnessPal Parsing

The MFP parser scans CSV files in `data/raw/mfp/` and classifies them as nutrition, exercise, or progress exports based on file names and columns.

Nutrition columns are normalized to stable snake_case names. Common columns such as calories, protein, carbohydrates, fat, fiber, sugar, sodium, potassium, and cholesterol are mapped to dashboard fields. Additional numeric nutrient-like columns are preserved, which makes the parser resilient when MFP export schemas vary.

## Apple Health Parsing

The Apple Health parser streams `export.xml` with `xml.etree.ElementTree.iterparse`, which avoids loading the full XML tree into memory. It extracts supported daily metrics from `Record` and `Workout` elements.

Sleep hours are assigned to the calendar date of the sleep record start time. This is a practical first-pass convention for dashboarding and can be refined later if the report needs a different sleep-night model.

## Data Modeling

The transform layer builds a complete date spine between the first and last observed date, merges source-specific daily tables, and adds rolling averages and target deltas. This keeps the Power BI model simple: the primary grain is one row per calendar day.

## Future Adapter Boundary

Scraping, APIs, HealthKit bridges, or automated sync should be added as separate source adapters that output the same normalized daily tables. Keeping adapters separate from the core model protects the dashboard layer from upstream source changes.

