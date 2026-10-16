"""SHAP explanations of the *hybrid ensemble output* (not of a single component).

Method: shap.PermutationExplainer over the end-to-end prediction function
    raw feature vector -> preprocessing -> RF + ANN -> meta-model -> class probabilities
with an Independent (interventional) masker built from a fixed background
sample of training rows. Masked features are replaced by background values and
the full pipeline is re-run, so the attributions explain exactly the
probabilities shown to the user. Permutation SHAP values satisfy additivity:
    base_value[c] + sum_j shap[j, c] == predicted_probability[c]
which is checked in tests/ml/test_explain.py.

Values are in probability units (e.g. +0.12 = this feature moved the predicted
probability of the class up by 12 percentage points relative to the baseline).
They describe the model's behaviour, not medical causation.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import shap


class HybridExplainer:
    def __init__(self, model, feature_names: list[str], background: pd.DataFrame, seed: int = 0):
        self.model = model
        self.feature_names = list(feature_names)
        self.background = background[self.feature_names].astype(float)
        self.classes = [int(c) for c in model.classes_]
        masker = shap.maskers.Independent(self.background.values, max_samples=len(self.background))
        self._explainer = shap.PermutationExplainer(self._predict, masker, feature_names=self.feature_names,
                                                    seed=seed)
        self.max_evals = 10 * (2 * len(self.feature_names) + 1)

    def _predict(self, X: np.ndarray) -> np.ndarray:
        return self.model.predict_proba(pd.DataFrame(X, columns=self.feature_names))

    def shap_values(self, X: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
        """Return (values[n, features, classes], base_values[n, classes])."""
        exp = self._explainer(X[self.feature_names].astype(float).values, max_evals=self.max_evals,
                              silent=True)
        values = np.asarray(exp.values)
        base = np.asarray(exp.base_values)
        if values.ndim == 2:  # defensive: single-output models
            values, base = values[..., None], base[..., None]
        return values, base

    def explain_one(self, x: pd.DataFrame, target_class: int | None = None, top_k: int | None = None) -> dict:
        """Explain a single row. Returns contributions for every class plus a
        sorted list for the target class (default: predicted class)."""
        values, base = self.shap_values(x)
        proba = self._predict(x[self.feature_names].astype(float).values)[0]
        pred_idx = int(np.argmax(proba))
        t_idx = self.classes.index(target_class) if target_class is not None else pred_idx
        row = x[self.feature_names].iloc[0]
        contribs = []
        for j, f in enumerate(self.feature_names):
            v = row[f]
            contribs.append({
                "feature": f,
                "value": None if pd.isna(v) else float(v),
                "shap": float(values[0, j, t_idx]),
            })
        contribs.sort(key=lambda d: abs(d["shap"]), reverse=True)
        if top_k:
            contribs = contribs[:top_k]
        return {
            "method": "SHAP PermutationExplainer on the full RF+ANN hybrid pipeline (probability units)",
            "explained_class": self.classes[t_idx],
            "base_value": float(base[0, t_idx]),
            "predicted_probability": float(proba[t_idx]),
            "contributions": contribs,
            "per_class": {
                str(c): {"base_value": float(base[0, k]),
                         "shap": {f: float(values[0, j, k]) for j, f in enumerate(self.feature_names)}}
                for k, c in enumerate(self.classes)
            },
            "additivity_error": float(abs(base[0, t_idx] + values[0, :, t_idx].sum() - proba[t_idx])),
        }


def global_importance(values: np.ndarray, feature_names: list[str], classes: list[int]) -> dict:
    """Mean |SHAP| per feature, per class and averaged over classes."""
    mean_abs = np.abs(values).mean(axis=0)  # [features, classes]
    overall = mean_abs.mean(axis=1)
    order = np.argsort(-overall)
    return {
        "features_ranked": [feature_names[i] for i in order],
        "mean_abs_shap_overall": {feature_names[i]: float(overall[i]) for i in order},
        "mean_abs_shap_per_class": {str(c): {f: float(mean_abs[j, k]) for j, f in enumerate(feature_names)}
                                    for k, c in enumerate(classes)},
    }


def humanize(contributions: list[dict], spec: dict, class_label: str, n: int = 3) -> list[str]:
    """Plain-language summary sentences for the top contributions."""
    out = []
    for c in contributions[:n]:
        meta = spec.get(c["feature"], {})
        label = meta.get("label", c["feature"])
        val = c["value"]
        if val is None:
            shown = "not provided (filled with a typical value)"
        elif meta.get("options"):
            shown = next((o["label"] for o in meta["options"] if float(o["value"]) == val), str(val))
        else:
            unit = meta.get("unit", "")
            shown = f"{val:g} {unit}".strip()
        direction = "raised" if c["shap"] > 0 else "lowered"
        out.append(f"{label} = {shown} {direction} the estimated probability of '{class_label}' "
                   f"by {abs(c['shap']) * 100:.1f} percentage points.")
    return out
