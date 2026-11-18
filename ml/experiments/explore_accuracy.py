"""Honest accuracy exploration: repeated stratified CV only (no test-set peeking, no duplicate leakage)."""
import sys, warnings, json
import numpy as np, pandas as pd
warnings.filterwarnings("ignore")
sys.path.insert(0, ".")
from sklearn.model_selection import RepeatedStratifiedKFold, cross_val_score, cross_validate
from sklearn.ensemble import RandomForestClassifier, ExtraTreesClassifier, HistGradientBoostingClassifier, VotingClassifier, StackingClassifier
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer, KNNImputer
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.svm import SVC
from ml.data import load_diabetes, load_heart, load_heart_raw, HEART_FEATURES

def cv(model, X, y, n_rep=3, folds=5, scoring="accuracy"):
    rs = RepeatedStratifiedKFold(n_splits=folds, n_repeats=n_rep, random_state=7)
    s = cross_val_score(model, X, y, cv=rs, scoring=scoring, n_jobs=2)
    return round(s.mean(), 4), round(s.std(), 4)

def pipe(m, scale=False, imp="median"):
    steps = [("imp", KNNImputer(n_neighbors=7) if imp == "knn" else SimpleImputer(strategy=imp))]
    if scale: steps.append(("sc", StandardScaler()))
    steps.append(("m", m))
    return Pipeline(steps)

which = sys.argv[1]
if which == "diabetes":
    X, y = load_diabetes()
    print("n", len(y), y.value_counts().to_dict())
    models = {
      "rf": pipe(RandomForestClassifier(500, random_state=1)),
      "et": pipe(ExtraTreesClassifier(500, random_state=1)),
      "hgb": pipe(HistGradientBoostingClassifier(max_depth=4, learning_rate=0.05, max_iter=300)),
      "mlp": pipe(MLPClassifier((16,), alpha=0.01, max_iter=1000, random_state=1), scale=True),
      "svc": pipe(SVC(C=5, probability=True), scale=True),
      "lr": pipe(LogisticRegression(C=1, max_iter=2000), scale=True),
    }
    for k, m in models.items(): print(k, cv(m, X, y))
    vote = VotingClassifier([("rf", models["rf"]), ("et", models["et"]), ("hgb", models["hgb"]), ("mlp", models["mlp"])], voting="soft")
    print("vote4", cv(vote, X, y))
elif which == "heart":
    X, y, site = load_heart()
    yb = (y > 0).astype(int)
    print("n", len(y), yb.value_counts().to_dict())
    for name, imp in [("median", "median"), ("knn", "knn")]:
        for k, m in {
          "rf": pipe(RandomForestClassifier(500, max_depth=8, min_samples_leaf=2, random_state=1), imp=imp),
          "hgb": pipe(HistGradientBoostingClassifier(max_depth=3, learning_rate=0.05, max_iter=200), imp=imp),
          "lr": pipe(LogisticRegression(C=0.5, max_iter=3000), scale=True, imp=imp),
          "mlp": pipe(MLPClassifier((32, 16), alpha=0.1, max_iter=800, random_state=1), scale=True, imp=imp),
        }.items():
            print("binary", name, k, cv(m, X, yb), "| 5class", cv(m, X, y))
    # cleveland only
    df = load_heart_raw(); df = df[df.site == "cleveland"].dropna(subset=["ca", "thal"]).drop_duplicates()
    Xc, yc = df[HEART_FEATURES], (df["num"] > 0).astype(int)
    print("cleveland complete n", len(yc))
    for k, m in {"rf": pipe(RandomForestClassifier(500, max_depth=6, random_state=1)),
                 "lr": pipe(LogisticRegression(C=0.3, max_iter=3000), scale=True)}.items():
        print("cleveland binary", k, cv(m, Xc, yc))
