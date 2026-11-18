"""Rule-based personalised recommendation engine.

Inputs: disease, risk level, model inputs, top SHAP contributions and optional
lifestyle data. Output: a list of recommendations, each with category,
priority, text, the rule that triggered it, and a guideline source.

Deliberately NOT included: medicines, dosages, or diagnostic statements.
Every rule is listed in docs/RECOMMENDATION_ENGINE.md.
"""
from __future__ import annotations

from backend.app.services.scoring import bmi as bmi_calc
from backend.app.services.scoring import lifestyle_score

SOURCES = {
    "who_pa": "WHO guidelines on physical activity and sedentary behaviour (2020)",
    "who_diet": "WHO Healthy diet fact sheet (2020)",
    "sleep": "AASM/SRS consensus statement on adult sleep duration (Watson et al., 2015)",
    "ada": "American Diabetes Association, Standards of Care in Diabetes (diagnosis section)",
    "diabetes_uk_4t": "Diabetes UK '4Ts' type 1 diabetes symptom awareness guidance",
    "aha_warning": "American Heart Association, Warning Signs of a Heart Attack",
    "acc_aha_prev": "ACC/AHA Guideline on the Primary Prevention of Cardiovascular Disease (2019)",
    "acc_aha_chest_pain": "AHA/ACC Guideline for the Evaluation and Diagnosis of Chest Pain (2021)",
    "acc_aha_bp": "ACC/AHA High Blood Pressure Guideline (2017)",
    "ncep": "NCEP ATP III cholesterol classification",
    "uk_cmo_alcohol": "UK Chief Medical Officers' low-risk drinking guidelines (2016)",
    "who_tobacco": "WHO tobacco cessation guidance",
    "who_bmi": "WHO BMI classification / WHO Expert Consultation on Asian BMI (2004)",
}

DISCLAIMER = ("This application is an educational screening and decision-support prototype. It does not "
              "provide a diagnosis and is not a substitute for evaluation by a qualified health professional. "
              "If you feel unwell or have urgent symptoms, contact a doctor or emergency services.")


def _rec(category, priority, text, rule, source) -> dict:
    return {"category": category, "priority": priority, "text": text, "rule": rule, "source": SOURCES[source]}


def _top_positive(explanation: dict | None, n: int = 3) -> list[str]:
    if not explanation:
        return []
    return [c["feature"] for c in explanation["contributions"] if c["shap"] > 0][:n]


def diabetes_rules(f: dict, risk: str, top: list[str]) -> list[dict]:
    r = []
    if risk == "high":
        r.append(_rec("follow_up", "high",
                      "Book an appointment with a doctor soon to have your blood glucose checked (for example a "
                      "fasting glucose or HbA1c test). Only a laboratory test can confirm or rule out diabetes.",
                      "risk_level == high", "ada"))
    elif risk == "moderate":
        r.append(_rec("follow_up", "medium",
                      "Consider asking a doctor or clinic for a routine blood glucose test, especially if symptoms persist.",
                      "risk_level == moderate", "ada"))
    else:
        r.append(_rec("follow_up", "low",
                      "No action is suggested by this screen. Repeat it, or see a doctor, if new symptoms appear.",
                      "risk_level == low", "ada"))
    if f.get("polyuria") and f.get("polydipsia") and f.get("sudden_weight_loss"):
        r.append(_rec("risk_mitigation", "high",
                      "Frequent urination, strong thirst and unexplained weight loss together can be signs of new-onset "
                      "diabetes, including type 1. Seek same-day medical care if they come with vomiting, abdominal "
                      "pain, drowsiness, confusion or fast breathing.",
                      "polyuria AND polydipsia AND sudden_weight_loss", "diabetes_uk_4t"))
    if f.get("visual_blurring") or f.get("delayed_healing"):
        r.append(_rec("follow_up", "medium",
                      "Blurred vision or slow-healing wounds should be mentioned to your doctor, as they can be linked "
                      "to raised blood sugar.", "visual_blurring OR delayed_healing", "ada"))
    r.append(_rec("diet", "medium",
                  "Limit sugary drinks and sweets; choose water, whole grains, pulses, vegetables and fruit, and keep "
                  "free sugars below 10% of daily energy.", "diabetes task (always)", "who_diet"))
    if f.get("obesity") or "obesity" in top:
        r.append(_rec("activity", "medium",
                      "Gradual weight reduction through regular activity and smaller portions can lower diabetes risk. "
                      "A doctor or dietitian can help set a safe target.", "obesity == yes OR obesity in top SHAP", "who_pa"))
    return r


def heart_rules(f: dict, risk: str, top: list[str]) -> list[dict]:
    r = []
    if risk == "high":
        r.append(_rec("follow_up", "high",
                      "Arrange a review with a doctor or cardiologist soon and bring this report. The model estimates a "
                      "high probability of heart disease, which needs clinical assessment.", "risk_level == high",
                      "acc_aha_prev"))
    elif risk == "moderate":
        r.append(_rec("follow_up", "medium",
                      "Discuss your heart health with a doctor at your next visit, including blood pressure and "
                      "cholesterol checks.", "risk_level == moderate", "acc_aha_prev"))
    else:
        r.append(_rec("follow_up", "low",
                      "Keep up regular health check-ups (blood pressure, cholesterol, blood sugar).",
                      "risk_level == low", "acc_aha_prev"))
    if f.get("cp") in (1, 2) or f.get("exang"):
        r.append(_rec("risk_mitigation", "high",
                      "Chest pain that comes on at rest, lasts more than a few minutes, or comes with breathlessness, "
                      "sweating or nausea is an emergency: call emergency services immediately.",
                      "cp in (typical, atypical angina) OR exang == yes", "aha_warning"))
    if f.get("trestbps") is not None and f["trestbps"] >= 130:
        r.append(_rec("risk_mitigation", "medium",
                      f"Your resting systolic blood pressure ({f['trestbps']:g} mm Hg) is at or above 130. Have it "
                      "re-measured on separate days; reducing salt, staying active and limiting alcohol help.",
                      "trestbps >= 130", "acc_aha_bp"))
    if f.get("chol") is not None and f["chol"] >= 240:
        r.append(_rec("follow_up", "medium",
                      f"Your cholesterol ({f['chol']:g} mg/dL) is in the 'high' range (>= 240). Ask for a full lipid "
                      "profile and advice from a doctor.", "chol >= 240", "ncep"))
    elif f.get("chol") is not None and f["chol"] >= 200:
        r.append(_rec("diet", "low",
                      f"Your cholesterol ({f['chol']:g} mg/dL) is borderline high (200-239). Fewer fried and fatty "
                      "foods and more fibre can help.", "200 <= chol < 240", "ncep"))
    if f.get("fbs"):
        r.append(_rec("follow_up", "medium",
                      "A fasting blood sugar above 120 mg/dL should be followed up with a doctor.", "fbs == 1", "ada"))
    r.append(_rec("diet", "medium",
                  "Eat less salt (under 5 g a day), fewer saturated and trans fats, and more vegetables, fruit, "
                  "whole grains and pulses.", "heart task (always)", "who_diet"))
    return r


def cad_rules(f: dict, risk: str, top: list[str]) -> list[dict]:
    r = []
    if risk == "high":
        r.append(_rec("follow_up", "high",
                      "The screen suggests coronary artery disease is likely. See a doctor (ideally a cardiologist) "
                      "soon for an ECG, stress test or imaging. Only angiography or CT can confirm it.",
                      "risk_level == high", "acc_aha_chest_pain"))
    elif risk == "moderate":
        r.append(_rec("follow_up", "medium",
                      "The result is in the uncertain range. A doctor visit with an ECG and a lipid profile would "
                      "clarify your heart risk.", "risk_level == moderate", "acc_aha_chest_pain"))
    else:
        r.append(_rec("follow_up", "low",
                      "The screen did not suggest significant coronary disease. Keep up regular check-ups, and "
                      "report any new chest pain or breathlessness.", "risk_level == low", "acc_aha_chest_pain"))
    if f.get("typical_chest_pain") or f.get("function_class", 0) >= 2:
        r.append(_rec("emergency", "high",
                      "Chest pain on effort or marked breathlessness needs medical assessment. Call emergency "
                      "services if pain is severe, spreads to the arm or jaw, or lasts more than a few minutes.",
                      "typical_chest_pain or function_class >= 2", "acc_aha_chest_pain"))
    if f.get("current_smoker"):
        r.append(_rec("risk_mitigation", "high", "Stopping smoking is the single most effective step for heart health. "
                      "Ask a doctor or quit-line for support.", "current_smoker == 1", "who_tobacco"))
    if f.get("bp_systolic") is not None and f["bp_systolic"] >= 130:
        r.append(_rec("risk_mitigation", "medium",
                      f"Your systolic blood pressure ({f['bp_systolic']:g} mm Hg) is at or above 130. Have it "
                      "re-measured on separate days.", "bp_systolic >= 130", "acc_aha_bp"))
    if f.get("ldl") is not None and f["ldl"] >= 130:
        r.append(_rec("follow_up", "medium", f"Your LDL cholesterol ({f['ldl']:g} mg/dL) is above 130. Ask a doctor "
                      "about a full lipid profile and treatment options.", "ldl >= 130", "ncep"))
    if f.get("fbs_mgdl") is not None and f["fbs_mgdl"] >= 126:
        r.append(_rec("follow_up", "medium", "Fasting glucose of 126 mg/dL or more should be followed up with a "
                      "doctor (possible diabetes).", "fbs_mgdl >= 126", "ada"))
    r.append(_rec("diet", "medium", "Eat less salt and saturated fat and more vegetables, fruit, whole grains and "
                  "pulses.", "cad task (always)", "who_diet"))
    return r


def lifestyle_rules(ls: dict) -> tuple[list[dict], dict, dict]:
    r = []
    score = lifestyle_score(ls["sleep_hours"], ls["activity_minutes_week"], ls["fruit_veg_servings_day"],
                            ls["smoking"], ls["alcohol_units_week"])
    b = bmi_calc(ls["height_cm"], ls["weight_kg"], ls.get("asian_bmi_cutoffs", False))
    if ls["activity_minutes_week"] < 150:
        r.append(_rec("activity", "medium",
                      f"You reported {ls['activity_minutes_week']:g} minutes of activity per week. Build up gradually "
                      "towards at least 150 minutes of moderate activity (such as brisk walking), plus muscle-"
                      "strengthening on 2 days.", "activity_minutes_week < 150", "who_pa"))
    else:
        r.append(_rec("activity", "low", "You meet the weekly activity recommendation. Keep it up and limit long "
                      "periods of sitting.", "activity_minutes_week >= 150", "who_pa"))
    if ls["sleep_hours"] < 7:
        r.append(_rec("sleep", "medium",
                      f"You reported {ls['sleep_hours']:g} hours of sleep. Aim for at least 7 hours with a regular "
                      "sleep and wake time, and limit screens and caffeine late in the day.", "sleep_hours < 7", "sleep"))
    elif ls["sleep_hours"] > 9:
        r.append(_rec("sleep", "low",
                      "You reported more than 9 hours of sleep. If you still feel tired, mention it to a doctor.",
                      "sleep_hours > 9", "sleep"))
    else:
        r.append(_rec("sleep", "low", "Your sleep duration is in the recommended 7-9 hour range.",
                      "7 <= sleep_hours <= 9", "sleep"))
    if ls["fruit_veg_servings_day"] < 5:
        r.append(_rec("diet", "medium", "Add fruit or vegetables to each meal to reach about 5 servings (400 g) a day.",
                      "fruit_veg_servings_day < 5", "who_diet"))
    if ls["smoking"] == "current":
        r.append(_rec("risk_mitigation", "high", "Stopping smoking is one of the most effective ways to lower heart "
                      "and diabetes complications risk. Ask a doctor or a quit-line about support.",
                      "smoking == current", "who_tobacco"))
    if ls["alcohol_units_week"] > 14:
        r.append(_rec("risk_mitigation", "medium", f"You reported {ls['alcohol_units_week']:g} units of alcohol a "
                      "week. Keep to 14 units or fewer, spread over several days with alcohol-free days.",
                      "alcohol_units_week > 14", "uk_cmo_alcohol"))
    if b["category"] not in ("Healthy weight",):
        r.append(_rec("diet", "medium", f"Your BMI is {b['bmi']} ({b['category']}). A healthy weight range for your "
                      f"height is about {b['healthy_weight_range_kg'][0]}-{b['healthy_weight_range_kg'][1]} kg. BMI is "
                      "only a rough guide; discuss weight goals with a professional.", "BMI outside healthy range",
                      "who_bmi"))
    return r, score, b


PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2}


def recommend(disease: str, features: dict, risk_level: str, explanation: dict | None,
              lifestyle: dict | None) -> dict:
    top = _top_positive(explanation)
    rules = {"diabetes": diabetes_rules, "heart": heart_rules, "cad": cad_rules}[disease]
    recs = rules(features, risk_level, top)
    score = bmi = None
    if lifestyle:
        extra, score, bmi = lifestyle_rules(lifestyle)
        recs += extra
    else:
        recs.append(_rec("activity", "low", "Add your lifestyle details (sleep, activity, diet, smoking, alcohol, "
                         "height and weight) to receive a lifestyle score, BMI and more personalised suggestions.",
                         "lifestyle not provided", "who_pa"))
    recs.sort(key=lambda d: PRIORITY_ORDER[d["priority"]])
    return {"items": recs, "lifestyle_score": score, "bmi": bmi, "top_risk_factors": top, "disclaimer": DISCLAIMER}
