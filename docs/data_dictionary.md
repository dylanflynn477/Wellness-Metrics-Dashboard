# Data Dictionary

This dictionary describes the generated CSV outputs and equivalent SQLite tables in `data/processed/`.

When `OUTPUT_MODE=sqlite` or `OUTPUT_MODE=both`, the table names are `daily_nutrition`, `daily_micronutrients`, `daily_activity`, `daily_sleep`, `daily_recovery`, `daily_body_metrics`, and `health_dashboard_fact`.

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

Daily activity values from HealthAutoExport or Apple Health XML, with MFP exercise minutes used as a fallback where Apple exercise minutes are unavailable.

| Field | Description |
|---|---|
| date | Calendar date. |
| steps | Daily step count. |
| active_energy_kcal | Active energy burned in kcal. |
| resting_energy_kcal | Resting or basal energy burned in kcal. |
| apple_exercise_time_min | Apple exercise time in minutes, when exported. |
| apple_stand_time_min | Apple stand time in minutes, when exported. |
| walking_running_distance_mi | Walking and running distance in miles, when exported. |
| flights_climbed | Flights climbed, when exported. |
| vo2_max | VO2 max, when exported. |
| workout_minutes | Unified workout or exercise minutes used by the dashboard. |
| mfp_exercise_calories | Exercise calories from MFP exercise exports, when available. |

## daily_sleep.csv

Daily sleep values from HealthAutoExport or Apple Health sleep analysis records.

| Field | Description |
|---|---|
| date | Calendar date. |
| sleep_hours | Total sleep hours. For HealthAutoExport, uses total sleep first, then Core + Deep + REM if total is missing. |
| sleep_core_hours | Core sleep hours, when exported. |
| sleep_deep_hours | Deep sleep hours, when exported. |
| sleep_rem_hours | REM sleep hours, when exported. |
| sleep_awake_hours | Awake time during sleep window, when exported. |
| sleep_in_bed_hours | In-bed hours, when exported. |

## daily_recovery.csv

Daily recovery and heart metrics from HealthAutoExport or Apple Health XML.

| Field | Description |
|---|---|
| date | Calendar date. |
| resting_hr | Resting heart rate in beats per minute. |
| hrv_ms | Heart rate variability SDNN in milliseconds. |
| respiratory_rate | Respiratory rate, when exported. |
| blood_oxygen_pct | Blood oxygen percentage, when exported. |
| walking_heart_rate_avg | Walking heart rate average, when exported. |
| heart_rate_avg | Average heart rate, when exported. |
| heart_rate_min | Minimum heart rate, when exported. |
| heart_rate_max | Maximum heart rate, when exported. |
| wrist_temperature_f | Wrist temperature in Fahrenheit, when exported. |
| alcohol_consumption_count | Daily alcohol consumption count recorded in HealthKit and exported by HealthAutoExport. This is a logged count, not an inferred quantity or alcohol calorie estimate. |

## daily_body_metrics.csv

Daily body metrics from Apple Health, with MFP progress weight used as a fallback where Apple body mass is unavailable.

| Field | Description |
|---|---|
| date | Calendar date. |
| weight_lb | Bodyweight normalized to pounds. |

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
| resting_energy_kcal | Resting or basal energy burned in kcal. |
| apple_exercise_time_min | Apple exercise time in minutes. |
| apple_stand_time_min | Apple stand time in minutes. |
| walking_running_distance_mi | Walking and running distance in miles. |
| flights_climbed | Flights climbed. |
| vo2_max | VO2 max. |
| sleep_hours | Daily sleep hours. |
| sleep_core_hours | Core sleep hours. |
| sleep_deep_hours | Deep sleep hours. |
| sleep_rem_hours | REM sleep hours. |
| sleep_awake_hours | Awake time during sleep window. |
| sleep_in_bed_hours | Optional Apple Health in-bed hours. |
| resting_hr | Resting heart rate. |
| hrv_ms | HRV SDNN in milliseconds. |
| respiratory_rate | Respiratory rate. |
| blood_oxygen_pct | Blood oxygen percentage. |
| walking_heart_rate_avg | Walking heart rate average. |
| heart_rate_avg | Average heart rate. |
| heart_rate_min | Minimum heart rate. |
| heart_rate_max | Maximum heart rate. |
| wrist_temperature_f | Wrist temperature in Fahrenheit. |
| alcohol_consumption_count | Daily alcohol consumption count from HealthAutoExport. Null means no source value was exported; zero means the source explicitly reported zero. |
| workout_minutes | Workout or exercise minutes. |
| mfp_exercise_calories | Exercise calories from MFP exercise exports. |
| calories_7d_avg | Seven-day rolling average calories. |
| protein_7d_avg | Seven-day rolling average protein. |
| weight_7d_avg | Seven-day rolling average bodyweight. |
| sleep_7d_avg | Seven-day rolling average sleep. |
| resting_hr_7d_avg | Seven-calendar-day rolling average resting heart rate, ignoring missing daily readings. |
| hrv_7d_avg | Seven-calendar-day rolling average HRV SDNN, ignoring missing daily readings. |
| weight_measurement_flag | `1` when bodyweight was recorded on that date and `0` otherwise; useful for filtering sparse weigh-ins in Power BI. |
| calorie_delta_from_target | Calories minus configured calorie target. |
| protein_delta_from_target | Protein minus configured protein target. |
| additional micronutrient fields | Any extra nutrient fields preserved from MFP exports. |
