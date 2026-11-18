"""Out-of-fold (cross-validated) evaluation of the production hybrid on ALL de-duplicated records,
plus the confidence-gating ("selective prediction") table used by the app.

    python -m ml.oof_eval

Why this exists: the single 80/20 hold-out has only 51 (diabetes) / 184 (heart) rows, so a single
test score swings by several points. Repeated stratified 5-fold CV predicts every record while it
is held out, 3 times with different shuffles, so every number below is computed on data the model
did not see when predicting it. Hyper-parameters are the ones chosen earlier by train-only CV.

Selective prediction: the model abstains ("inconclusive") when its top probability is below a
threshold. The threshold is the lowest confidence at which the held-out accuracy of the confident
predictions is >= TARGET_ACCURACY. This is a legitimate, standard technique (reject option); it is
NOT the same as overall accuracy, and the app always reports both.
"""
from __future__ import annotations

import json
import time
import warnings

import joblib
import numpy as np
from sklearn.base import clone
from sklearn.metrics import (accuracy_score, balanced_accuracy_score, confusion_matrix, f1_score,
                             roc_auc_score)
from sklearn.model_selection import StratifiedKFold, cross_val_predict

from ml.data import ROOT, TASKS
from ml.pipelines import SEED
from ml.train import MODELS_DIR, load_task

warnings.filterwarnings("ignore")
TARGET_ACCURACY = {"diabetes": 0.95, "heart": 0.90, "cad": 0.95}  # accuracy the confident predictions must reach
REPEATS = 3
GRID = [0.5, 0.55, 0.6, 0.65, 0.7, 0.75, 0.8, 0.85, 0.9, 0.95]


def _oof_proba(model, X, y, repeats=REPEATS):
    P = 0
    for r in range(repeats):
        cv = StratifiedKFold(5, shuffle=True, random_state=SEED + r)
        P = P + cross_val_predict(clone(model), X, y, cv=cv, method="predict_proba", n_jobs=2)
    return P / repeats


def _gate(conf: np.ndarray, correct: np.ndarray, target: float) -> tuple[list[dict], float | None]:
    rows, chosen = [], None
    for t in GRID:
        m = conf >= t
        if m.sum() < 15:
            continue
        acc = float(correct[m].mean())
        rows.append({"min_confidence": t, "coverage": float(m.mean()), "accuracy": acc, "n": int(m.sum())})
        if chosen is None and acc >= target:
            chosen = t
    return rows, chosen


def evaluate_task(task: str) -> dict:
    spec = TASKS[task]
    X, y, _ = load_task(task)
    model = joblib.load(MODELS_DIR / task / "hybrid.joblib")
    classes = spec["classes"]
    t0 = time.time()
    P = _oof_proba(model, X, y)
    pred = np.asarray(classes)[P.argmax(1)]
    out = {
        "task": task, "n_records": int(len(y)), "repeats": REPEATS, "folds": 5, "target_accuracy": TARGET_ACCURACY[task],
        "overall": {
            "accuracy": float(accuracy_score(y, pred)),
            "balanced_accuracy": float(balanced_accuracy_score(y, pred)),
            "f1_macro": float(f1_score(y, pred, average="macro", zero_division=0)),
            "confusion_matrix": confusion_matrix(y, pred, labels=classes).tolist(),
        },
    }
    if task in ("diabetes", "cad"):
        conf = P.max(1)
        out["overall"]["roc_auc"] = float(roc_auc_score(y, P[:, 1]))
        rows, thr = _gate(conf, (pred == y.values), TARGET_ACCURACY[task])
        out["gate"] = {"decision": ("diabetes screen (positive vs negative)" if task == "diabetes" else "coronary artery disease screen (likely vs unlikely)"), "table": rows, "threshold": thr}
    else:
        any_p = 1 - P[:, 0]
        yb = (y.values > 0).astype(int)
        predb = (any_p >= 0.5).astype(int)
        out["any_disease"] = {
            "accuracy": float(accuracy_score(yb, predb)),
            "balanced_accuracy": float(balanced_accuracy_score(yb, predb)),
            "roc_auc": float(roc_auc_score(yb, any_p)),
            "sensitivity": float(((predb == 1) & (yb == 1)).sum() / (yb == 1).sum()),
            "specificity": float(((predb == 0) & (yb == 0)).sum() / (yb == 0).sum()),
            "confusion_matrix": confusion_matrix(yb, predb).tolist(),
        }
        conf_b = np.maximum(any_p, 1 - any_p)
        rows, thr = _gate(conf_b, predb == yb, TARGET_ACCURACY[task])
        out["gate"] = {"decision": "any heart disease (grades 1-4) vs none", "table": rows, "threshold": thr}
        rows5, thr5 = _gate(P.max(1), pred == y.values, 0.90)
        out["gate_grade"] = {"decision": "exact disease grade 0-4", "table": rows5, "threshold": thr5}
    out["seconds"] = round(time.time() - t0, 1)
    path = MODELS_DIR / task / "oof_report.json"
    path.write_text(json.dumps(out, indent=2))
    print(task, json.dumps({k: out[k] for k in out if k in ("overall", "any_disease")}, indent=1)[:900])
    print(task, "gate threshold", out["gate"]["threshold"], out["gate"]["table"])
    return out


if __name__ == "__main__":
    for t in TASKS:
        evaluate_task(t)
