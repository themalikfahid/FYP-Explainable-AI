"""ECG heartbeat classifier service (MIT-BIH hybrid RF + ANN). Loaded lazily, once per process.

Explanation method: occlusion saliency. The 187-sample beat is split into 17 windows; each window is
flattened to the baseline (0) in turn and the drop in the predicted class probability is recorded.
It shows which part of the beat the model relied on. It is a model-behaviour explanation, not proof of
a physiological cause."""
from __future__ import annotations

import json
import threading
from pathlib import Path

import joblib
import numpy as np

N = 187
WINDOW = 11  # 17 windows cover 187 samples


class EcgUnavailable(RuntimeError):
    pass


class EcgModel:
    def __init__(self, folder: Path):
        need = [folder / n for n in ("hybrid.joblib", "metadata.json", "test_report.json", "samples.json")]
        missing = [p.name for p in need if not p.exists()]
        if missing:
            raise EcgUnavailable(f"ECG model artifacts missing: {', '.join(missing)}. Run `python -m ml.ecg`.")
        self.meta = json.loads((folder / "metadata.json").read_text())
        import sklearn
        if self.meta["versions"]["sklearn"] != sklearn.__version__:
            raise EcgUnavailable("ECG model was trained with a different scikit-learn version; retrain with `python -m ml.ecg`.")
        self.model = joblib.load(folder / "hybrid.joblib")
        self.report = json.loads((folder / "test_report.json").read_text())
        self.samples = json.loads((folder / "samples.json").read_text())
        self.classes = self.meta["classes"]
        self.labels = self.meta["class_labels"]
        self.short = self.meta["class_short"]
        self.threshold = self.meta.get("gate_threshold")
        self._lock = threading.Lock()

    def _proba(self, X: np.ndarray) -> np.ndarray:
        with self._lock:
            return self.model.predict_proba(X)

    def classify(self, beat: list[float]) -> dict:
        x = np.asarray(beat, dtype=np.float32)[None, :]
        p = self._proba(x)[0]
        top = int(np.argmax(p))
        conf = float(p[top])
        # saliency by occlusion
        starts = list(range(0, N, WINDOW))
        occl = np.repeat(x, len(starts), axis=0)
        for i, s in enumerate(starts):
            occl[i, s:s + WINDOW] = 0.0
        drops = p[top] - self._proba(occl)[:, top]
        saliency = [{"start": s, "end": min(s + WINDOW, N), "importance": float(d)} for s, d in zip(starts, drops)]
        gate = self.report["gate"]
        row = next((r for r in gate["test_table"] if self.threshold is not None
                    and abs(r["min_confidence"] - self.threshold) < 1e-9), None)
        tier = "unrated" if self.threshold is None else ("confident" if conf >= self.threshold else "inconclusive")
        abnormal = float(1.0 - p[0])
        warnings = []
        if float(x.max()) > 1.0 or float(x.min()) < 0.0:
            warnings.append("Values outside 0-1 were given; the model expects beats scaled to 0-1.")
        if tier == "inconclusive":
            warnings.append(f"Confidence {conf:.0%} is below the {self.threshold:.0%} level needed for a reliable "
                            "call. Treat this as inconclusive.")
        return {
            "predicted_class": self.classes[top], "predicted_label": self.labels[str(self.classes[top])],
            "probabilities": {self.short[str(c)]: float(p[i]) for i, c in enumerate(self.classes)},
            "confidence": {"tier": tier, "value": conf, "threshold": self.threshold,
                           "expected_accuracy_if_confident": row["accuracy"] if row else None,
                           "coverage_at_threshold": row["coverage"] if row else None},
            "abnormal_probability": abnormal, "saliency": saliency, "warnings": warnings,
            "model_accuracy": {"test_accuracy": self.report["test"]["hybrid"]["accuracy"],
                               "balanced_accuracy": self.report["test"]["hybrid"]["balanced_accuracy"],
                               "n_test": self.report["n_test"]},
            "disclaimer": ("Educational research prototype trained on single-lead MIT-BIH beats. It classifies one "
                           "already-segmented heartbeat and is not a diagnosis or a substitute for a clinician or "
                           "a certified ECG device."),
        }


_model: EcgModel | None = None
_lock = threading.Lock()


def get_model(models_dir: str) -> EcgModel:
    global _model
    with _lock:
        if _model is None:
            _model = EcgModel(Path(models_dir) / "ecg")
        return _model
