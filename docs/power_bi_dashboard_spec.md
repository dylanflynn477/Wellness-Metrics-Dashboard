# Power BI Dashboard Spec

This spec describes the first Power BI layer for the processed wellness dataset. The goal is a clear daily-grain model that can evolve into automated insights later.

## Data Model

Use `health_dashboard_fact` as the main daily fact table. It should have one row per calendar date.

Suggested tables:

- `health_dashboard_fact`: main daily fact table from `data/processed/health_dashboard_fact.csv` or the SQLite table of the same name.
- `daily_micronutrients`: optional separate nutrient table when `NUTRIENT_OUTPUT_MODE=long`.
- `daily_recovery`: optional separate recovery table if you prefer not to use only the flattened fact fields.
- `Date`: a dedicated date table related one-to-many to `health_dashboard_fact[date]`.

Recommended relationships:

- `Date[Date]` to `health_dashboard_fact[date]`
- `Date[Date]` to `daily_micronutrients[date]` when using long nutrient output
- `Date[Date]` to `daily_recovery[date]` if using recovery as a separate table

## Page 1: Executive Health Overview

Purpose: fast read on adherence, trend direction, and recovery context.

Suggested visuals:

- Calories vs target card and trend
- Protein vs target card and trend
- Weight trend with 7-day average
- Sleep trend with 7-day average
- Steps trend
- Weekly adherence score

Suggested filters:

- Date range
- Week
- Month

## Page 2: Nutrition & Micronutrients

Purpose: show macro consistency and micronutrient gaps.

Suggested visuals:

- Macro breakdown by day or week
- Protein per day vs target
- Fiber, sodium, potassium, and cholesterol trends
- Micronutrient heatmap
- Nutrient gaps by week

If micronutrients are wide columns, use selected measures for the most important nutrients. If `NUTRIENT_OUTPUT_MODE=long`, use `daily_micronutrients[nutrient]` as the matrix or heatmap category.

## Page 3: Body Composition & Weight Trend

Purpose: connect nutrition consistency with bodyweight movement.

Suggested visuals:

- Daily weight
- 7-day rolling average weight
- Calorie deficit or surplus trend
- Expected vs actual weight movement if enough assumptions are configured

Expected weight movement can be added later with a configurable maintenance calorie estimate. Keep this separate from the raw ETL outputs so assumptions are visible in the report layer.

## Page 4: Sleep, Recovery, and Activity

Purpose: combine wearable context with lifestyle trend signals.

Suggested visuals:

- Sleep hours
- Resting heart rate
- HRV
- Respiratory rate
- Blood oxygen
- Steps
- Active energy
- Resting energy
- Workout minutes

Use conditional formatting for suspicious or low-quality values surfaced by the data quality report.

## Page 5: Correlation Explorer

Purpose: explore relationships without overstating causality.

Suggested scatterplots:

- Calories vs weight
- Sleep vs resting HR
- Sleep vs HRV
- Steps or activity vs sleep
- Sodium or carbs vs scale weight spikes

Use rolling averages or weekly aggregation where daily noise is too high.

## Basic DAX Measures

```DAX
Total Calories =
SUM ( health_dashboard_fact[calories] )

Average Calories =
AVERAGE ( health_dashboard_fact[calories] )

Calories 7D Avg =
AVERAGEX (
    DATESINPERIOD ( 'Date'[Date], MAX ( 'Date'[Date] ), -7, DAY ),
    CALCULATE ( AVERAGE ( health_dashboard_fact[calories] ) )
)

Protein 7D Avg =
AVERAGEX (
    DATESINPERIOD ( 'Date'[Date], MAX ( 'Date'[Date] ), -7, DAY ),
    CALCULATE ( AVERAGE ( health_dashboard_fact[protein_g] ) )
)

Weight 7D Avg =
AVERAGEX (
    DATESINPERIOD ( 'Date'[Date], MAX ( 'Date'[Date] ), -7, DAY ),
    CALCULATE ( AVERAGE ( health_dashboard_fact[weight_lb] ) )
)

Sleep 7D Avg =
AVERAGEX (
    DATESINPERIOD ( 'Date'[Date], MAX ( 'Date'[Date] ), -7, DAY ),
    CALCULATE ( AVERAGE ( health_dashboard_fact[sleep_hours] ) )
)

Calorie Delta From Target =
AVERAGE ( health_dashboard_fact[calorie_delta_from_target] )

Protein Delta From Target =
AVERAGE ( health_dashboard_fact[protein_delta_from_target] )

Protein Adherence % =
DIVIDE (
    AVERAGE ( health_dashboard_fact[protein_g] ),
    AVERAGE ( health_dashboard_fact[protein_g] ) - AVERAGE ( health_dashboard_fact[protein_delta_from_target] )
)

Weekly Adherence Score =
VAR CalorieHit =
    IF ( ABS ( [Calorie Delta From Target] ) <= 150, 1, 0 )
VAR ProteinHit =
    IF ( [Protein Adherence %] >= 0.9, 1, 0 )
VAR SleepHit =
    IF ( [Sleep 7D Avg] >= 7, 1, 0 )
RETURN
    DIVIDE ( CalorieHit + ProteinHit + SleepHit, 3 )
```

## Build Notes

- Prefer importing CSVs first for simplicity.
- Use SQLite when you want a single local database file for multiple tables.
- Keep the Power BI file out of git if it contains private health data.
- Add screenshots only after sanitizing private values.
