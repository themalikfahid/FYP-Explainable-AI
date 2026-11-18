"""ECG heartbeat classifier (MIT-BIH Arrhythmia, Kaggle "ECG Heartbeat Categorization" version).

    python -m ml.ecg [--data-dir PATH]

Data: mitbih_train.csv (87,554 beats) and mitbih_test.csv (21,892 beats). Each row is one heartbeat
resampled to 187 samples (values scaled to 0-1) plus a class label (AAMI classes):
  0 N normal, 1 S supraventricular ectopic, 2 V ventricular ectopic, 3 F fusion, 4 Q unknown/paced.

Protocol: the official test file is touched once, at the end. The training file is split 85/15
(stratified); the hybrid (Random Forest + ANN, equal-weight soft voting) is fit on the 85%, the confidence
gate threshold is chosen on the 15% validation part, and everything reported in test_report.json is
measured on the untouched test file. The normal class is capped at 30,000 training beats to keep
training fast; no class weighting or oversampling is used, so probabilities stay realistic.
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import time
import warnings
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.ensemble import RandomForestClassifier, VotingClassifier
from sklearn.metrics import (accuracy_score, balanced_accuracy_score, confusion_matrix, f1_score,
                             precision_recall_fscore_support)
from sklearn.model_selection import train_test_split
from sklearn.neural_network import MLPClassifier

from ml.data import RAW, ROOT

warnings.filterwarnings("ignore")
OUT = ROOT / "artifacts" / "models" / "ecg"
SEED = 42
N_SAMPLES = 187
CLASSES = [0, 1, 2, 3, 4]
CLASS_LABELS = {
    0: "Normal beat",
    1: "Supraventricular ectopic beat",
    2: "Ventricular ectopic beat",
    3: "Fusion beat",
    4: "Unclassifiable / paced beat",
}
CLASS_SHORT = {0: "Normal", 1: "Supraventricular", 2: "Ventricular", 3: "Fusion", 4: "Unknown/paced"}
NORMAL_CAP = 30000
GATE_TARGET = 0.99
GRID = [0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 0.99]


def data_dir(arg: str | None = None) -> Path:
    for c in (arg, os.environ.get("ECG_DATA_DIR"), RAW / "mitbih", ROOT.parent / "Datasets"):
        if c and (Path(c) / "mitbih_train.csv").exists():
            return Path(c)
    raise FileNotFoundError("mitbih_train.csv / mitbih_test.csv not found. Pass --data-dir, set ECG_DATA_DIR, or "
                            "unzip the Kaggle archive into data/raw/mitbih/.")


def load(path: Path, name: str) -> tuple[np.ndarray, np.ndarray]:
    a = pd.read_csv(path / name, header=None, dtype=np.float32).values
    return a[:, :N_SAMPLES], a[:, N_SAMPLES].astype(int)


def build() -> VotingClassifier:
    rf = RandomForestClassifier(150, min_samples_leaf=1, n_jobs=-1, random_state=SEED)
    ann = MLPClassifier((128, 64), alpha=1e-3, max_iter=200, early_stopping=True, random_state=SEED)
    return VotingClassifier([("rf", rf), ("ann", ann)], voting="soft", weights=[1, 1])


def gate_table(conf: np.ndarray, correct: np.ndarray) -> tuple[list[dict], float | None]:
    rows, chosen = [], None
    for t in GRID:
        m = conf >= t
        if m.sum() < 30:
            continue
        acc = float(correct[m].mean())
        rows.append({"min_confidence": t, "coverage": float(m.mean()), "accuracy": acc, "n": int(m.sum())})
        if chosen is None and acc >= GATE_TARGET:
            chosen = t
    return rows, chosen


def metrics(y, P) -> dict:
    pred = P.argmax(1)
    pr, rc, f1, sup = precision_recall_fscore_support(y, pred, labels=CLASSES, zero_division=0)
    return {
        "n": int(len(y)), "accuracy": float(accuracy_score(y, pred)),
        "balanced_accuracy": float(balanced_accuracy_score(y, pred)),
        "f1_macro": float(f1_score(y, pred, average="macro")),
        "per_class": {str(c): {"label": CLASS_SHORT[c], "precision": float(pr[i]), "recall": float(rc[i]),
                               "f1": float(f1[i]), "support": int(sup[i])} for i, c in enumerate(CLASSES)},
        "confusion_matrix": confusion_matrix(y, pred, labels=CLASSES).tolist(),
    }


def main(dir_arg: str | None = None) -> None:
    t0 = time.time()
    d = data_dir(dir_arg)
    Xtr, ytr = load(d, "mitbih_train.csv")
    Xte, yte = load(d, "mitbih_test.csv")
    rng = np.random.RandomState(SEED)
    keep = np.concatenate([rng.choice(np.where(ytr == c)[0], min(NORMAL_CAP, int((ytr == c).sum())), replace=False)
                           if c == 0 else np.where(ytr == c)[0] for c in CLASSES])
    Xtr, ytr = Xtr[keep], ytr[keep]
    Xfit, Xval, yfit, yval = train_test_split(Xtr, ytr, test_size=0.15, stratify=ytr, random_state=SEED)
    print("fit", Xfit.shape, "val", Xval.shape, "test", Xte.shape)

    model = build().fit(Xfit, yfit)
    Pv = model.predict_proba(Xval)
    vrows, thr = gate_table(Pv.max(1), Pv.argmax(1) == yval)
    Pt = model.predict_proba(Xte)
    parts = {n: m.predict_proba(Xte) for n, m in model.named_estimators_.items()}
    test = {"hybrid": metrics(yte, Pt), "random_forest": metrics(yte, parts["rf"]), "ann": metrics(yte, parts["ann"])}
    trows, _ = gate_table(Pt.max(1), Pt.argmax(1) == yte)
    # abnormal-vs-normal screen (any non-normal class): what a screening user cares about
    yb, pb = (yte > 0).astype(int), 1 - Pt[:, 0]
    abn = {"accuracy": float(((pb >= .5) == yb).mean()),
           "sensitivity": float(((pb >= .5) & (yb == 1)).sum() / (yb == 1).sum()),
           "specificity": float(((pb < .5) & (yb == 0)).sum() / (yb == 0).sum())}

    OUT.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, OUT / "hybrid.joblib", compress=3)
    samples = {}
    for c in CLASSES:  # one confidently, correctly classified real test beat per class, for the demo buttons
        ok = np.where((yte == c) & (Pt.argmax(1) == c))[0]
        i = ok[np.argmax(Pt[ok, c])] if len(ok) else np.where(yte == c)[0][0]
        samples[str(c)] = {"label": CLASS_SHORT[c], "beat": [round(float(v), 4) for v in Xte[i]]}
    (OUT / "samples.json").write_text(json.dumps(samples))
    report = {
        "task": "ecg", "dataset": "MIT-BIH Arrhythmia (Kaggle ECG Heartbeat Categorization)",
        "n_train_fit": int(len(yfit)), "n_validation": int(len(yval)), "n_test": int(len(yte)),
        "test": test, "abnormal_vs_normal": abn,
        "gate": {"decision": "heartbeat class", "target_accuracy": GATE_TARGET, "threshold": thr,
                 "validation_table": vrows, "test_table": trows},
        "class_distribution_test": {str(c): int((yte == c).sum()) for c in CLASSES},
    }
    (OUT / "test_report.json").write_text(json.dumps(report, indent=2))
    meta = {"trained_at_utc": datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"), "classes": CLASSES,
            "class_labels": {str(k): v for k, v in CLASS_LABELS.items()},
            "class_short": {str(k): v for k, v in CLASS_SHORT.items()}, "n_samples": N_SAMPLES,
            "gate_threshold": thr, "seed": SEED, "hybrid": "soft voting RF(150) + ANN(128,64), equal weights",
            "versions": {"python": platform.python_version(), "sklearn": sklearn.__version__}}
    (OUT / "metadata.json").write_text(json.dumps(meta, indent=2))
    h = test["hybrid"]
    print(f"TEST hybrid acc {h['accuracy']:.4f} bal {h['balanced_accuracy']:.4f} f1 {h['f1_macro']:.4f}; "
          f"RF {test['random_forest']['accuracy']:.4f} ANN {test['ann']['accuracy']:.4f}; gate {thr}; "
          f"abnormal screen {abn}; {time.time()-t0:.0f}s")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir")
    main(ap.parse_args().data_dir)
