# Synthetic Sample Data

These files are deterministic, independently simulated wellness exports for public demos and tests. They cover `2025-11-27` through `2026-07-06` and provide:

- 583 fictional MyFitnessPal nutrition rows
- 296 fictional MyFitnessPal exercise rows
- 19 sparse fictional bodyweight measurements
- 222 fictional HealthAutoExport daily rows
- A visible build, maintenance, and cut-style trend for dashboard storytelling
- Correlated sleep, activity, resting heart rate, and HRV values

No private meal names, workout descriptions, daily measurements, or exact personal trajectories are copied into these files.

Regenerate the sample with:

```bash
python src/generate_synthetic_data.py
```

Then build public-safe dashboard outputs with:

```bash
python src/build_dataset.py --sample
```

The AutoExport sample includes deliberately impossible nutrition decoy values. The ETL must ignore them because MyFitnessPal remains the nutrition source of truth.
