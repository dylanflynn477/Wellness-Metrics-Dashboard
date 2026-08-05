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
- Sparse weight measurements shown as points, plus latest recorded weight
- Sleep trend with 7-day average
- Resting heart rate and HRV trends with 7-day averages
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

- Recorded weight as points; filter `weight_measurement_flag` to `1`
- Latest recorded weight card
- Optional 28-day change based only on recorded weigh-ins
- Calorie deficit or surplus trend
- Expected vs actual weight movement if enough assumptions are configured

Expected weight movement can be added later with a configurable maintenance calorie estimate. Keep this separate from the raw ETL outputs so assumptions are visible in the report layer. A likely bulk/cut/maintenance label should be described as an inference because intake targets, water shifts, and sparse weigh-ins can all change the result.

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

When the ETL is run with `--impute`, use `has_imputed_values` as a report filter or tooltip marker. Keep `imputation_count` and `imputed_fields` available in drill-through so estimated days remain visible and auditable rather than silently presented as observations.

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

Resting HR 7D Avg =
CALCULATE (
    AVERAGE ( health_dashboard_fact[resting_hr] ),
    DATESINPERIOD ( 'Date'[Date], MAX ( 'Date'[Date] ), -7, DAY )
)

HRV 7D Avg =
CALCULATE (
    AVERAGE ( health_dashboard_fact[hrv_ms] ),
    DATESINPERIOD ( 'Date'[Date], MAX ( 'Date'[Date] ), -7, DAY )
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

## Sparse Weight Measures

Do not use `SUM(weight_lb)`. The fact table intentionally leaves weight blank on days without a measurement.

```DAX
Latest Recorded Weight =
VAR LastWeightDate =
    MAXX (
        FILTER (
            ALLSELECTED ( health_dashboard_fact ),
            health_dashboard_fact[weight_measurement_flag] = 1
        ),
        health_dashboard_fact[date]
    )
RETURN
    CALCULATE (
        MAX ( health_dashboard_fact[weight_lb] ),
        health_dashboard_fact[date] = LastWeightDate
    )

Weight Change 28D =
VAR EndDate = MAX ( 'Date'[Date] )
VAR WindowDates =
    FILTER (
        ALL ( 'Date'[Date] ),
        'Date'[Date] >= EndDate - 27 && 'Date'[Date] <= EndDate
    )
VAR FirstWeightDate =
    MINX (
        FILTER ( WindowDates, CALCULATE ( COUNT ( health_dashboard_fact[weight_lb] ) ) > 0 ),
        'Date'[Date]
    )
VAR LastWeightDate =
    MAXX (
        FILTER ( WindowDates, CALCULATE ( COUNT ( health_dashboard_fact[weight_lb] ) ) > 0 ),
        'Date'[Date]
    )
VAR FirstWeight = CALCULATE ( MAX ( health_dashboard_fact[weight_lb] ), 'Date'[Date] = FirstWeightDate )
VAR LastWeight = CALCULATE ( MAX ( health_dashboard_fact[weight_lb] ), 'Date'[Date] = LastWeightDate )
RETURN
    IF ( FirstWeightDate = LastWeightDate, BLANK (), LastWeight - FirstWeight )
```

## KPI Benchmarks and Colors

Use personal baselines for resting HR and HRV rather than universal good/bad thresholds. Compare the current 7-day average with a 28-day baseline; a rising resting HR or falling HRV is a recovery signal, not a diagnosis.

```DAX
Resting HR 28D Avg =
CALCULATE (
    AVERAGE ( health_dashboard_fact[resting_hr] ),
    DATESINPERIOD ( 'Date'[Date], MAX ( 'Date'[Date] ), -28, DAY )
)

HRV 28D Avg =
CALCULATE (
    AVERAGE ( health_dashboard_fact[hrv_ms] ),
    DATESINPERIOD ( 'Date'[Date], MAX ( 'Date'[Date] ), -28, DAY )
)

Resting HR KPI Color =
VAR Delta = [Resting HR 7D Avg] - [Resting HR 28D Avg]
RETURN SWITCH ( TRUE (), ISBLANK ( Delta ), "#808080", Delta <= 0, "#2E7D32", Delta <= 3, "#F9A825", "#C62828" )

HRV KPI Color =
VAR Ratio = DIVIDE ( [HRV 7D Avg], [HRV 28D Avg] )
RETURN SWITCH ( TRUE (), ISBLANK ( Ratio ), "#808080", Ratio >= 1, "#2E7D32", Ratio >= 0.9, "#F9A825", "#C62828" )

Sleep KPI Color =
VAR Hours = [Sleep 7D Avg]
RETURN SWITCH ( TRUE (), ISBLANK ( Hours ), "#808080", Hours >= 7 && Hours <= 9, "#2E7D32", Hours >= 6 && Hours <= 10, "#F9A825", "#C62828" )
```

In a card visual, open **Format visual > Callout value > Color > fx**, choose **Format style: Field value**, and select the corresponding color measure.

## Likely Nutrition Phase

This label uses observed behavior, not a medically precise energy-balance model. The energy balance proxy subtracts Apple resting and active energy from MFP calorie intake. Wearable energy estimates and food logs both contain error, so confirm the result against the direction of recorded weight.

```DAX
Energy Balance Proxy 7D =
CALCULATE (
    AVERAGEX (
        health_dashboard_fact,
        health_dashboard_fact[calories]
            - health_dashboard_fact[resting_energy_kcal]
            - health_dashboard_fact[active_energy_kcal]
    ),
    DATESINPERIOD ( 'Date'[Date], MAX ( 'Date'[Date] ), -7, DAY )
)

Likely Nutrition Phase =
VAR WeightChange = [Weight Change 28D]
VAR EnergyBalance = [Energy Balance Proxy 7D]
RETURN
    SWITCH (
        TRUE (),
        ISBLANK ( WeightChange ) || ISBLANK ( EnergyBalance ), "Insufficient data",
        WeightChange <= -0.75 && EnergyBalance < -100, "Likely cut",
        WeightChange >= 0.75 && EnergyBalance > 100, "Likely bulk",
        ABS ( WeightChange ) < 0.75, "Likely maintenance",
        "Mixed / unclear"
    )
```

Use a card for the label and a tooltip that shows `Weight Change 28D`, `Calories 7D Avg`, and `Energy Balance Proxy 7D`. Keep the words **Likely** or **Inferred** visible.

## Recommended First-Page Layout

1. Keep the date slicer at the top right.
2. Use six KPI cards: average calories, protein adherence, latest weight, sleep 7D, resting HR 7D, and HRV 7D.
3. Replace the weight line chart with a line chart using `date` on the X-axis and `weight_lb` on the Y-axis. Turn markers on, turn the line stroke off or make it thin, and filter `weight_measurement_flag` to `1`.
4. Add a two-line recovery chart with `resting_hr_7d_avg` and `hrv_7d_avg`. Put HRV on the secondary Y-axis because the scales differ.
5. Keep calories and protein as daily values plus their 7-day averages; format the daily line lightly and the rolling line more strongly.
6. Add a likely nutrition phase card only after confirming the calorie target and recording at least two weights within the selected 28-day period.

## Build Notes

- Prefer importing CSVs first for simplicity.
- Use SQLite when you want a single local database file for multiple tables.
- Keep the Power BI file out of git if it contains private health data.
- Add screenshots only after sanitizing private values.
