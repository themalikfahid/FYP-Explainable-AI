"""Dataset loading and the single source of truth for feature schemas.

The FEATURE_SPECS dictionaries are used by:
  * training (feature names and order),
  * the backend (request validation, served to the frontend via /api/meta/features),
  * the frontend (forms are generated from the served spec),
so training and inference always share names, order, codes and units.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"

# ---------------------------------------------------------------- heart (UCI)
HEART_SITES = {
    "cleveland": "processed.cleveland.data",
    "hungarian": "hungarian.data",  # raw 76-attribute file: keeps graded 0-4 labels
    "hungarian_processed": "processed.hungarian.data",  # audit only: labels collapsed to 0/1
    "switzerland": "processed.switzerland.data",
    "va_long_beach": "processed.va.data",
}
HEART_FEATURES = ["age", "sex", "cp", "trestbps", "chol", "fbs", "restecg",
                  "thalach", "exang", "oldpeak", "slope", "ca", "thal"]
HEART_TARGET = "num"
HEART_CLASSES = [0, 1, 2, 3, 4]
HEART_CLASS_LABELS = {
    0: "No significant disease (<50% narrowing)",
    1: "Disease grade 1 (mildest)",
    2: "Disease grade 2",
    3: "Disease grade 3",
    4: "Disease grade 4 (most severe)",
}
HEART_CATEGORICAL = ["cp", "restecg", "slope", "thal"]   # one-hot encoded
HEART_BINARY = ["sex", "fbs", "exang"]
HEART_NUMERIC = ["age", "trestbps", "chol", "thalach", "oldpeak", "ca"]

HEART_SPEC: dict[str, dict] = {
    "age": {"label": "Age", "unit": "years", "type": "number", "min": 18, "max": 100, "required": True},
    "sex": {"label": "Sex", "type": "select", "required": True,
            "options": [{"value": 1, "label": "Male"}, {"value": 0, "label": "Female"}]},
    "cp": {"label": "Chest pain type", "type": "select", "required": True,
           "options": [{"value": 1, "label": "Typical angina"}, {"value": 2, "label": "Atypical angina"},
                       {"value": 3, "label": "Non-anginal pain"}, {"value": 4, "label": "No chest pain (asymptomatic)"}]},
    "trestbps": {"label": "Resting blood pressure (systolic)", "unit": "mm Hg", "type": "number", "min": 70, "max": 250, "required": True},
    "chol": {"label": "Serum cholesterol", "unit": "mg/dL", "type": "number", "min": 80, "max": 700, "required": False},
    "fbs": {"label": "Fasting blood sugar > 120 mg/dL", "type": "select", "required": True,
            "options": [{"value": 1, "label": "Yes"}, {"value": 0, "label": "No"}]},
    "restecg": {"label": "Resting ECG result", "type": "select", "required": True,
                "options": [{"value": 0, "label": "Normal"}, {"value": 1, "label": "ST-T wave abnormality"},
                            {"value": 2, "label": "Left ventricular hypertrophy"}]},
    "thalach": {"label": "Maximum heart rate achieved (exercise test)", "unit": "bpm", "type": "number", "min": 50, "max": 230, "required": True},
    "exang": {"label": "Exercise-induced angina", "type": "select", "required": True,
              "options": [{"value": 1, "label": "Yes"}, {"value": 0, "label": "No"}]},
    "oldpeak": {"label": "ST depression induced by exercise (oldpeak)", "unit": "mm", "type": "number", "min": -3, "max": 7, "step": 0.1, "required": True},
    "slope": {"label": "Slope of peak exercise ST segment", "type": "select", "required": False,
              "options": [{"value": 1, "label": "Upsloping"}, {"value": 2, "label": "Flat"}, {"value": 3, "label": "Downsloping"}]},
    "ca": {"label": "Major vessels coloured by fluoroscopy", "type": "select", "required": False,
           "options": [{"value": v, "label": str(v)} for v in (0, 1, 2, 3)]},
    "thal": {"label": "Thallium stress test", "type": "select", "required": False,
             "options": [{"value": 3, "label": "Normal"}, {"value": 6, "label": "Fixed defect"}, {"value": 7, "label": "Reversible defect"}]},
}


# 1-based attribute positions of the 14 standard attributes in the 76-attribute files
_RAW76_POSITIONS = [3, 4, 9, 10, 12, 16, 19, 32, 38, 40, 41, 44, 51, 58]


def parse_raw76(path: Path) -> pd.DataFrame:
    """Parse a 76-attribute UCI heart file (records span lines and end with 'name')."""
    tokens = path.read_text(encoding="latin-1").split()
    records, cur = [], []
    for t in tokens:
        cur.append(t)
        if t == "name":
            records.append(cur)
            cur = []
    rows = [[float(r[i - 1]) for i in _RAW76_POSITIONS] for r in records if len(r) == 76]
    return pd.DataFrame(rows, columns=HEART_FEATURES + [HEART_TARGET]).replace(-9.0, np.nan)


def load_heart_raw(clean_invalid: bool = True, include_audit_only: bool = False) -> pd.DataFrame:
    """Load and concatenate the four processed UCI files (14 attributes each).

    The Hungarian site is read from the raw 76-attribute file because the
    distributed processed.hungarian.data collapses disease grades 1-4 into 1
    (verified in ml/audit_datasets.py). '?' and -9 are missing-value markers. With clean_invalid=True, physiologically
    impossible zeros (chol == 0, trestbps == 0) become missing values; these zeros
    are recording artefacts (mostly the Switzerland site), not real measurements.
    """
    frames = []
    for site, fname in HEART_SITES.items():
        if site.endswith("_processed") and not include_audit_only:
            continue
        if fname.startswith("processed."):
            df = pd.read_csv(RAW / "heart_uci" / fname, header=None, names=HEART_FEATURES + [HEART_TARGET],
                             na_values="?")
        else:
            df = parse_raw76(RAW / "heart_uci" / fname)
        df["site"] = site
        frames.append(df)
    df = pd.concat(frames, ignore_index=True)
    df = df.apply(lambda c: pd.to_numeric(c, errors="coerce") if c.name != "site" else c)
    if clean_invalid:
        df.loc[df["chol"] == 0, "chol"] = np.nan
        df.loc[df["trestbps"] == 0, "trestbps"] = np.nan
    df[HEART_TARGET] = df[HEART_TARGET].astype(int)
    return df


def load_heart() -> tuple[pd.DataFrame, pd.Series, pd.Series]:
    """Return (X, y, site). Exact duplicates are removed before any split."""
    df = load_heart_raw(clean_invalid=True)
    df = df.drop_duplicates(subset=HEART_FEATURES + [HEART_TARGET]).reset_index(drop=True)
    return df[HEART_FEATURES].astype(float), df[HEART_TARGET], df["site"]


# ------------------------------------------------- early-stage diabetes (UCI)
DIABETES_TARGET = "class"
DIABETES_RAW_COLUMNS = ["Age", "Gender", "Polyuria", "Polydipsia", "sudden weight loss", "weakness",
                        "Polyphagia", "Genital thrush", "visual blurring", "Itching", "Irritability",
                        "delayed healing", "partial paresis", "muscle stiffness", "Alopecia", "Obesity"]
DIABETES_FEATURES = ["age", "gender_male", "polyuria", "polydipsia", "sudden_weight_loss", "weakness",
                     "polyphagia", "genital_thrush", "visual_blurring", "itching", "irritability",
                     "delayed_healing", "partial_paresis", "muscle_stiffness", "alopecia", "obesity"]
DIABETES_CLASSES = [0, 1]
DIABETES_CLASS_LABELS = {0: "Negative (screen negative)", 1: "Positive (diabetes-consistent symptom profile)"}

_YN = [{"value": 1, "label": "Yes"}, {"value": 0, "label": "No"}]
_SYMPTOM_HELP = {
    "polyuria": "Passing urine much more often or in larger amounts than usual",
    "polydipsia": "Excessive thirst",
    "sudden_weight_loss": "Unexplained, sudden weight loss",
    "weakness": "General weakness or fatigue",
    "polyphagia": "Excessive hunger",
    "genital_thrush": "Genital yeast infection",
    "visual_blurring": "Blurred vision",
    "itching": "Persistent itching",
    "irritability": "Unusual irritability",
    "delayed_healing": "Cuts or wounds heal slowly",
    "partial_paresis": "Partial muscle weakness / reduced ability to move",
    "muscle_stiffness": "Muscle stiffness",
    "alopecia": "Hair loss",
    "obesity": "Obesity (as recorded in the source dataset; BMI >= 30 is a common definition)",
}
DIABETES_SPEC: dict[str, dict] = {
    "age": {"label": "Age", "unit": "years", "type": "number", "min": 16, "max": 90, "required": True},
    "gender_male": {"label": "Sex", "type": "select", "required": True,
                    "options": [{"value": 1, "label": "Male"}, {"value": 0, "label": "Female"}]},
}
for _f in DIABETES_FEATURES[2:]:
    DIABETES_SPEC[_f] = {"label": _f.replace("_", " ").capitalize(), "help": _SYMPTOM_HELP[_f],
                         "type": "select", "required": True, "options": _YN}


def load_diabetes_raw() -> pd.DataFrame:
    return pd.read_csv(RAW / "early_stage_diabetes" / "diabetes_data_upload.csv")


def encode_diabetes(df: pd.DataFrame) -> pd.DataFrame:
    out = pd.DataFrame(index=df.index)
    out["age"] = df["Age"].astype(float)
    out["gender_male"] = (df["Gender"] == "Male").astype(float)
    for raw, new in zip(DIABETES_RAW_COLUMNS[2:], DIABETES_FEATURES[2:]):
        out[new] = (df[raw] == "Yes").astype(float)
    return out[DIABETES_FEATURES]


def load_diabetes() -> tuple[pd.DataFrame, pd.Series]:
    """Return (X, y) after removing the 269 exact duplicate rows.

    Duplicates are removed BEFORE splitting; otherwise identical records land in
    both train and test and inflate test scores.
    """
    df = load_diabetes_raw().drop_duplicates().reset_index(drop=True)
    y = (df[DIABETES_TARGET] == "Positive").astype(int)
    return encode_diabetes(df), y


# --------------------------------------------- coronary artery disease (Z-Alizadeh Sani, UCI)
CAD_FILE = RAW / "z_alizadeh_sani" / "z_alizadeh_sani.xlsx"
CAD_TARGET = "Cath"
# raw column -> model feature name (27 clinically practical screening inputs; the dataset has 54)
CAD_COLUMNS = {
    "Age": "age", "Sex": "sex", "BMI": "bmi", "DM": "diabetes_hx", "HTN": "hypertension",
    "Current Smoker": "current_smoker", "FH": "family_history", "DLP": "dyslipidemia", "BP": "bp_systolic",
    "PR": "pulse", "Typical Chest Pain": "typical_chest_pain", "Atypical": "atypical_chest_pain",
    "Nonanginal": "nonanginal_pain", "Dyspnea": "dyspnea", "Function Class": "function_class",
    "Q Wave": "q_wave", "St Elevation": "st_elevation", "St Depression": "st_depression",
    "Tinversion": "t_inversion", "LVH": "lvh", "FBS": "fbs_mgdl", "LDL": "ldl", "HDL": "hdl",
    "TG": "triglycerides", "ESR": "esr", "HB": "hemoglobin", "EF-TTE": "ef_tte",
}
CAD_FEATURES = list(CAD_COLUMNS.values())
CAD_CLASSES = [0, 1]
CAD_CLASS_LABELS = {0: "No significant coronary artery disease (<50% narrowing)",
                    1: "Coronary artery disease likely (>=50% narrowing)"}
CAD_NUMERIC = ["age", "bmi", "bp_systolic", "pulse", "function_class", "fbs_mgdl", "ldl", "hdl", "triglycerides",
               "esr", "hemoglobin", "ef_tte"]
CAD_BINARY = [f for f in CAD_FEATURES if f not in CAD_NUMERIC]
_CAD_FLAG_INFO = {
    "sex": ("Sex", None),
    "diabetes_hx": ("Diabetes (diagnosed)", "Previously diagnosed with diabetes mellitus"),
    "hypertension": ("High blood pressure (diagnosed)", "Diagnosed hypertension or on BP medication"),
    "current_smoker": ("Current smoker", "Smokes at present"),
    "family_history": ("Family history of heart disease", "Close relative with coronary artery disease"),
    "dyslipidemia": ("High cholesterol / lipids (diagnosed)", "Diagnosed dyslipidemia or on lipid-lowering treatment"),
    "typical_chest_pain": ("Typical chest pain (angina)", "Pressure-like chest pain brought on by effort and relieved by rest"),
    "atypical_chest_pain": ("Atypical chest pain", "Chest pain that only partly fits typical angina"),
    "nonanginal_pain": ("Non-anginal chest pain", "Chest pain unlikely to come from the heart"),
    "dyspnea": ("Shortness of breath", "Breathlessness on exertion or at rest"),
    "q_wave": ("Q wave on ECG", "Pathological Q wave on a resting ECG"),
    "st_elevation": ("ST elevation on ECG", "ST-segment elevation on a resting ECG"),
    "st_depression": ("ST depression on ECG", "ST-segment depression on a resting ECG"),
    "t_inversion": ("T-wave inversion on ECG", "Inverted T waves on a resting ECG"),
    "lvh": ("Left ventricular hypertrophy on ECG", "LVH criteria met on a resting ECG"),
}
CAD_SPEC: dict[str, dict] = {
    "age": {"label": "Age", "unit": "years", "type": "number", "min": 18, "max": 100, "required": True},
    "sex": {"label": "Sex", "type": "select", "required": True,
            "options": [{"value": 1, "label": "Male"}, {"value": 0, "label": "Female"}]},
    "bmi": {"label": "Body mass index", "unit": "kg/m²", "type": "number", "min": 12, "max": 60, "step": 0.1, "required": True},
    "bp_systolic": {"label": "Resting blood pressure (systolic)", "unit": "mm Hg", "type": "number", "min": 70, "max": 250, "required": True},
    "pulse": {"label": "Resting pulse", "unit": "bpm", "type": "number", "min": 30, "max": 200, "required": True},
    "function_class": {"label": "Functional class (NYHA)", "type": "select", "required": True,
                       "help": "How much daily activity causes symptoms: 0 none, 1 slight, 2 moderate, 3 marked limitation",
                       "options": [{"value": 0, "label": "0 - none"}, {"value": 1, "label": "1 - slight"},
                                   {"value": 2, "label": "2 - moderate"}, {"value": 3, "label": "3 - marked"}]},
    "fbs_mgdl": {"label": "Fasting blood glucose", "unit": "mg/dL", "type": "number", "min": 40, "max": 600, "required": False},
    "ldl": {"label": "LDL cholesterol", "unit": "mg/dL", "type": "number", "min": 10, "max": 400, "required": False},
    "hdl": {"label": "HDL cholesterol", "unit": "mg/dL", "type": "number", "min": 10, "max": 150, "required": False},
    "triglycerides": {"label": "Triglycerides", "unit": "mg/dL", "type": "number", "min": 20, "max": 2000, "required": False},
    "esr": {"label": "ESR (erythrocyte sedimentation rate)", "unit": "mm/h", "type": "number", "min": 0, "max": 150, "required": False},
    "hemoglobin": {"label": "Hemoglobin", "unit": "g/dL", "type": "number", "min": 5, "max": 20, "step": 0.1, "required": False},
    "ef_tte": {"label": "Ejection fraction (echocardiogram)", "unit": "%", "type": "number", "min": 10, "max": 80, "required": False},
}
for _f, (_label, _help) in _CAD_FLAG_INFO.items():
    if _f == "sex":
        continue
    CAD_SPEC[_f] = {"label": _label, "type": "select", "required": True, "options": _YN, **({"help": _help} if _help else {})}
CAD_SPEC = {f: CAD_SPEC[f] for f in CAD_FEATURES}


def load_cad() -> tuple[pd.DataFrame, pd.Series]:
    """Return (X, y). 303 patients, no duplicates or missing values in the source file."""
    df = pd.read_excel(CAD_FILE)
    out = pd.DataFrame(index=df.index)
    for raw, new in CAD_COLUMNS.items():
        col = df[raw]
        if new == "sex":
            col = (col.astype(str).str.strip().str.lower() == "male").astype(float)
        elif not pd.api.types.is_numeric_dtype(col):
            col = (col.astype(str).str.strip().str.upper().isin(["Y", "YES"])).astype(float)
        out[new] = col.astype(float)
    y = (df[CAD_TARGET].astype(str).str.strip().str.lower() == "cad").astype(int)
    keep = ~pd.concat([out, y.rename("y")], axis=1).duplicated()
    return out[keep].reset_index(drop=True), y[keep].reset_index(drop=True)


TASKS = {
    "diabetes": {
        "title": "Diabetes symptom-based risk screening (type not specified by the data)",
        "features": DIABETES_FEATURES, "spec": DIABETES_SPEC,
        "classes": DIABETES_CLASSES, "class_labels": DIABETES_CLASS_LABELS,
        "binary_features": DIABETES_FEATURES[1:], "numeric_features": ["age"], "categorical_features": [],
    },
    "heart": {
        "title": "Multiclass heart disease classification (UCI angiographic grade 0-4)",
        "features": HEART_FEATURES, "spec": HEART_SPEC,
        "classes": HEART_CLASSES, "class_labels": HEART_CLASS_LABELS,
        "binary_features": HEART_BINARY, "numeric_features": HEART_NUMERIC,
        "categorical_features": HEART_CATEGORICAL,
    },
    "cad": {
        "title": "Coronary artery disease screening (Z-Alizadeh Sani, angiography-confirmed)",
        "features": CAD_FEATURES, "spec": CAD_SPEC,
        "classes": CAD_CLASSES, "class_labels": CAD_CLASS_LABELS,
        "binary_features": CAD_BINARY, "numeric_features": CAD_NUMERIC, "categorical_features": [],
    },
}
