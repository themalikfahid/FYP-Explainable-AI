"""ML pipeline tests: data, leakage safety, artifacts, inference, evaluation, SHAP."""
import json

import joblib
import numpy as np
import pandas as pd
import pytest
from sklearn.model_selection import train_test_split

from ml import evaluate as ev
from ml.data import DIABETES_FEATURES, HEART_FEATURES, TASKS, load_diabetes, load_heart
from ml.explain import HybridExplainer
from ml.pipelines import SEED, build_ann, build_hybrid, build_rf, build_voting
from tests.conftest import HEART_HIGH, HIGH_RISK_DIABETES, MODELS_DIR, require_models


# ------------------------------------------------------------------- data
def test_diabetes_loader_dedup_and_schema():
    X, y = load_diabetes()
    assert list(X.columns) == DIABETES_FEATURES
    assert len(X) == 251 and not pd.concat([X, y], axis=1).duplicated().any()
    assert set(y.unique()) == {0, 1} and X.isna().sum().sum() == 0
    assert set(np.unique(X.drop(columns="age").values)) <= {0.0, 1.0}


def test_heart_loader_graded_labels_and_cleaning():
    X, y, site = load_heart()
    assert list(X.columns) == HEART_FEATURES
    assert sorted(y.unique()) == [0, 1, 2, 3, 4]
    assert sorted(y[site == "hungarian"].unique()) == [0, 1, 2, 3, 4]  # recovered from raw 76-attr file
    assert (X["chol"].dropna() > 0).all() and (X["trestbps"].dropna() > 0).all()
    assert not pd.concat([X, y], axis=1).duplicated().any()


# -------------------------------------------------------------- leakage
def test_preprocessing_fitted_on_training_fold_only():
    X, y, _ = load_heart()
    X_tr, X_te, y_tr, _ = train_test_split(X, y, test_size=0.2, stratify=y, random_state=SEED)
    m = build_ann("heart", max_iter=20).fit(X_tr, y_tr)
    num = m.named_steps["prep"].named_transformers_["num"]
    medians = num.named_steps["impute"].statistics_
    feats = TASKS["heart"]["numeric_features"]
    assert np.allclose(medians, X_tr[feats].median().values)
    assert not np.allclose(medians, X[feats].median().values)  # would match if fitted on all data
    assert np.allclose(num.named_steps["scale"].mean_, X_tr[feats].fillna(X_tr[feats].median()).mean().values)


def test_stacking_uses_out_of_fold_cv():
    h = build_hybrid(build_rf("heart"), build_ann("heart"))
    assert h.cv.get_n_splits() == 5 and h.stack_method == "predict_proba" and h.passthrough is False


@pytest.mark.parametrize("task,loader", [("diabetes", load_diabetes), ("heart", lambda: load_heart()[:2])])
@pytest.mark.parametrize("kind", ["stacking", "voting"])
def test_hybrid_probability_shape_and_class_order(task, loader, kind):
    X, y = loader()
    X_tr, X_te, y_tr, _ = train_test_split(X, y, test_size=0.2, stratify=y, random_state=SEED)
    rf, ann = build_rf(task, n_estimators=30), build_ann(task, max_iter=50)
    h = build_hybrid(rf, ann) if kind == "stacking" else build_voting(rf, ann)
    h.fit(X_tr, y_tr)
    p = h.predict_proba(X_te)
    assert [int(c) for c in h.classes_] == TASKS[task]["classes"]
    assert p.shape == (len(X_te), len(TASKS[task]["classes"]))
    assert np.allclose(p.sum(1), 1) and (p >= 0).all()


# -------------------------------------------------------------- evaluation
def test_metrics_on_known_example():
    y = np.array([0, 0, 1, 1])
    perfect = np.array([[.9, .1], [.8, .2], [.1, .9], [.3, .7]])
    m = ev.compute_metrics(y, perfect, [0, 1])
    assert m["accuracy"] == 1 and m["f1_macro"] == 1 and m["roc_auc"] == 1
    assert m["confusion_matrix"] == [[2, 0], [0, 2]]
    assert m["brier"] == pytest.approx(np.mean([2 * .1 ** 2, 2 * .2 ** 2, 2 * .1 ** 2, 2 * .3 ** 2]))
    # ECE: confidences .9,.8,.9,.7 all correct -> |1-conf| weighted = mean(.1,.2,.1,.3)
    assert m["ece_top_label"] == pytest.approx(0.175)
    wrong = perfect[:, ::-1]
    assert ev.compute_metrics(y, wrong, [0, 1])["accuracy"] == 0


def test_multiclass_metrics_any_disease():
    y = np.array([0, 1, 2, 3, 4, 0])
    p = np.eye(5)[[0, 1, 2, 3, 4, 1]] * 0.9 + 0.02
    m = ev.compute_metrics(y, p, [0, 1, 2, 3, 4])
    assert m["accuracy"] == pytest.approx(5 / 6)
    assert m["any_disease_accuracy"] == pytest.approx(5 / 6) and m["any_disease_sensitivity"] == 1.0
    assert set(m["per_class"]) == {"0", "1", "2", "3", "4"}


# ------------------------------------------------------------- artifacts
@pytest.mark.parametrize("task", ["diabetes", "heart"])
def test_artifacts_reproduce_saved_test_predictions_and_metrics(task):
    """Serialised models reload and reproduce the stored test probabilities; the
    metrics in metadata.json are recomputable from those predictions."""
    require_models()
    folder = MODELS_DIR / task
    meta = json.loads((folder / "metadata.json").read_text())
    assert meta["features"] == TASKS[task]["features"] and meta["classes"] == TASKS[task]["classes"]
    X, y = (load_diabetes() if task == "diabetes" else load_heart()[:2])
    _, X_te, _, y_te = train_test_split(X, y, test_size=0.2, stratify=y, random_state=SEED)
    saved = pd.read_csv(folder / "test_predictions.csv")
    assert (saved["y_true"].values == y_te.values).all()
    for name in ("random_forest", "ann", "hybrid"):
        model = joblib.load(folder / f"{name}.joblib")
        p = model.predict_proba(X_te)
        cols = [f"{name}_p{c}" for c in meta["classes"]]
        assert np.allclose(p, saved[cols].values, atol=1e-9)
        recomputed = ev.compute_metrics(y_te.values, p, meta["classes"])
        for k in ("accuracy", "f1_macro", "f1_weighted", "brier"):
            assert recomputed[k] == pytest.approx(meta["test_metrics"][name][k])


def test_metadata_records_honest_protocol():
    require_models()
    for task in ("diabetes", "heart"):
        meta = json.loads((MODELS_DIR / task / "metadata.json").read_text())
        assert meta["split"]["train"] + meta["split"]["test"] == meta["split"]["rows_after_dedup"]
        assert meta["fast_mode"] is False
        assert meta["hybrid_strategy"] in ("stacking", "soft_voting")
        assert set(meta["test_metrics"]) == {"random_forest", "ann", "hybrid"}


# ------------------------------------------------------------------ SHAP
@pytest.mark.parametrize("task,row", [("diabetes", HIGH_RISK_DIABETES), ("heart", HEART_HIGH)])
def test_shap_explains_hybrid_output_additively(task, row):
    require_models()
    folder = MODELS_DIR / task
    model = joblib.load(folder / "hybrid.joblib")
    bg = pd.read_csv(folder / "shap_background.csv")
    exp = HybridExplainer(model, TASKS[task]["features"], bg)
    x = pd.DataFrame([row])[TASKS[task]["features"]].astype(float)
    out = exp.explain_one(x)
    p = model.predict_proba(x)[0]
    assert out["explained_class"] == model.classes_[np.argmax(p)]
    assert out["predicted_probability"] == pytest.approx(p.max())
    assert out["additivity_error"] < 1e-6
    for c, d in out["per_class"].items():
        k = list(model.classes_).index(int(c))
        assert d["base_value"] + sum(d["shap"].values()) == pytest.approx(p[k], abs=1e-6)
    assert {c["feature"] for c in out["contributions"]} == set(TASKS[task]["features"])
    # sorted by absolute contribution
    mags = [abs(c["shap"]) for c in out["contributions"]]
    assert mags == sorted(mags, reverse=True)


def test_shap_with_missing_optional_inputs():
    require_models()
    folder = MODELS_DIR / "heart"
    model = joblib.load(folder / "hybrid.joblib")
    exp = HybridExplainer(model, HEART_FEATURES, pd.read_csv(folder / "shap_background.csv"))
    row = {**HEART_HIGH, "ca": None, "thal": None, "chol": None}
    out = exp.explain_one(pd.DataFrame([row])[HEART_FEATURES].astype(float))
    assert out["additivity_error"] < 1e-6
    assert next(c for c in out["contributions"] if c["feature"] == "ca")["value"] is None
