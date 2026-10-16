"""Evaluation metrics and plots. Every reported number is computed here from
real held-out predictions; nothing is hard-coded."""
from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from sklearn.metrics import (  # noqa: E402
    accuracy_score, average_precision_score, balanced_accuracy_score, confusion_matrix,
    f1_score, precision_recall_fscore_support, precision_score, recall_score, roc_auc_score,
    roc_curve,
)
from sklearn.preprocessing import label_binarize  # noqa: E402


def expected_calibration_error(y_true, proba, classes, n_bins: int = 10) -> float:
    """Top-label ECE: |accuracy - confidence| averaged over equal-width bins."""
    conf = proba.max(axis=1)
    pred = np.asarray(classes)[proba.argmax(axis=1)]
    correct = (pred == np.asarray(y_true)).astype(float)
    bins = np.linspace(0, 1, n_bins + 1)
    ece = 0.0
    for lo, hi in zip(bins[:-1], bins[1:]):
        m = (conf > lo) & (conf <= hi)
        if m.any():
            ece += m.mean() * abs(correct[m].mean() - conf[m].mean())
    return float(ece)


def brier_multiclass(y_true, proba, classes) -> float:
    Y = label_binarize(y_true, classes=classes)
    if Y.shape[1] == 1:  # binary
        Y = np.hstack([1 - Y, Y])
    return float(np.mean(np.sum((proba - Y) ** 2, axis=1)))


def compute_metrics(y_true, proba, classes) -> dict:
    y_true = np.asarray(y_true)
    classes = list(classes)
    y_pred = np.asarray(classes)[proba.argmax(axis=1)]
    binary = len(classes) == 2
    m = {
        "n": int(len(y_true)),
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "balanced_accuracy": float(balanced_accuracy_score(y_true, y_pred)),
        "precision_macro": float(precision_score(y_true, y_pred, average="macro", zero_division=0)),
        "recall_macro": float(recall_score(y_true, y_pred, average="macro", zero_division=0)),
        "f1_macro": float(f1_score(y_true, y_pred, average="macro", zero_division=0)),
        "f1_weighted": float(f1_score(y_true, y_pred, average="weighted", zero_division=0)),
        "confusion_matrix": confusion_matrix(y_true, y_pred, labels=classes).tolist(),
        "brier": brier_multiclass(y_true, proba, classes),
        "ece_top_label": expected_calibration_error(y_true, proba, classes),
    }
    p, r, f, s = precision_recall_fscore_support(y_true, y_pred, labels=classes, zero_division=0)
    Y = label_binarize(y_true, classes=classes)
    per_class = {}
    for i, c in enumerate(classes):
        yc = (y_true == c).astype(int)
        entry = {"precision": float(p[i]), "recall": float(r[i]), "f1": float(f[i]), "support": int(s[i])}
        if 0 < yc.sum() < len(yc):
            entry["roc_auc_ovr"] = float(roc_auc_score(yc, proba[:, i]))
            entry["average_precision_ovr"] = float(average_precision_score(yc, proba[:, i]))
        per_class[str(c)] = entry
    m["per_class"] = per_class
    if binary:
        m["roc_auc"] = float(roc_auc_score(y_true, proba[:, 1]))
        m["average_precision"] = float(average_precision_score(y_true, proba[:, 1]))
        # sensitivity / specificity for the positive class at the 0.5 argmax threshold
        tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=classes).ravel()
        m["sensitivity"] = float(tp / (tp + fn)) if tp + fn else None
        m["specificity"] = float(tn / (tn + fp)) if tn + fp else None
    else:
        m["roc_auc_ovr_macro"] = float(roc_auc_score(y_true, proba, multi_class="ovr", average="macro", labels=classes))
        m["roc_auc_ovr_weighted"] = float(roc_auc_score(y_true, proba, multi_class="ovr", average="weighted", labels=classes))
        m["average_precision_macro"] = float(np.mean([v["average_precision_ovr"] for v in per_class.values()
                                                      if "average_precision_ovr" in v]))
        # clinically relevant collapse: any disease (1-4) vs none (0)
        any_true = (y_true > 0).astype(int)
        any_proba = 1 - proba[:, classes.index(0)]
        m["any_disease_roc_auc"] = float(roc_auc_score(any_true, any_proba))
        any_pred = (any_proba >= 0.5).astype(int)
        m["any_disease_accuracy"] = float(accuracy_score(any_true, any_pred))
        m["any_disease_sensitivity"] = float(recall_score(any_true, any_pred))
        m["any_disease_specificity"] = float(recall_score(1 - any_true, 1 - any_pred))
        _ = Y
    return m


def bootstrap_ci(y_true, proba, classes, n_boot: int = 1000, seed: int = 0) -> dict:
    """Percentile 95% CIs over test-set bootstrap resamples (stratification not
    enforced; resamples lacking a class are skipped for AUC)."""
    rng = np.random.default_rng(seed)
    y_true = np.asarray(y_true)
    classes = list(classes)
    keys = {"accuracy": [], "f1_macro": [], "auc": []}
    n = len(y_true)
    for _ in range(n_boot):
        idx = rng.integers(0, n, n)
        yt, pp = y_true[idx], proba[idx]
        yp = np.asarray(classes)[pp.argmax(axis=1)]
        keys["accuracy"].append(accuracy_score(yt, yp))
        keys["f1_macro"].append(f1_score(yt, yp, average="macro", labels=classes, zero_division=0))
        if len(np.unique(yt)) == len(classes):
            if len(classes) == 2:
                keys["auc"].append(roc_auc_score(yt, pp[:, 1]))
            else:
                keys["auc"].append(roc_auc_score(yt, pp, multi_class="ovr", average="macro", labels=classes))
    return {k: [float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))] for k, v in keys.items() if v}


def calibration_table(y_true, proba, classes, n_bins: int = 10) -> list[dict]:
    conf = proba.max(axis=1)
    pred = np.asarray(classes)[proba.argmax(axis=1)]
    correct = (pred == np.asarray(y_true)).astype(float)
    bins = np.linspace(0, 1, n_bins + 1)
    rows = []
    for lo, hi in zip(bins[:-1], bins[1:]):
        m = (conf > lo) & (conf <= hi)
        if m.any():
            rows.append({"bin": f"{lo:.1f}-{hi:.1f}", "count": int(m.sum()),
                         "mean_confidence": float(conf[m].mean()), "accuracy": float(correct[m].mean())})
    return rows


# ------------------------------------------------------------------ plots
def plot_confusion(cm, labels, title, path: Path):
    cm = np.asarray(cm)
    fig, ax = plt.subplots(figsize=(4.6, 4))
    ax.imshow(cm, cmap="Blues")
    ax.set_xticks(range(len(labels)), labels)
    ax.set_yticks(range(len(labels)), labels)
    ax.set_xlabel("Predicted")
    ax.set_ylabel("Actual")
    for i in range(cm.shape[0]):
        for j in range(cm.shape[1]):
            ax.text(j, i, cm[i, j], ha="center", va="center",
                    color="white" if cm[i, j] > cm.max() / 2 else "black")
    ax.set_title(title, fontsize=10)
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


def plot_roc(y_true, probas: dict, classes, title, path: Path):
    fig, ax = plt.subplots(figsize=(4.8, 4.2))
    y_true = np.asarray(y_true)
    for name, proba in probas.items():
        if len(classes) == 2:
            fpr, tpr, _ = roc_curve(y_true, proba[:, 1])
            auc = roc_auc_score(y_true, proba[:, 1])
        else:  # any-disease collapse for readability
            yt = (y_true > 0).astype(int)
            score = 1 - proba[:, list(classes).index(0)]
            fpr, tpr, _ = roc_curve(yt, score)
            auc = roc_auc_score(yt, score)
        ax.plot(fpr, tpr, label=f"{name} (AUC {auc:.3f})")
    ax.plot([0, 1], [0, 1], "--", color="grey", lw=0.8)
    ax.set_xlabel("False positive rate")
    ax.set_ylabel("True positive rate")
    ax.set_title(title, fontsize=10)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


def plot_calibration(rows_by_model: dict, title, path: Path):
    fig, ax = plt.subplots(figsize=(4.8, 4.2))
    ax.plot([0, 1], [0, 1], "--", color="grey", lw=0.8, label="Perfect calibration")
    for name, rows in rows_by_model.items():
        ax.plot([r["mean_confidence"] for r in rows], [r["accuracy"] for r in rows], marker="o", label=name)
    ax.set_xlabel("Mean predicted confidence (top class)")
    ax.set_ylabel("Observed accuracy")
    ax.set_title(title, fontsize=10)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


def plot_global_shap(importance: dict, spec: dict, title, path: Path, top: int = 13):
    items = list(importance["mean_abs_shap_overall"].items())[:top][::-1]
    fig, ax = plt.subplots(figsize=(6, 0.35 * len(items) + 1.2))
    ax.barh([spec.get(k, {}).get("label", k) for k, _ in items], [v for _, v in items], color="#2f6f8f")
    ax.set_xlabel("Mean |SHAP value| (probability units, averaged over classes)")
    ax.set_title(title, fontsize=10)
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)
