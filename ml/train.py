"""Train, tune and evaluate RF, ANN and the stacked RF+ANN hybrid for one or both tasks.

    python -m ml.train                 # both tasks
    python -m ml.train --task heart    # one task
    python -m ml.train --fast          # smaller grids / fewer repeats (smoke test)

Protocol (identical for all three models):
  1. Remove exact duplicate rows, then one stratified 80/20 train/test split (seed 42).
     The test set is not used for tuning, model selection or stacking.
  2. Hyperparameters for RF and ANN chosen by 5-fold stratified CV on TRAIN (macro-F1).
  3. Hybrid strategy chosen by 5-fold CV on TRAIN between
       (a) stacking: tuned RF + tuned ANN -> logistic regression on out-of-fold
           probabilities (meta C / class_weight tuned), and
       (b) weighted soft voting of tuned RF + tuned ANN (weight tuned).
  4. Repeated stratified CV (5 folds x 3 repeats) on TRAIN for a variance-aware comparison.
  5. All three refit on full TRAIN and evaluated once on TEST (+ bootstrap 95% CIs).
  6. Global SHAP for the hybrid on TEST rows; artifacts written to artifacts/models/<task>/.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import time
from datetime import datetime, timezone

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.base import clone
from sklearn.model_selection import (GridSearchCV, RepeatedStratifiedKFold, StratifiedKFold,
                                     cross_validate, train_test_split)

from ml import evaluate as ev
from ml.data import RAW, ROOT, TASKS, load_cad, load_diabetes, load_heart
from ml.explain import HybridExplainer, global_importance
from ml.pipelines import (ANN_GRID, HYBRID_GRID, RF_GRID, SEED, VOTING_GRID, build_ann, build_hybrid, build_rf,
                          build_voting)

MODELS_DIR = ROOT / "artifacts" / "models"
EVAL_DIR = ROOT / "artifacts" / "eval"
RISK_THRESHOLDS = {"low_below": 0.30, "high_at_or_above": 0.70}


def _sha256(path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_task(task: str):
    if task == "diabetes":
        X, y = load_diabetes()
        return X, y, None
    if task == "cad":
        X, y = load_cad()
        return X, y, None
    X, y, site = load_heart()
    return X, y, site


def run_task(task: str, fast: bool = False) -> dict:
    t0 = time.time()
    spec = TASKS[task]
    X, y, site = load_task(task)
    classes = spec["classes"]
    X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.2, stratify=y, random_state=SEED)
    print(f"[{task}] rows={len(X)} train={len(X_tr)} test={len(X_te)}")
    cv = StratifiedKFold(5, shuffle=True, random_state=SEED)
    scoring = "f1_macro"

    def grid(g):
        return {k: v[:1] for k, v in g.items()} if fast else g

    # --- 1. tune components on TRAIN only
    rf_search = GridSearchCV(build_rf(task), grid(RF_GRID), cv=cv, scoring=scoring, n_jobs=-1)
    rf_search.fit(X_tr, y_tr)
    ann_search = GridSearchCV(build_ann(task), grid(ANN_GRID), cv=cv, scoring=scoring, n_jobs=-1)
    ann_search.fit(X_tr, y_tr)
    rf_best, ann_best = rf_search.best_estimator_, ann_search.best_estimator_
    print(f"[{task}] RF best {rf_search.best_params_} cv={rf_search.best_score_:.3f}")
    print(f"[{task}] ANN best {ann_search.best_params_} cv={ann_search.best_score_:.3f}")

    # --- 2. choose the hybrid combination strategy (base models fixed at tuned params)
    stack_search = GridSearchCV(build_hybrid(clone(rf_best), clone(ann_best)), grid(HYBRID_GRID), cv=cv,
                                scoring=scoring, n_jobs=-1).fit(X_tr, y_tr)
    vote_search = GridSearchCV(build_voting(clone(rf_best), clone(ann_best)), grid(VOTING_GRID), cv=cv,
                               scoring=scoring, n_jobs=-1).fit(X_tr, y_tr)
    hybrid_candidates = {
        "stacking": {"cv_f1_macro": float(stack_search.best_score_), "params": stack_search.best_params_},
        "soft_voting": {"cv_f1_macro": float(vote_search.best_score_), "params": vote_search.best_params_},
    }
    strategy = max(hybrid_candidates, key=lambda k: hybrid_candidates[k]["cv_f1_macro"])
    hyb_search = stack_search if strategy == "stacking" else vote_search
    print(f"[{task}] Hybrid candidates {hybrid_candidates} -> {strategy}")

    models = {
        "random_forest": clone(rf_best),
        "ann": clone(ann_best),
        "hybrid": clone(hyb_search.best_estimator_),
    }

    # --- 3. repeated CV comparison on TRAIN
    rcv = RepeatedStratifiedKFold(n_splits=5, n_repeats=1 if fast else 3, random_state=SEED)
    cv_scoring = {"accuracy": "accuracy", "f1_macro": "f1_macro", "f1_weighted": "f1_weighted",
                  "roc_auc": "roc_auc" if len(classes) == 2 else "roc_auc_ovr"}
    cv_results = {}
    for name, m in models.items():
        r = cross_validate(clone(m), X_tr, y_tr, cv=rcv, scoring=cv_scoring, n_jobs=-1)
        cv_results[name] = {k: {"mean": float(np.mean(r[f"test_{k}"])), "std": float(np.std(r[f"test_{k}"])),
                                "folds": [float(v) for v in r[f"test_{k}"]]} for k in cv_scoring}
        print(f"[{task}] CV {name}: f1_macro {cv_results[name]['f1_macro']['mean']:.3f} "
              f"± {cv_results[name]['f1_macro']['std']:.3f}")

    # --- 4. fit on full TRAIN, evaluate once on TEST
    test_metrics, probas = {}, {}
    for name, m in models.items():
        m.fit(X_tr, y_tr)
        assert [int(c) for c in m.classes_] == classes, "class order mismatch"
        p = m.predict_proba(X_te)
        assert p.shape == (len(X_te), len(classes))
        assert np.allclose(p.sum(axis=1), 1.0)
        probas[name] = p
        tm = ev.compute_metrics(y_te.values, p, classes)
        tm["bootstrap_95ci"] = ev.bootstrap_ci(y_te.values, p, classes)
        tm["calibration_table"] = ev.calibration_table(y_te.values, p, classes)
        test_metrics[name] = tm
        print(f"[{task}] TEST {name}: acc {tm['accuracy']:.3f} f1_macro {tm['f1_macro']:.3f}")

    # --- 5. supplementary: leave-one-site-out for heart (hybrid only)
    site_results = None
    if site is not None and not fast:
        site_results = {}
        for s in sorted(site.unique()):
            tr, te = site != s, site == s
            m = clone(models["hybrid"]).fit(X[tr], y[tr])
            p = m.predict_proba(X[te])
            yt = y[te].values
            present = sorted(set(yt))
            site_results[s] = {
                "n": int(te.sum()),
                "accuracy": float((np.asarray(classes)[p.argmax(1)] == yt).mean()),
                "f1_macro_over_present_classes": float(
                    __import__("sklearn.metrics", fromlist=["f1_score"]).f1_score(
                        yt, np.asarray(classes)[p.argmax(1)], labels=present, average="macro", zero_division=0)),
                "any_disease_accuracy": float((((1 - p[:, 0]) >= 0.5).astype(int) == (yt > 0)).mean()),
            }
        print(f"[{task}] leave-one-site-out: {site_results}")

    # --- 6. artifacts
    out = MODELS_DIR / task
    out.mkdir(parents=True, exist_ok=True)
    for name, m in models.items():
        joblib.dump(m, out / f"{name}.joblib", compress=3)
    background = X_tr.sample(n=min(50, len(X_tr)), random_state=SEED)
    background.to_csv(out / "shap_background.csv", index=False)
    pd.DataFrame({"y_true": y_te.values,
                  **{f"{n}_p{c}": probas[n][:, i] for n in probas for i, c in enumerate(classes)}}
                 ).to_csv(out / "test_predictions.csv", index=False)

    # global SHAP of the hybrid on test rows
    t_shap = time.time()
    explainer = HybridExplainer(models["hybrid"], spec["features"], background)
    shap_rows = X_te.sample(n=min(len(X_te), 15 if fast else 120), random_state=SEED)
    values, base = explainer.shap_values(shap_rows)
    hyb_p = models["hybrid"].predict_proba(shap_rows)
    additivity = float(np.max(np.abs(base + values.sum(axis=1) - hyb_p)))
    gi = global_importance(values, spec["features"], classes)
    gi.update({"n_rows_explained": int(len(shap_rows)), "background_rows": int(len(background)),
               "max_additivity_error": additivity, "seconds": round(time.time() - t_shap, 1),
               "method": "PermutationExplainer on hybrid predict_proba"})
    (out / "global_shap.json").write_text(json.dumps(gi, indent=2))
    print(f"[{task}] global SHAP done in {gi['seconds']}s, additivity err {additivity:.2e}")

    # training-range info (used for out-of-range warnings at inference)
    ranges = {f: {"min": float(X_tr[f].min()), "max": float(X_tr[f].max())} for f in spec["features"]}

    files = sorted(p for p in (RAW).rglob("*") if p.is_file())
    meta = {
        "task": task,
        "title": spec["title"],
        "trained_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "features": spec["features"],
        "classes": classes,
        "class_labels": {str(k): v for k, v in spec["class_labels"].items()},
        "production_model": "hybrid",
        "hybrid_strategy": strategy,
        "hybrid_candidates": hybrid_candidates,
        "split": {"rows_after_dedup": int(len(X)), "train": int(len(X_tr)), "test": int(len(X_te)),
                  "test_size": 0.2, "stratified": True, "seed": SEED},
        "class_distribution_train": {str(k): int(v) for k, v in y_tr.value_counts().sort_index().items()},
        "class_distribution_test": {str(k): int(v) for k, v in y_te.value_counts().sort_index().items()},
        "best_params": {"random_forest": rf_search.best_params_, "ann": ann_search.best_params_,
                        "hybrid": hyb_search.best_params_},
        "inner_cv_best_f1_macro": {"random_forest": rf_search.best_score_, "ann": ann_search.best_score_,
                                   "hybrid": hyb_search.best_score_},
        "cv_train_repeated": cv_results,
        "test_metrics": test_metrics,
        "leave_one_site_out_hybrid": site_results,
        "risk_thresholds": RISK_THRESHOLDS,
        "feature_ranges_train": ranges,
        "versions": {"python": platform.python_version(), "sklearn": sklearn.__version__,
                     "numpy": np.__version__, "pandas": pd.__version__},
        "data_sha256": {str(p.relative_to(ROOT)): _sha256(p) for p in files if task in str(p) or
                        (task == "diabetes" and "early_stage" in str(p)) or (task == "heart" and "heart_uci" in str(p)) or
                        (task == "cad" and "z_alizadeh" in str(p))},
        "fast_mode": fast,
        "train_seconds": round(time.time() - t0, 1),
    }
    (out / "metadata.json").write_text(json.dumps(meta, indent=2, default=str))

    # plots
    EVAL_DIR.mkdir(parents=True, exist_ok=True)
    labels = [str(c) for c in classes]
    for name in models:
        ev.plot_confusion(test_metrics[name]["confusion_matrix"], labels, f"{task} - {name} (test)",
                          EVAL_DIR / f"{task}_{name}_confusion.png")
    ev.plot_roc(y_te.values, probas, classes,
                f"{task} ROC (test){' - any disease vs none' if len(classes) > 2 else ''}",
                EVAL_DIR / f"{task}_roc.png")
    ev.plot_calibration({n: test_metrics[n]["calibration_table"] for n in models},
                        f"{task} reliability (top-class, test)", EVAL_DIR / f"{task}_calibration.png")
    ev.plot_global_shap(gi, spec["spec"], f"{task}: global SHAP importance of the hybrid (test rows)",
                        EVAL_DIR / f"{task}_global_shap.png")
    print(f"[{task}] finished in {meta['train_seconds']}s")
    return meta


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", choices=["diabetes", "heart", "cad", "all"], default="all")
    ap.add_argument("--fast", action="store_true")
    a = ap.parse_args()
    tasks = ["diabetes", "heart", "cad"] if a.task == "all" else [a.task]
    for t in tasks:
        run_task(t, fast=a.fast)


if __name__ == "__main__":
    main()
