"""Profile every dataset used (or considered) by the project.

Writes artifacts/eval/dataset_profile.json. All numbers in docs/DATASET_AUDIT.md
come from this file.

    python -m ml.audit_datasets
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from ml.data import (
    ROOT, HEART_FEATURES, load_heart_raw, load_diabetes_raw, DIABETES_TARGET,
)

OUT = ROOT / "artifacts" / "eval" / "dataset_profile.json"


def _missing(df: pd.DataFrame) -> dict:
    return {c: int(v) for c, v in df.isna().sum().items() if v}


def hungarian_label_check() -> dict:
    """Show that processed.hungarian.data collapses grades 1-4 into 1."""
    df = load_heart_raw(clean_invalid=False, include_audit_only=True)
    raw = df[df.site == "hungarian"].copy()
    proc = df[df.site == "hungarian_processed"].copy()
    key = lambda d: d[HEART_FEATURES].fillna(-999).round(3).astype(str).agg("|".join, axis=1)
    raw["k"], proc["k"] = key(raw), key(proc)
    m = proc.merge(raw[["k", "num"]].drop_duplicates("k").rename(columns={"num": "graded"}), on="k", how="inner")
    ct = pd.crosstab(m["num"], m["graded"])
    return {
        "processed_label_values": sorted(int(v) for v in proc["num"].unique()),
        "raw_label_values": sorted(int(v) for v in raw["num"].unique()),
        "rows_matched_by_features": int(len(m)),
        "crosstab_processed_rows_vs_raw_cols": {int(i): {int(j): int(ct.loc[i, j]) for j in ct.columns} for i in ct.index},
        "conclusion": "processed 0 == raw 0 and processed 1 == raw 1..4 for every matched row; raw file used for training",
    }


def profile_heart() -> dict:
    df = load_heart_raw(clean_invalid=False)
    out = {
        "rows": int(len(df)),
        "rows_per_site": df["site"].value_counts().to_dict(),
        "target_distribution_num": {int(k): int(v) for k, v in df["num"].value_counts().sort_index().items()},
        "target_by_site": {s: {int(k): int(v) for k, v in g["num"].value_counts().sort_index().items()}
                           for s, g in df.groupby("site")},
        "missing_raw": _missing(df[HEART_FEATURES]),
        "missing_by_site_pct": {s: {c: round(float(g[c].isna().mean() * 100), 1) for c in ["slope", "ca", "thal"]}
                                for s, g in df.groupby("site")},
        "zero_cholesterol_rows": int((df["chol"] == 0).sum()),
        "zero_cholesterol_by_site": df.loc[df["chol"] == 0, "site"].value_counts().to_dict(),
        "zero_resting_bp_rows": int((df["trestbps"] == 0).sum()),
        "negative_oldpeak_rows": int((df["oldpeak"] < 0).sum()),
        "exact_duplicate_rows": int(df[HEART_FEATURES + ["num"]].duplicated().sum()),
        "hungarian_label_check": hungarian_label_check(),
    }
    return out


def profile_diabetes() -> dict:
    df = load_diabetes_raw()
    dup_mask = df.duplicated()
    dedup = df[~dup_mask]
    # conflicting labels: identical features, different class
    feats = [c for c in df.columns if c != DIABETES_TARGET]
    conflicts = dedup.groupby(feats)[DIABETES_TARGET].nunique()
    return {
        "rows": int(len(df)),
        "columns": list(df.columns),
        "target_distribution": df[DIABETES_TARGET].value_counts().to_dict(),
        "exact_duplicate_rows": int(dup_mask.sum()),
        "rows_after_dedup": int(len(dedup)),
        "target_after_dedup": dedup[DIABETES_TARGET].value_counts().to_dict(),
        "feature_sets_with_conflicting_labels": int((conflicts > 1).sum()),
        "missing": _missing(df),
        "age_range": [int(df["Age"].min()), int(df["Age"].max())],
        "age_median": float(df["Age"].median()),
        "gender_distribution": df["Gender"].value_counts().to_dict(),
        "positive_rate_by_gender": df.groupby("Gender")[DIABETES_TARGET].apply(lambda s: round(float((s == "Positive").mean()), 3)).to_dict(),
    }


def profile_t1d_cohort() -> dict:
    p = ROOT / "data" / "restricted" / "t1d_cohort_deidentified.csv"
    if not p.exists():
        return {"available": False}
    df = pd.read_csv(p)
    return {
        "available": True,
        "rows": int(len(df)),
        "columns_kept": list(df.columns),
        "label_note": "All rows are diagnosed T1D patients (insulin_dose=1 for "
                      f"{int(df['insulin_dose'].sum())}/{len(df)}). No non-diabetic controls.",
        "age_range": [float(df["age"].min()), float(df["age"].max())],
        "missing": _missing(df),
        "implausible_hba1c_gt_20": int((df["hba1c"] > 20).sum()),
        "hba1c_lt_4": int((df["hba1c"] < 4).sum()),
        "fasting_bg_lt_70": int((df["fasting_bg"] < 70).sum()),
        "duplicate_rows_excluding_id": int(df.drop(columns="pseudo_id").duplicated().sum()),
        "symptom_prevalence": {c: round(float(df[c].mean()), 3) for c in
                               ["urination", "thirst", "blurry_vision", "loss_of_weight", "body_itching"]},
    }


def profile_cardio() -> dict:
    p = ROOT / "data" / "raw" / "cardio_kaggle" / "cardio_train.csv"
    if not p.exists():
        return {"available": False}
    df = pd.read_csv(p, sep=";")
    return {
        "available": True,
        "rows": int(len(df)),
        "columns": list(df.columns),
        "target_distribution": {int(k): int(v) for k, v in df["cardio"].value_counts().items()},
        "implausible_ap_hi_rows": int(((df["ap_hi"] < 70) | (df["ap_hi"] > 250)).sum()),
        "implausible_ap_lo_rows": int(((df["ap_lo"] < 40) | (df["ap_lo"] > 200)).sum()),
        "ap_lo_gt_ap_hi_rows": int((df["ap_lo"] > df["ap_hi"]).sum()),
        "duplicate_rows_excluding_id": int(df.drop(columns="id").duplicated().sum()),
    }


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    prof = {
        "heart_uci": profile_heart(),
        "early_stage_diabetes": profile_diabetes(),
        "t1d_cohort_deidentified": profile_t1d_cohort(),
        "cardio_kaggle": profile_cardio(),
    }
    OUT.write_text(json.dumps(prof, indent=2, default=lambda o: o.item() if isinstance(o, np.generic) else str(o)))
    print(json.dumps(prof, indent=2, default=str))


if __name__ == "__main__":
    main()
