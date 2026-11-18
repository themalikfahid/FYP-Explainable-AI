"""Type-1 diabetes clinical-pattern indicator (transparent, rule-based).

IMPORTANT: this is NOT a trained machine-learning model. No dataset available to this project contains
both Type-1 patients and non-diabetic controls, so a Type-1 classifier cannot be trained or validated
(see docs/DATASET_AUDIT.md). Instead this module scores how closely a person's presentation matches the
textbook picture of Type-1 diabetes (ADA Standards of Care; ISPAD guidelines): younger age, rapid
onset, marked thirst/urination/weight loss, non-obese build, family or autoimmune history. Every point
added or removed is shown to the user. It supports a conversation with a clinician; it does not diagnose.

Glucose / HbA1c entries are compared with the published diagnostic thresholds only.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
COHORT_FILE = ROOT / "artifacts" / "eval" / "t1d_external_check.json"

SYMPTOMS = {
    "polyuria": ("Passing a lot of urine", 8, "polyuria"),
    "polydipsia": ("Intense thirst", 8, "polydipsia"),
    "weight_loss": ("Unintentional weight loss", 10, "sudden_weight_loss"),
    "fatigue": ("Unusual tiredness", 3, None),
    "blurred_vision": ("Blurred vision", 3, "visual_blurring"),
    "bedwetting": ("New night-time bed-wetting (children)", 5, None),
    "recurrent_infections": ("Frequent skin or genital infections", 2, None),
}
EMERGENCY = {
    "abdominal_pain_vomiting": "Stomach pain with nausea or vomiting",
    "fruity_breath_or_fast_breathing": "Fruity-smelling breath or fast, deep breathing",
}
BMI_POINTS = {"underweight": (8, "Underweight build"), "normal": (5, "Normal-weight build"),
              "overweight": (-4, "Overweight (more typical of Type 2)"), "obese": (-10, "Obesity (more typical of Type 2)"),
              "unknown": (0, "")}


def _cohort() -> dict:
    try:
        return json.loads(COHORT_FILE.read_text()).get("cohort_symptom_prevalence", {})
    except Exception:
        return {}


def _lab_flags(fasting, random, hba1c, symptomatic: bool) -> tuple[list[dict], bool]:
    flags, diagnostic = [], False
    if fasting is not None:
        if fasting >= 126:
            flags.append({"label": f"Fasting glucose {fasting:.0f} mg/dL is in the diabetes range (>= 126)", "level": "high"})
            diagnostic = True
        elif fasting >= 100:
            flags.append({"label": f"Fasting glucose {fasting:.0f} mg/dL is above normal (100-125, prediabetes range)", "level": "moderate"})
    if random is not None and random >= 200:
        flags.append({"label": f"Random glucose {random:.0f} mg/dL is >= 200" + (" with symptoms (diabetes range)" if symptomatic else ""), "level": "high"})
        diagnostic = diagnostic or symptomatic
    if hba1c is not None:
        if hba1c >= 6.5:
            flags.append({"label": f"HbA1c {hba1c:.1f}% is in the diabetes range (>= 6.5%)", "level": "high"})
            diagnostic = True
        elif hba1c >= 5.7:
            flags.append({"label": f"HbA1c {hba1c:.1f}% is above normal (5.7-6.4%, prediabetes range)", "level": "moderate"})
    return flags, diagnostic


def assess(inp: dict) -> dict:
    age = float(inp["age"])
    weeks = inp.get("symptom_weeks")
    contrib: list[dict] = []

    def add(label: str, pts: int):
        if pts:
            contrib.append({"label": label, "points": pts})

    # age
    if age <= 18:
        add("Age 18 or younger (peak onset of Type 1)", 20)
    elif age <= 30:
        add("Age 19-30", 12)
    elif age <= 40:
        add("Age 31-40", 4)
    else:
        add("Age over 40 (Type 2 is far more common)", -8)

    present = [k for k in SYMPTOMS if inp.get(k)]
    for k in present:
        if k == "bedwetting" and age > 18:
            continue
        add(SYMPTOMS[k][0], SYMPTOMS[k][1])

    symptomatic = bool(present)
    if weeks is not None and symptomatic:
        if weeks <= 6:
            add("Symptoms appeared within about 6 weeks (rapid onset)", 15)
        elif weeks <= 26:
            add("Symptoms developed over 2-6 months", 8)
        else:
            add("Symptoms present for more than 6 months (slow onset)", -5)

    pts, lab = BMI_POINTS.get(inp.get("bmi_category", "unknown"), (0, ""))
    add(lab, pts)
    if inp.get("family_history_t1d"):
        add("Close relative with Type 1 diabetes", 8)
    if inp.get("other_autoimmune"):
        add("Another autoimmune condition (thyroid, coeliac, etc.)", 7)

    flags, diagnostic = _lab_flags(inp.get("fasting_glucose"), inp.get("random_glucose"), inp.get("hba1c"), symptomatic)
    if diagnostic:
        add("Glucose or HbA1c already in the diabetes range", 10)

    raw = sum(c["points"] for c in contrib)
    score = max(0, min(100, raw))
    band = "strong" if score >= 50 else "possible" if score >= 25 else "low"
    emergency = [EMERGENCY[k] for k in EMERGENCY if inp.get(k)]
    dka_warning = bool(emergency) and (inp.get("polyuria") or inp.get("polydipsia") or diagnostic or inp.get("weight_loss"))

    prev = _cohort()
    cohort_notes = []
    for k, (label, _pts, cohort_key) in SYMPTOMS.items():
        if inp.get(k) and cohort_key in prev:
            cohort_notes.append({"symptom": label, "share_of_cohort": prev[cohort_key]})

    steps = []
    if dka_warning:
        steps.append("Seek emergency medical care now. Stomach pain, vomiting or fruity/fast breathing together with high thirst or urination can signal diabetic ketoacidosis, which is an emergency.")
    if band in ("possible", "strong") or diagnostic:
        steps.append("Book a clinician visit within 24-48 hours and ask for a fasting or random plasma glucose and HbA1c.")
        steps.append("If diabetes is confirmed in someone under 40 or with this pattern, ask about confirming the type: blood or urine ketones, C-peptide and islet autoantibodies (GAD65, IA-2, ZnT8).")
    else:
        steps.append("Your reported pattern is not typical of Type 1 diabetes. If symptoms are new or worsening, a basic glucose or HbA1c test is still inexpensive and worthwhile.")
    steps.append("Do not start, stop or change any treatment without a clinician.")

    summary = {
        "strong": "Your answers closely match the classic presentation of Type 1 diabetes. This is a reason to get tested promptly, not a diagnosis.",
        "possible": "Some features match the Type 1 pattern. Testing is the only way to tell.",
        "low": "Few features match the typical Type 1 pattern.",
    }[band]

    return {
        "kind": "t1d_indicator",
        "method": "Rule-based clinical-pattern score (not a trained model)",
        "score": score, "band": band, "summary": summary,
        "contributions": sorted(contrib, key=lambda c: -abs(c["points"])),
        "lab_flags": flags, "meets_diagnostic_range": diagnostic,
        "emergency_warning": bool(dka_warning), "emergency_signs": emergency,
        "next_steps": steps, "cohort_comparison": cohort_notes,
        "cohort_note": "Shares come from a de-identified local cohort of 85 children already diagnosed with Type 1 diabetes. "
                       "They describe how common each symptom was in that group, not your risk." if cohort_notes else None,
        "limitations": [
            "Rules come from published clinical guidance, not from a validated predictive model.",
            "The local T1D cohort has no non-diabetic controls, so it cannot measure how well this pattern separates Type 1 from other people.",
            "Type 1 can only be confirmed by a clinician using laboratory tests.",
        ],
    }
