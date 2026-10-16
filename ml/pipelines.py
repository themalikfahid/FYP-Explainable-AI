"""Model construction: preprocessing, Random Forest, ANN and the stacked hybrid.

Every estimator returned here is a full scikit-learn Pipeline whose first step is
the preprocessor. Because preprocessing lives inside the pipeline, any
cross-validation (tuning, stacking out-of-fold predictions, evaluation) refits
imputation / scaling / encoding on the training folds only. No statistics from a
validation or test fold ever reach the model.
"""
from __future__ import annotations

from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier, StackingClassifier, VotingClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from ml.data import TASKS

SEED = 42


def make_preprocessor(task: str, scale: bool) -> ColumnTransformer:
    t = TASKS[task]
    num_steps = [("impute", SimpleImputer(strategy="median"))]
    if scale:
        num_steps.append(("scale", StandardScaler()))
    transformers = []
    if t["numeric_features"]:
        transformers.append(("num", Pipeline(num_steps), t["numeric_features"]))
    if t["binary_features"]:
        transformers.append(("bin", SimpleImputer(strategy="most_frequent"), t["binary_features"]))
    if t["categorical_features"]:
        transformers.append(("cat", Pipeline([
            ("impute", SimpleImputer(strategy="most_frequent")),
            ("onehot", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
        ]), t["categorical_features"]))
    return ColumnTransformer(transformers, remainder="drop", verbose_feature_names_out=False)


def build_rf(task: str, **params) -> Pipeline:
    defaults = dict(n_estimators=300, class_weight="balanced_subsample", random_state=SEED, n_jobs=1)
    defaults.update(params)
    return Pipeline([("prep", make_preprocessor(task, scale=False)),
                     ("model", RandomForestClassifier(**defaults))])


def build_ann(task: str, **params) -> Pipeline:
    """Feed-forward ANN (multi-layer perceptron) with L2 penalty and an epoch cap.

    scikit-learn's MLPClassifier is used instead of TensorFlow/Keras: the
    datasets have 251 and 918 rows, so a small dense network is appropriate, and
    keeping it inside a scikit-learn Pipeline lets the stacking ensemble produce
    leakage-safe out-of-fold predictions without custom wrappers. Output layer is
    softmax (multiclass) / logistic (binary) trained with cross-entropy loss.

    Overfitting control: L2 weight penalty (alpha) and a tuned maximum number of
    epochs. Validation-based early stopping was evaluated and rejected: with
    ~160-590 training rows per fold its 15% hold-out is too small and stopped
    training prematurely (CV macro-F1 0.41-0.70 vs 0.90-0.92 without it on the
    diabetes task; see docs/MODEL_METHODOLOGY.md).
    """
    defaults = dict(hidden_layer_sizes=(32, 16), activation="relu", solver="adam", alpha=1e-3,
                    learning_rate_init=1e-3, max_iter=500, early_stopping=False, random_state=SEED)
    defaults.update(params)
    return Pipeline([("prep", make_preprocessor(task, scale=True)),
                     ("model", MLPClassifier(**defaults))])


def build_hybrid(rf: Pipeline, ann: Pipeline, C: float = 1.0, class_weight=None) -> StackingClassifier:
    """Stacked RF + ANN hybrid.

    Level 0: the RF and ANN pipelines (refit on the full training set).
    Level 1: multinomial logistic regression trained on OUT-OF-FOLD class
    probabilities produced by 5-fold stratified CV over the training set
    (sklearn's StackingClassifier uses cross_val_predict internally), so the
    meta-model never sees in-sample predictions of the base models.
    """
    return StackingClassifier(
        estimators=[("rf", rf), ("ann", ann)],
        final_estimator=LogisticRegression(C=C, class_weight=class_weight, max_iter=5000),
        cv=StratifiedKFold(n_splits=5, shuffle=True, random_state=SEED),
        stack_method="predict_proba",
        passthrough=False,
        n_jobs=1,
    )


def build_voting(rf: Pipeline, ann: Pipeline, rf_weight: float = 0.5) -> VotingClassifier:
    """Alternative hybrid: weighted average of RF and ANN class probabilities
    (soft voting). The weight is chosen by cross-validation on the training set."""
    return VotingClassifier(estimators=[("rf", rf), ("ann", ann)], voting="soft",
                            weights=[rf_weight, 1.0 - rf_weight], n_jobs=1)


RF_GRID = {
    "model__max_depth": [None, 8],
    "model__min_samples_leaf": [1, 3, 6],
    "model__max_features": ["sqrt", 0.5],
}
ANN_GRID = {
    "model__hidden_layer_sizes": [(16,), (32, 16)],
    "model__alpha": [1e-2, 1e-1, 1.0],
    "model__max_iter": [300, 1000],
}
VOTING_GRID = {"weights": [[0.3, 0.7], [0.5, 0.5], [0.7, 0.3]]}
HYBRID_GRID = {
    "final_estimator__C": [0.1, 1.0, 10.0],
    "final_estimator__class_weight": [None, "balanced"],
}
