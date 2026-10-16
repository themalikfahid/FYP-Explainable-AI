"""De-identify the local Type-1 Diabetes cohort spreadsheet.

The original workbook (PATIENT_DATA_T1D.xlsx) contains direct identifiers of
children (names, phone numbers, home addresses, photo flags) and family/caste
surnames recorded as "ethnicity". None of these are needed for analysis, so this
script keeps only clinical and symptom fields, normalises yes/no values, and
replaces the serial numbers with random pseudonymous IDs.

The original workbook is NEVER copied into this project. Run:

    python scripts/deidentify_t1d_cohort.py "C:/path/to/PATIENT_DATA_T1D.xlsx"

Output: data/restricted/t1d_cohort_deidentified.csv
"""
from __future__ import annotations

import re
import secrets
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "restricted" / "t1d_cohort_deidentified.csv"

DROP = ["SR. NO", "NAME", "PHONE NO.", "ADDRESS", "PICTURE", "ETHNICITY", "EDUCATION"]
YES_NO_COLS = [
    "FAMILY HISTORY", "CONSANGUINITY", "INSULIN DOSE", "URINATION", "THIRST", "BLURRY VISION",
    "JOINT PAIN", "LOSS OF WEIGHT", "BODY ITCHING", "DIZZINESS", "BLINDNESS", "HYPERTENSION",
    "CARDIO DISEASE", "CONGENITAL HYPOTHYROIDISM", "LIVER DISEASE", "KIDNEY DISEASE",
    "EXOCRINE PANCREATIC DISEASE", "CONGENITAL GLAUCOMA", "SKELETAL DISEASE",
    "DEVELOPMENTAL DELAY", "FACIAL DYSMORPHISM",
]
NUMERIC_COLS = ["AGE", "WEIGHT", "HEIGHT", "FASTING BG", "HbA1c"]


def yes_no(v) -> float:
    """Map messy YES/NO strings to 1/0. Unknown or typo values become NaN."""
    if pd.isna(v):
        return np.nan
    s = str(v).strip().upper()
    if s.startswith("YES") or s in {"YS", "Y"}:
        return 1.0
    if s in {"NO", "N"}:
        return 0.0
    return np.nan  # e.g. "MO" typo is left as missing rather than guessed


def onset_years(v) -> float:
    """Age at onset in years. '2 month' -> 0.17. Unparseable -> NaN."""
    if pd.isna(v):
        return np.nan
    s = str(v).strip().lower()
    m = re.match(r"^([\d.]+)\s*(month|months)$", s)
    if m:
        return round(float(m.group(1)) / 12, 2)
    try:
        return float(s)
    except ValueError:
        return np.nan


def main(path: str) -> None:
    raw = pd.read_excel(path, header=None)
    header_row = raw.index[raw.iloc[:, 1].astype(str).str.upper().eq("NAME")][0]
    df = raw.iloc[header_row + 1 :].copy()
    df.columns = [str(c).strip() for c in raw.iloc[header_row]]
    df = df[df["NAME"].notna() | df["AGE"].notna()]  # drop blank rows
    df = df.drop(columns=[c for c in DROP if c in df.columns])
    for c in NUMERIC_COLS:
        df[c] = pd.to_numeric(df[c], errors="coerce")  # 'nill' -> NaN
    df["ONSET_YEARS"] = df.pop("ONSET").map(onset_years)
    for c in YES_NO_COLS:
        df[c] = df[c].map(yes_no)
    df.insert(0, "pseudo_id", [f"T1D-{secrets.token_hex(3).upper()}" for _ in range(len(df))])
    df.columns = [c.lower().replace(" ", "_").replace(".", "") for c in df.columns]
    df = df.sample(frac=1.0, random_state=7).reset_index(drop=True)  # break row-order linkage
    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT, index=False)
    print(f"Wrote {len(df)} de-identified rows, {df.shape[1]} columns -> {OUT}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
