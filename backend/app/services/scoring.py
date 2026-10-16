"""BMI and lifestyle score. Formulas and sources are documented in
docs/RECOMMENDATION_ENGINE.md (section 'Scoring')."""
from __future__ import annotations

# WHO adult BMI categories (kg/m^2)
WHO_BMI = [(18.5, "Underweight"), (25.0, "Healthy weight"), (30.0, "Overweight"), (float("inf"), "Obesity")]
# WHO Expert Consultation (Lancet 2004) public-health action points for Asian populations
ASIAN_BMI = [(18.5, "Underweight"), (23.0, "Healthy weight"), (27.5, "Increased risk (overweight)"),
             (float("inf"), "High risk (obesity)")]


def bmi(height_cm: float, weight_kg: float, asian_cutoffs: bool = False) -> dict:
    if height_cm <= 0 or weight_kg <= 0:
        raise ValueError("height and weight must be positive")
    h = height_cm / 100.0
    # categorise the value as displayed (1 decimal) so 29.99.. shown as "30.0" is not labelled overweight
    value = round(weight_kg / (h * h), 1)
    table = ASIAN_BMI if asian_cutoffs else WHO_BMI
    category = next(label for upper, label in table if value < upper)
    lo, hi = (18.5, 22.9) if asian_cutoffs else (18.5, 24.9)
    return {
        "bmi": value,
        "category": category,
        "cutoffs": "WHO Asian action points (23 / 27.5)" if asian_cutoffs else "WHO adult (18.5 / 25 / 30)",
        "healthy_weight_range_kg": [round(lo * h * h, 1), round(hi * h * h, 1)],
        "note": ("BMI is a screening measure for adults. It does not measure body fat directly or "
                 "account for muscle mass, age, sex or ethnicity, and is not a complete health assessment."),
    }


def lifestyle_score(sleep_hours: float, activity_minutes_week: float, fruit_veg_servings_day: float,
                    smoking: str, alcohol_units_week: float) -> dict:
    """0-100 educational lifestyle score from five weighted components."""
    # Physical activity (25): WHO 2020 recommends 150-300 min/week moderate activity
    if activity_minutes_week >= 150:
        act = 25
    elif activity_minutes_week >= 75:
        act = 15
    elif activity_minutes_week > 0:
        act = 7
    else:
        act = 0
    # Sleep (20): AASM/SRS consensus: adults need >= 7 h; 7-9 h is the usual recommended range
    if 7 <= sleep_hours <= 9:
        slp = 20
    elif 6 <= sleep_hours < 7 or 9 < sleep_hours <= 10:
        slp = 12
    else:
        slp = 5
    # Diet (20): WHO recommends >= 400 g (about 5 servings) of fruit and vegetables per day
    if fruit_veg_servings_day >= 5:
        diet = 20
    elif fruit_veg_servings_day >= 3:
        diet = 12
    elif fruit_veg_servings_day >= 1:
        diet = 6
    else:
        diet = 0
    # Smoking (20)
    smk = {"never": 20, "former": 14, "current": 0}[smoking]
    # Alcohol (15): UK Chief Medical Officers' low-risk guideline is <= 14 units/week
    if alcohol_units_week == 0:
        alc = 15
    elif alcohol_units_week <= 14:
        alc = 10
    else:
        alc = 0
    total = act + slp + diet + smk + alc
    band = "Good" if total >= 80 else "Fair" if total >= 60 else "Needs improvement"
    return {
        "score": total,
        "band": band,
        "components": {
            "physical_activity": {"points": act, "max": 25, "input": activity_minutes_week},
            "sleep": {"points": slp, "max": 20, "input": sleep_hours},
            "diet_fruit_veg": {"points": diet, "max": 20, "input": fruit_veg_servings_day},
            "smoking": {"points": smk, "max": 20, "input": smoking},
            "alcohol": {"points": alc, "max": 15, "input": alcohol_units_week},
        },
        "note": ("Educational score based on public-health guidelines. It is not a validated clinical "
                 "risk score and is not used by the machine-learning models."),
    }
