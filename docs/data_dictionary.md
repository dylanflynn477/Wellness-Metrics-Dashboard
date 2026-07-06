# Data Dictionary

This dictionary describes the generated CSV outputs in `data/processed/`.

## daily_nutrition.csv

Daily nutrition values aggregated from MyFitnessPal nutrition exports.

| Field | Description |
|---|---|
| date | Calendar date. |
| calories | Total logged food calories. |
| protein_g | Total protein in grams. |
| carbs_g | Total carbohydrates in grams. |
| fat_g | Total fat in grams. |
| saturated_fat_g | Saturated fat in grams, when exported. |
| trans_fat_g | Trans fat in grams, when exported. |
| cholesterol_mg | Cholesterol in milligrams, when exported. |
| sodium_mg | Sodium in milligrams, when exported. |
| potassium_mg | Potassium in milligrams, when exported. |
| fiber_g | Fiber in grams, when exported. |
| sugar_g | Sugar in grams, when exported. |

## daily_micronutrients.csv

Daily micronutrients aggregated from MyFitnessPal nutrition exports. In the default wide mode, each nutrient is a separate column. If `nutrient_output_mode` is set to `long`, the output uses:

| Field | Description |
|---|---|
| date | Calendar date. |
| nutrient | Normalized nutrient name. |
| value | Daily aggregated value. |

Example wide fields include `vitamin_a_mcg`, `vitamin_c_mg`, `calcium_mg`, `iron_mg`, `magnesium_mg`, and `zinc_mg`. Actual fields depend on the source export.

## daily_activity.csv

Daily activity values from Apple Health, with MFP exercise minutes used as a fallback where Apple workout minutes are unavailable.

| Field | Description |
|---|---|
| date | Calendar date. |
| steps | Daily step count. |
| active_energy_kcal | Active energy burned in kcal. |
| basal_energy_kcal | Basal energy burned in kcal. |
| workout_minutes | Workout or exercise minutes. |

## daily_sleep.csv

Daily sleep values from Apple Health sleep analysis records.

| Field | Description |
|---|---|
| date | Calendar date assigned from the sleep record start time. |
| sleep_hours | Hours categorized as asleep. Falls back to in-bed hours if asleep stages are unavailable. |
| in_bed_hours | Hours categorized as in bed. |

## daily_body_metrics.csv

Daily body and recovery metrics from Apple Health, with MFP progress weight used as a fallback where Apple body mass is unavailable.

| Field | Description |
|---|---|
| date | Calendar date. |
| weight_lb | Bodyweight normalized to pounds. |
| resting_hr | Resting heart rate in beats per minute. |
| hrv_ms | Heart rate variability SDNN in milliseconds. |

## health_dashboard_fact.csv

Main daily-grain fact table for Power BI.

| Field | Description |
|---|---|
| date | Calendar date, one row per day in the modeled range. |
| calories | Total logged food calories. |
| protein_g | Total protein in grams. |
| carbs_g | Total carbohydrates in grams. |
| fat_g | Total fat in grams. |
| saturated_fat_g | Saturated fat in grams, when exported. |
| trans_fat_g | Trans fat in grams, when exported. |
| fiber_g | Fiber in grams. |
| sugar_g | Sugar in grams. |
| sodium_mg | Sodium in milligrams. |
| potassium_mg | Potassium in milligrams. |
| cholesterol_mg | Cholesterol in milligrams. |
| weight_lb | Bodyweight normalized to pounds. |
| steps | Daily step count. |
| active_energy_kcal | Active energy burned in kcal. |
| basal_energy_kcal | Basal energy burned in kcal. |
| sleep_hours | Daily sleep hours. |
| in_bed_hours | Optional Apple Health in-bed hours. |
| resting_hr | Resting heart rate. |
| hrv_ms | HRV SDNN in milliseconds. |
| workout_minutes | Workout or exercise minutes. |
| calories_7d_avg | Seven-day rolling average calories. |
| protein_7d_avg | Seven-day rolling average protein. |
| weight_7d_avg | Seven-day rolling average bodyweight. |
| sleep_7d_avg | Seven-day rolling average sleep. |
| calorie_delta_from_target | Calories minus configured calorie target. |
| protein_delta_from_target | Protein minus configured protein target. |
| additional micronutrient fields | Any extra nutrient fields preserved from MFP exports. |
