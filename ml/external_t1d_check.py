"""Exploratory external check of the diabetes screen on the local, de-identified
Type-1 Diabetes cohort (85 diagnosed children/adolescents).

This is NOT a validation study:
  * every cohort member has T1D, so only sensitivity (share flagged positive) can be
    estimated; specificity cannot;
  * symptoms were recorded around/after diagnosis (retrospective), not before it;
  * only 5 of the 14 symptom questions exist in the cohort; the other 9 are set to
    "No" (a conservative assumption that can only lower the score);
  * sex is not recorded, so results are reported for both values;
  * cohort ages (4-18) are mostly below the training range (16-90), so the
    model is extrapolating; a sensitivity analysis clips age to 16.

    python -m ml.external_t1d_check
"""
from __future__ import annotations

import json

import joblib
import numpy as np
import pandas as pd

from ml.data import DIABETES_FEATURES, ROOT

COHORT = ROOT / "data" / "restricted" / "t1d_cohort_deidentified.csv"
OUT = ROOT / "artifacts" / "eval" / "t1d_external_check.json"
MAPPING = {"polyuria": "urination", "polydipsia": "thirst", "sudden_weight_loss": "loss_of_weight",
           "visual_blurring": "blurry_vision", "itching": "body_itching"}


def build_features(df: pd.DataFrame, gender_male: int, clip_age: bool) -> pd.DataFrame:
    X = pd.DataFrame(0.0, index=df.index, columns=DIABETES_FEATURES)
    X["age"] = df["age"].clip(lower=16) if clip_age else df["age"]
    X["gender_male"] = float(gender_male)
    for feat, col in MAPPING.items():
        X[feat] = df[col].fillna(0).astype(float)
    bmi = df["weight"] / (df["height"] / 100) ** 2
    X["obesity"] = (bmi >= 30).astype(float).fillna(0)
    return X


def main() -> None:
    if not COHORT.exists():
        raise SystemExit("De-identified cohort not found. Run scripts/deidentify_t1d_cohort.py first.")
    df = pd.read_csv(COHORT)
    models = {n: joblib.load(ROOT / "artifacts" / "models" / "diabetes" / f"{n}.joblib")
              for n in ("hybrid", "random_forest", "ann")}
    meta = json.loads((ROOT / "artifacts" / "models" / "diabetes" / "metadata.json").read_text())
    th = meta["risk_thresholds"]
    results = {}
    for clip in (False, True):
        for g in (0, 1):
            X = build_features(df, g, clip)
            key = f"sex={'male' if g else 'female'}, age={'clipped_to_16' if clip else 'as_recorded'}"
            results[key] = {}
            for name, m in models.items():
                p = m.predict_proba(X)[:, 1]
                results[key][name] = {
                    "share_predicted_positive": round(float((p >= 0.5).mean()), 3),
                    "share_high_risk": round(float((p >= th["high_at_or_above"]).mean()), 3),
                    "share_low_risk": round(float((p < th["low_below"]).mean()), 3),
                    "median_probability": round(float(np.median(p)), 3),
                }
    summary = {
        "n": int(len(df)),
        "cohort_symptom_prevalence": {k: round(float(df[v].mean()), 3) for k, v in MAPPING.items()},
        "share_with_no_mapped_symptom": round(float((df[list(MAPPING.values())].fillna(0).sum(axis=1) == 0).mean()), 3),
        "results": results,
        "caveats": __doc__.split("This is NOT a validation study:")[1].split("python -m")[0].strip(),
    }
    OUT.write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
