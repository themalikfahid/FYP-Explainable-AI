"""Model registry and inference: loads the trained hybrid pipeline (plus its
RF/ANN components for transparency) and returns probabilities, risk level,
uncertainty notes and a SHAP explanation of the hybrid output."""
from __future__ import annotations

import json
import logging
import threading
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from ml.data import TASKS
from ml.explain import HybridExplainer, humanize

log = logging.getLogger("app.inference")


class ModelUnavailable(RuntimeError):
    pass


class TaskModel:
    def __init__(self, task: str, folder: Path):
        self.task = task
        meta_path = folder / "metadata.json"
        files = {n: folder / f"{n}.joblib" for n in ("hybrid", "random_forest", "ann")}
        missing = [p.name for p in [meta_path, folder / "shap_background.csv", *files.values()] if not p.exists()]
        if missing:
            raise ModelUnavailable(f"Model artifacts for '{task}' are missing: {', '.join(missing)}. "
                                   f"Run `python -m ml.train` first.")
        self.meta = json.loads(meta_path.read_text())
        import sklearn
        trained_with = self.meta.get("versions", {}).get("sklearn")
        if trained_with != sklearn.__version__:
            # pickled scikit-learn models are only reliable with the version that saved them
            raise ModelUnavailable(f"Model for '{task}' was trained with scikit-learn {trained_with} but "
                                   f"{sklearn.__version__} is installed. Install requirements.txt or retrain "
                                   f"with `python -m ml.train`.")
        self.features: list[str] = self.meta["features"]
        if self.features != TASKS[task]["features"]:
            raise ModelUnavailable(f"Feature schema mismatch for '{task}': retrain the model.")
        self.hybrid = joblib.load(files["hybrid"])
        self.rf = joblib.load(files["random_forest"])
        self.ann = joblib.load(files["ann"])
        self.classes = [int(c) for c in self.hybrid.classes_]
        if self.classes != self.meta["classes"]:
            raise ModelUnavailable(f"Class order mismatch for '{task}'")
        bg = pd.read_csv(folder / "shap_background.csv")
        self.explainer = HybridExplainer(self.hybrid, self.features, bg)
        self.global_shap = json.loads((folder / "global_shap.json").read_text()) \
            if (folder / "global_shap.json").exists() else None
        oof_path = folder / "oof_report.json"
        self.oof = json.loads(oof_path.read_text()) if oof_path.exists() else None
        self.version = f"{task}-hybrid-{self.meta['trained_at_utc']}"
        self.strategy = self.meta.get("hybrid_strategy", "stacking")
        if self.strategy == "stacking":
            self.strategy_text = "Hybrid RF + ANN (stacking with logistic-regression meta-model)"
        else:
            w = self.meta["best_params"]["hybrid"].get("weights", [0.5, 0.5])
            self.strategy_text = f"Hybrid RF + ANN (weighted soft voting, RF {w[0]:.1f} / ANN {w[1]:.1f})"
        self._lock = threading.Lock()

    # ---------------------------------------------------------------
    def _frame(self, features: dict) -> pd.DataFrame:
        row = {f: (np.nan if features.get(f) is None else float(features[f])) for f in self.features}
        return pd.DataFrame([row], columns=self.features).astype(float)

    def risk_score(self, proba: np.ndarray) -> float:
        if self.task in ("diabetes", "cad"):
            return float(proba[self.classes.index(1)])
        return float(1.0 - proba[self.classes.index(0)])  # P(any disease grade 1-4)

    def risk_level(self, score: float) -> str:
        th = self.meta["risk_thresholds"]
        if score >= th["high_at_or_above"]:
            return "high"
        if score < th["low_below"]:
            return "low"
        return "moderate"

    def confidence(self, p: np.ndarray, score: float) -> dict:
        """Confidence gate: the model answers only when its confidence reaches the threshold at which the
        cross-validated accuracy of confident predictions is >= 90% (see ml/oof_eval.py)."""
        conf = float(max(p)) if self.task in ("diabetes", "cad") else float(max(score, 1.0 - score))
        gate = (self.oof or {}).get("gate") or {}
        thr = gate.get("threshold")
        if thr is None:
            return {"tier": "unrated", "value": conf, "note": "No cross-validated gate is available for this model."}
        row = next((r for r in gate["table"] if abs(r["min_confidence"] - thr) < 1e-9), None)
        tier = "confident" if conf >= thr else "inconclusive"
        what = gate["decision"]
        if tier == "confident":
            note = (f"Confident result for {what}. In cross-validation, predictions at this confidence level or above "
                    f"were correct {row['accuracy']:.0%} of the time (they cover {row['coverage']:.0%} of cases).")
        else:
            note = (f"Inconclusive: the model is not confident enough for {what} (confidence {conf:.0%}, "
                    f"needs {thr:.0%}). Treat the score as a prompt for a clinical check, not as an answer.")
        base = self.oof["any_disease"] if self.task == "heart" else self.oof["overall"]
        return {"tier": tier, "value": conf, "threshold": thr, "decision": what,
                "expected_accuracy_if_confident": row["accuracy"] if row else None,
                "coverage_at_threshold": row["coverage"] if row else None,
                "overall_cv_accuracy": base["accuracy"], "note": note}

    def predict(self, features: dict, explain: bool = True) -> dict:
        X = self._frame(features)
        with self._lock:  # sklearn estimators are not guaranteed thread-safe for predict
            p = self.hybrid.predict_proba(X)[0]
            # component outputs taken from the hybrid's own fitted members (the exact inputs it combines)
            p_rf = self.hybrid.named_estimators_["rf"].predict_proba(X)[0]
            p_ann = self.hybrid.named_estimators_["ann"].predict_proba(X)[0]
            explanation = self.explainer.explain_one(X) if explain else None
        if p.shape[0] != len(self.classes) or not np.isclose(p.sum(), 1.0):
            raise RuntimeError("Invalid probability vector from model")
        pred_idx = int(np.argmax(p))
        pred_class = self.classes[pred_idx]
        score = self.risk_score(p)
        labels = self.meta["class_labels"]
        disagreement = float(np.max(np.abs(p_rf - p_ann)))

        warnings = []
        missing = [f for f in self.features if features.get(f) is None]
        if missing:
            names = [TASKS[self.task]["spec"][f]["label"] for f in missing]
            warnings.append("Not provided and filled with typical training values: " + ", ".join(names) +
                            ". Results are less reliable.")
        ranges = self.meta["feature_ranges_train"]
        oor = [TASKS[self.task]["spec"][f]["label"] for f in self.features
               if features.get(f) is not None and not (ranges[f]["min"] <= float(features[f]) <= ranges[f]["max"])]
        if oor:
            warnings.append("Outside the range seen in training data: " + ", ".join(oor) +
                            ". The model is extrapolating.")
        if disagreement > 0.30:
            warnings.append(f"The Random Forest and ANN components disagree by up to {disagreement:.0%} "
                            "on a class probability, so this estimate is uncertain.")
        top_p = float(p[pred_idx])
        if self.task == "heart" and top_p < 0.5:
            warnings.append(f"No disease grade is clearly favoured (top probability {top_p:.0%}); "
                            "treat the grade as uncertain and focus on the overall disease probability.")

        out = {
            "task": self.task,
            "predicted_class": pred_class,
            "predicted_label": labels[str(pred_class)],
            "probabilities": {str(c): float(p[i]) for i, c in enumerate(self.classes)},
            "risk_score": score,
            "risk_score_definition": {
                "diabetes": "estimated probability of a positive screen",
                "cad": "estimated probability of significant coronary artery disease (>=50% narrowing)",
            }.get(self.task, "estimated probability of any heart disease grade (1-4)"),
            "risk_level": self.risk_level(score),
            "risk_thresholds": self.meta["risk_thresholds"],
            "components": {
                "random_forest": {str(c): float(p_rf[i]) for i, c in enumerate(self.classes)},
                "ann": {str(c): float(p_ann[i]) for i, c in enumerate(self.classes)},
                "max_disagreement": disagreement,
            },
            "probability_note": ("Probabilities are model estimates from the hybrid RF + ANN ensemble. They "
                                 "were checked for calibration on a small held-out test set only "
                                 "(see Model information) and are not clinically validated risks."),
            "warnings": warnings,
            "confidence": self.confidence(p, score),
            "model": {"version": self.version, "production_model": self.strategy_text,
                      "test_metrics": _headline(self.meta),
                      "cross_validated": _oof_headline(self.oof, self.task)},
        }
        if explanation:
            label = labels[str(explanation["explained_class"])]
            explanation["summary"] = humanize(explanation["contributions"], TASKS[self.task]["spec"], label)
            if self.task == "heart":
                # SHAP for P(any disease) = -SHAP for P(class 0), by additivity
                s0 = explanation["per_class"]["0"]
                explanation["any_disease"] = {
                    "base_value": 1.0 - s0["base_value"],
                    "shap": {f: -v for f, v in s0["shap"].items()},
                }
            out["explanation"] = explanation
        return out


def _oof_headline(oof: dict | None, task: str) -> dict | None:
    if not oof:
        return None
    base = oof["any_disease"] if task == "heart" else oof["overall"]
    gate = oof.get("gate", {})
    row = next((r for r in gate.get("table", []) if gate.get("threshold") is not None
                and abs(r["min_confidence"] - gate["threshold"]) < 1e-9), None)
    return {"cv_accuracy": base["accuracy"], "cv_balanced_accuracy": base["balanced_accuracy"],
            "cv_roc_auc": base.get("roc_auc"), "gate_threshold": gate.get("threshold"),
            "confident_accuracy": row["accuracy"] if row else None, "confident_coverage": row["coverage"] if row else None}


def _headline(meta: dict) -> dict:
    m = meta["test_metrics"]["hybrid"]
    keys = ["accuracy", "f1_macro", "roc_auc", "roc_auc_ovr_macro", "any_disease_roc_auc", "brier", "ece_top_label"]
    return {k: m[k] for k in keys if k in m} | {"n_test": m["n"]}


class Registry:
    def __init__(self, models_dir: str):
        self.dir = Path(models_dir)
        self._models: dict[str, TaskModel] = {}
        self._errors: dict[str, str] = {}
        self._lock = threading.Lock()

    def load_all(self) -> None:
        for task in TASKS:
            try:
                self.get(task)
            except ModelUnavailable as e:
                log.error(str(e))

    def get(self, task: str) -> TaskModel:
        with self._lock:
            if task not in self._models:
                try:
                    self._models[task] = TaskModel(task, self.dir / task)
                    self._errors.pop(task, None)
                except ModelUnavailable as e:
                    self._errors[task] = str(e)
                    raise
                except Exception as e:  # corrupt pickle, version mismatch...
                    msg = f"Failed to load '{task}' model: {type(e).__name__}"
                    log.exception(msg)
                    self._errors[task] = msg
                    raise ModelUnavailable(msg) from e
            return self._models[task]

    def status(self) -> dict:
        return {t: ("loaded" if t in self._models else self._errors.get(t, "not loaded")) for t in TASKS}
