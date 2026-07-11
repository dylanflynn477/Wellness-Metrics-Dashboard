"""Generate public-safe synthetic MFP and HealthAutoExport source files.

The generated scenario is independently simulated. It preserves useful schemas,
date coverage, broad missingness, and cross-metric relationships without copying
private row values, meal names, workouts, or exact personal trajectories.
"""

from __future__ import annotations

import argparse
import csv
from datetime import date, timedelta
import math
from pathlib import Path
import random
from typing import Iterable

try:
    from .config import PROJECT_ROOT
except ImportError:  # pragma: no cover - supports direct script execution
    from config import PROJECT_ROOT


DEFAULT_START_DATE = date(2025, 11, 27)
DEFAULT_END_DATE = date(2026, 7, 6)
DEFAULT_SEED = 20260706

MFP_NUTRITION_FIELDS = [
    "Date",
    "Meal",
    "Calories",
    "Fat (g)",
    "Saturated Fat",
    "Polyunsaturated Fat",
    "Monounsaturated Fat",
    "Trans Fat",
    "Cholesterol",
    "Sodium (mg)",
    "Potassium",
    "Carbohydrates (g)",
    "Fiber",
    "Sugar",
    "Protein (g)",
    "Vitamin A",
    "Vitamin C",
    "Calcium",
    "Iron",
    "Note",
]

MFP_EXERCISE_FIELDS = [
    "Date",
    "Exercise",
    "Type",
    "Exercise Calories",
    "Exercise Minutes",
    "Sets",
    "Reps Per Set",
    "Pounds",
    "Steps",
    "Note",
]

AUTOEXPORT_FIELDS = [
    "Date/Time",
    "Step Count (steps)",
    "Active Energy (kcal)",
    "Resting Energy (kcal)",
    "Apple Exercise Time (min)",
    "Apple Stand Time (min)",
    "Walking + Running Distance (mi)",
    "Flights Climbed (count)",
    "VO2 Max (ml/(kg·min))",
    "Sleep Analysis [Total] (hr)",
    "Sleep Analysis [Asleep] (hr)",
    "Sleep Analysis [In Bed] (hr)",
    "Sleep Analysis [Core] (hr)",
    "Sleep Analysis [Deep] (hr)",
    "Sleep Analysis [REM] (hr)",
    "Sleep Analysis [Awake] (hr)",
    "Resting Heart Rate (bpm)",
    "Heart Rate Variability (ms)",
    "Respiratory Rate (count/min)",
    "Blood Oxygen Saturation (%)",
    "Walking Heart Rate Average (bpm)",
    "Heart Rate [Avg] (bpm)",
    "Heart Rate [Min] (bpm)",
    "Heart Rate [Max] (bpm)",
    "Apple Sleeping Wrist Temperature (ºF)",
    # Deliberately unrealistic decoys prove that AutoExport nutrition is ignored.
    "Dietary Energy (kcal)",
    "Protein (g)",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate deterministic public-safe wellness sample exports.")
    parser.add_argument("--start-date", type=date.fromisoformat, default=DEFAULT_START_DATE)
    parser.add_argument("--end-date", type=date.fromisoformat, default=DEFAULT_END_DATE)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--output-root", type=Path, default=PROJECT_ROOT / "data" / "sample")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    outputs = generate_synthetic_dataset(args.output_root, args.start_date, args.end_date, args.seed)
    print("Synthetic wellness sample generated")
    for name, path in outputs.items():
        print(f"- {name}: {path}")


def generate_synthetic_dataset(
    output_root: Path,
    start_date: date = DEFAULT_START_DATE,
    end_date: date = DEFAULT_END_DATE,
    seed: int = DEFAULT_SEED,
) -> dict[str, Path]:
    """Write deterministic MFP and AutoExport samples and return their paths."""

    if end_date < start_date:
        raise ValueError("end_date must be on or after start_date")

    dates = list(iter_dates(start_date, end_date))
    rng = random.Random(seed)
    daily = build_daily_scenario(dates, rng)

    mfp_dir = output_root / "mfp"
    apple_dir = output_root / "apple_health"
    mfp_dir.mkdir(parents=True, exist_ok=True)
    apple_dir.mkdir(parents=True, exist_ok=True)

    outputs = {
        "mfp_nutrition": mfp_dir / "nutrition.csv",
        "mfp_exercise": mfp_dir / "exercise.csv",
        "mfp_progress": mfp_dir / "progress.csv",
        "apple_health_autoexport": apple_dir / "HealthAutoExport.csv",
    }
    write_csv(outputs["mfp_nutrition"], MFP_NUTRITION_FIELDS, build_nutrition_rows(daily, rng))
    write_csv(outputs["mfp_exercise"], MFP_EXERCISE_FIELDS, build_exercise_rows(daily, rng))
    write_csv(outputs["mfp_progress"], ["Date", "Weight"], build_progress_rows(daily, rng))
    write_csv(outputs["apple_health_autoexport"], AUTOEXPORT_FIELDS, build_autoexport_rows(daily, rng))
    return outputs


def iter_dates(start_date: date, end_date: date) -> Iterable[date]:
    current = start_date
    while current <= end_date:
        yield current
        current += timedelta(days=1)


def build_daily_scenario(dates: list[date], rng: random.Random) -> list[dict[str, float | date | str]]:
    """Create a fictional build-maintain-cut arc with correlated daily metrics."""

    output = []
    last_index = max(len(dates) - 1, 1)
    for index, current_date in enumerate(dates):
        progress = index / last_index
        if progress < 0.32:
            phase = "build"
            phase_progress = progress / 0.32
            calorie_base = 3200
            weight = 184.0 + 6.0 * phase_progress
        elif progress < 0.56:
            phase = "maintain"
            phase_progress = (progress - 0.32) / 0.24
            calorie_base = 2850
            weight = 190.0 - 0.5 * phase_progress
        else:
            phase = "cut"
            phase_progress = (progress - 0.56) / 0.44
            calorie_base = 2450
            weight = 189.5 - 8.0 * phase_progress

        weekend_boost = 140 if current_date.weekday() in {4, 5} else 0
        calories = clamp(calorie_base + weekend_boost + rng.gauss(0, 260), 1850, 3900)
        protein = clamp(195 + (calories - 2800) * 0.018 + rng.gauss(0, 16), 145, 255)
        fat = clamp({"build": 98, "maintain": 86, "cut": 72}[phase] + rng.gauss(0, 12), 45, 135)
        carbs = clamp((calories - 4 * protein - 9 * fat) / 4, 160, 525)

        workout = current_date.weekday() in {0, 2, 4, 5}
        steps = int(round(clamp(8200 + (1900 if workout else 0) + rng.gauss(0, 2200), 2800, 18500)))
        exercise_minutes = int(round(clamp((48 if workout else 16) + rng.gauss(0, 12), 0, 95)))
        active_energy = clamp(350 + steps * 0.045 + exercise_minutes * 3.1 + rng.gauss(0, 80), 350, 1450)

        sleep = clamp(7.65 + 0.25 * math.sin(index / 8) + rng.gauss(0, 0.55), 5.6, 9.4)
        resting_hr = clamp(60.5 + (7.5 - sleep) * 1.7 + active_energy / 950 + rng.gauss(0, 2.2), 51, 76)
        hrv = clamp(64 - (resting_hr - 60) * 1.35 + (sleep - 7.5) * 4 + rng.gauss(0, 8), 30, 95)

        output.append(
            {
                "date": current_date,
                "phase": phase,
                "weight": weight + rng.gauss(0, 0.45),
                "calories": calories,
                "protein": protein,
                "fat": fat,
                "carbs": carbs,
                "fiber": clamp(29 + carbs * 0.018 + rng.gauss(0, 5), 17, 52),
                "sugar": clamp(72 + weekend_boost * 0.12 + rng.gauss(0, 20), 25, 145),
                "sodium": clamp(2850 + weekend_boost * 2.5 + rng.gauss(0, 650), 1450, 5200),
                "potassium": clamp(3700 + rng.gauss(0, 520), 2400, 5400),
                "cholesterol": clamp(330 + rng.gauss(0, 110), 90, 680),
                "steps": steps,
                "exercise_minutes": exercise_minutes,
                "active_energy": active_energy,
                "sleep": sleep,
                "resting_hr": resting_hr,
                "hrv": hrv,
            }
        )
    return output


def build_nutrition_rows(daily: list[dict[str, float | date | str]], rng: random.Random) -> list[dict[str, object]]:
    # Match the reference export's broad row density without matching which dates had missing meals.
    two_meal_count = min(len(daily), round(len(daily) * 83 / 222))
    two_meal_dates = set(rng.sample(range(len(daily)), two_meal_count))
    rows = []
    for index, day in enumerate(daily):
        meals = ["Breakfast", "Dinner"] if index in two_meal_dates else ["Breakfast", "Lunch", "Dinner"]
        weights = [0.34, 0.66] if len(meals) == 2 else [0.25, 0.34, 0.41]
        totals = {
            "Calories": day["calories"],
            "Fat (g)": day["fat"],
            "Saturated Fat": float(day["fat"]) * 0.18,
            "Polyunsaturated Fat": float(day["fat"]) * 0.14,
            "Monounsaturated Fat": float(day["fat"]) * 0.31,
            "Trans Fat": clamp(rng.gauss(0.35, 0.25), 0, 1.2),
            "Cholesterol": day["cholesterol"],
            "Sodium (mg)": day["sodium"],
            "Potassium": day["potassium"],
            "Carbohydrates (g)": day["carbs"],
            "Fiber": day["fiber"],
            "Sugar": day["sugar"],
            "Protein (g)": day["protein"],
            "Vitamin A": clamp(rng.gauss(115, 25), 55, 190),
            "Vitamin C": clamp(rng.gauss(130, 40), 45, 240),
            "Calcium": clamp(rng.gauss(105, 20), 55, 170),
            "Iron": clamp(rng.gauss(110, 25), 50, 185),
        }
        for meal, weight in zip(meals, weights):
            row: dict[str, object] = {"Date": day["date"].isoformat(), "Meal": meal, "Note": ""}
            for field, total in totals.items():
                row[field] = round(float(total) * weight, 1)
            rows.append(row)
    return rows


def build_exercise_rows(daily: list[dict[str, float | date | str]], rng: random.Random) -> list[dict[str, object]]:
    extra_count = min(len(daily), round(len(daily) * 74 / 222))
    extra_days = set(rng.sample(range(len(daily)), extra_count))
    rows = []
    for index, day in enumerate(daily):
        minutes = int(clamp(22 + rng.gauss(0, 8), 8, 45))
        rows.append(exercise_row(day["date"], "Walking", "Cardio", minutes, minutes * 6.5, rng))
        if index in extra_days:
            exercise = ["Strength Training", "Cycling", "Interval Training"][index % 3]
            exercise_type = "Strength" if exercise == "Strength Training" else "Cardio"
            minutes = int(clamp(42 + rng.gauss(0, 11), 20, 75))
            rows.append(exercise_row(day["date"], exercise, exercise_type, minutes, minutes * 8.2, rng))
    return rows


def exercise_row(
    workout_date: date,
    exercise: str,
    exercise_type: str,
    minutes: int,
    calories: float,
    rng: random.Random,
) -> dict[str, object]:
    strength = exercise_type == "Strength"
    return {
        "Date": workout_date.isoformat(),
        "Exercise": exercise,
        "Type": exercise_type,
        "Exercise Calories": round(calories + rng.gauss(0, 25), 1),
        "Exercise Minutes": minutes,
        "Sets": 5 if strength else "",
        "Reps Per Set": 8 if strength else "",
        "Pounds": 135 if strength else "",
        "Steps": "",
        "Note": "",
    }


def build_progress_rows(daily: list[dict[str, float | date | str]], rng: random.Random) -> list[dict[str, object]]:
    measurement_count = max(2, round(len(daily) * 19 / 222))
    indices = sorted({round(i * (len(daily) - 1) / (measurement_count - 1)) for i in range(measurement_count)})
    return [
        {"Date": daily[index]["date"].isoformat(), "Weight": round(float(daily[index]["weight"]) + rng.gauss(0, 0.2), 1)}
        for index in indices
    ]


def build_autoexport_rows(daily: list[dict[str, float | date | str]], rng: random.Random) -> list[dict[str, object]]:
    rows = []
    for index, day in enumerate(daily):
        sleep = float(day["sleep"])
        deep = clamp(1.05 + rng.gauss(0, 0.2), 0.55, 1.65)
        rem = clamp(1.85 + rng.gauss(0, 0.3), 1.0, 2.7)
        core = max(3.0, sleep - deep - rem)
        awake = clamp(0.42 + rng.gauss(0, 0.15), 0.1, 0.9)
        steps = int(day["steps"])
        exercise_minutes = int(day["exercise_minutes"])
        resting_hr = float(day["resting_hr"])
        row = {
            "Date/Time": day["date"].isoformat(),
            "Step Count (steps)": steps,
            "Active Energy (kcal)": round(float(day["active_energy"]), 1),
            "Resting Energy (kcal)": int(round(2025 + (float(day["weight"]) - 185) * 4 + rng.gauss(0, 35))),
            "Apple Exercise Time (min)": exercise_minutes,
            "Apple Stand Time (min)": int(round(clamp(155 + rng.gauss(0, 28), 75, 220))),
            "Walking + Running Distance (mi)": round(steps / 2250 + rng.gauss(0, 0.18), 2),
            "Flights Climbed (count)": int(round(clamp(8 + rng.gauss(0, 5), 0, 28))),
            "VO2 Max (ml/(kg·min))": round(43.5 + index * 0.006 + rng.gauss(0, 0.45), 2),
            "Sleep Analysis [Total] (hr)": "" if index % 17 == 6 else round(sleep, 2),
            "Sleep Analysis [Asleep] (hr)": 0,
            "Sleep Analysis [In Bed] (hr)": round(sleep + awake, 2),
            "Sleep Analysis [Core] (hr)": round(core, 2),
            "Sleep Analysis [Deep] (hr)": round(deep, 2),
            "Sleep Analysis [REM] (hr)": round(rem, 2),
            "Sleep Analysis [Awake] (hr)": round(awake, 2),
            "Resting Heart Rate (bpm)": int(round(resting_hr)),
            "Heart Rate Variability (ms)": round(float(day["hrv"]), 2),
            "Respiratory Rate (count/min)": round(clamp(15.1 + rng.gauss(0, 0.65), 12.8, 17.5), 2),
            "Blood Oxygen Saturation (%)": round(clamp(97.2 + rng.gauss(0, 0.65), 94.5, 99.5), 2),
            "Walking Heart Rate Average (bpm)": int(round(clamp(96 + steps / 4200 + rng.gauss(0, 5), 82, 118))),
            "Heart Rate [Avg] (bpm)": round(clamp(resting_hr + 21 + rng.gauss(0, 4), 68, 98), 1),
            "Heart Rate [Min] (bpm)": int(round(clamp(resting_hr - 11 + rng.gauss(0, 2), 40, 61))),
            "Heart Rate [Max] (bpm)": int(round(clamp(145 + exercise_minutes * 0.35 + rng.gauss(0, 10), 125, 185))),
            "Apple Sleeping Wrist Temperature (ºF)": round(clamp(97.55 + rng.gauss(0, 0.38), 96.4, 98.8), 2),
            "Dietary Energy (kcal)": 9999,
            "Protein (g)": 999,
        }
        rows.append(row)
    return rows


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(value, upper))


if __name__ == "__main__":
    main()
