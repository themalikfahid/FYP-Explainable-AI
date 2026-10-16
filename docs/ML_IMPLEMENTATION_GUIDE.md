# ML implementation guide

Practical guide to the training code. Rationale and interpretation: MODEL_METHODOLOGY.md. Numbers:
MODEL_EVALUATION.md. Dataset facts: DATASET_AUDIT.md.

## Dataset schema and targets

| Task | Loader | Features (order) | Target |
|---|---|---|---|
| diabetes | `ml.data.load_diabetes()` | age, gender_male, polyuria, polydipsia, sudden_weight_loss, weakness, polyphagia, genital_thrush, visual_blurring, itching, irritability, delayed_healing, partial_paresis, muscle_stiffness, alopecia, obesity | `class` Positive = 1 |
| heart | `ml.data.load_heart()` | age, sex, cp, trestbps, chol, fbs, restecg, thalach, exang, oldpeak, slope, ca, thal | `num` 0-4 |

Encodings, ranges and labels are in `DIABETES_SPEC` / `HEART_SPEC`.

## Data-quality handling (in the loaders)

* Heart: `?` and `-9` are missing; Hungarian read from the raw 76-attribute file (`parse_raw76`) to keep grades
  1-4; `chol == 0` and `trestbps == 0` set to missing; exact duplicates dropped.
* Diabetes: Yes/No -> 1/0, Male -> 1; exact duplicates (269) dropped.

## Preprocessing (`ml/pipelines.py::make_preprocessor`)

`ColumnTransformer` per task: numeric median impute (+ StandardScaler for the ANN), binary most-frequent impute,
categorical most-frequent impute + one-hot. Always used inside a `Pipeline`, so it is fit inside each CV fold.

## Split and leakage prevention

`train_test_split(test_size=0.2, stratify=y, random_state=42)` after de-duplication. Tuning, hybrid selection and
CV comparison use only the training part. The test part is evaluated once. No oversampling. See the leakage
tests in `tests/ml/test_ml.py`.

## Models and hyperparameters

| Model | Builder | Grid (5-fold stratified CV, macro F1) |
|---|---|---|
| Random Forest | `build_rf(task, **params)` | max_depth {None, 8}; min_samples_leaf {1, 3, 6}; max_features {sqrt, 0.5}; fixed 300 trees, balanced_subsample |
| ANN (MLP) | `build_ann(task, **params)` | hidden {(16), (32,16)}; alpha {0.01, 0.1, 1}; max_iter {300, 1000}; ReLU, Adam, no early stopping |
| Hybrid A: stacking | `build_hybrid(rf, ann, C, class_weight)` | C {0.1, 1, 10}; class_weight {None, balanced}; 5-fold OOF probabilities |
| Hybrid B: soft voting | `build_voting(rf, ann, rf_weight)` | weights {0.3/0.7, 0.5/0.5, 0.7/0.3} |

The hybrid with the higher CV score is saved as `hybrid.joblib`; `metadata.json` records both candidates' scores
and the chosen strategy.

## Training and evaluation workflow

```bash
python -m ml.train                  # both tasks (diabetes ~3 min, heart ~5 min on 2 cores)
python -m ml.train --task heart     # one task
python -m ml.train --fast           # tiny grids, 1 CV repeat: smoke test only (metadata marks fast_mode=true)
python scripts/make_eval_report.py  # refresh docs/MODEL_EVALUATION.md
```

Console output and `artifacts/eval/training_log.txt` show best parameters, CV scores and test scores.

## Evaluation metrics (`ml/evaluate.py`)

`compute_metrics` returns accuracy, balanced accuracy, macro precision/recall/F1, weighted F1, confusion
matrix, multiclass Brier score, top-label ECE, per-class precision/recall/F1/support plus one-vs-rest ROC-AUC
and average precision; binary tasks add ROC-AUC, average precision, sensitivity, specificity; multiclass adds
macro/weighted OvR ROC-AUC and "any disease" metrics. `bootstrap_ci` gives 95% percentile intervals (1000
resamples). `calibration_table` gives reliability bins. Plots: confusion matrices, ROC, reliability, global SHAP.

## Probability calibration

Reported (Brier, ECE, reliability table and plot), not adjusted. The hybrid's probabilities are averages (soft
voting) or logistic outputs (stacking) of component probabilities. A post-hoc calibrator would need a further
held-out split; see FINAL_RECOMMENDATIONS.md.

## Serialization and inference

`joblib.dump(model, compress=3)`. Inference loads `hybrid.joblib` and uses `named_estimators_` for component
probabilities. Loading is refused on a feature, class-order or scikit-learn version mismatch. Training input
ranges (`feature_ranges_train`) drive the "outside training range" warning.

## Retraining procedure

1. Replace or add data in `data/raw/...` (keep the same columns), or change code.
2. `python -m ml.audit_datasets` and review the profile.
3. `python -m ml.train`.
4. `python scripts/make_eval_report.py`; read MODEL_EVALUATION.md critically.
5. `python -m pytest tests` (artifact tests confirm the saved models reproduce `test_predictions.csv` and the
   metadata metrics).
6. Restart the backend (models load at startup).

## Reproducibility

Seeds: 42 (split, RF, MLP, CV shuffles, SHAP background), 0 (SHAP permutations, bootstrap). `metadata.json`
stores library versions and SHA-256 hashes of the raw data files used. Parallel CV (`n_jobs=-1`) does not change
results. Different BLAS/CPU or library versions may change the last decimals of the MLP.

## Limitations
Small datasets and test sets, site-dependent missingness in the heart data, sex bias in the diabetes data,
no prospective data, no clinical validation. Full list: KNOWN_LIMITATIONS.md.
