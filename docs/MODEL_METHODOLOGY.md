# Model methodology

This document explains how the models were built and why, and interprets the results. The numbers
themselves are in MODEL_EVALUATION.md (generated from the saved metadata).

## 1. Tasks

| Task | Inputs | Output | Production model |
|---|---|---|---|
| Diabetes symptom screening | Age, sex, 14 yes/no symptoms (UCI Early Stage Diabetes Risk) | P(positive), P(negative) | Hybrid RF + ANN |
| Heart disease classification | 13 clinical/exercise-test inputs (UCI Heart Disease, 4 sites) | Probabilities for grades 0, 1, 2, 3, 4 | Hybrid RF + ANN |

Why the diabetes task is not called "Type-1": see DATASET_AUDIT.md section 2.

## 2. Pipeline and leakage prevention

1. **Load and clean** (`ml/data.py`): parse the raw Hungarian file to keep graded labels; turn impossible
   zeros (cholesterol, resting BP) into missing values; encode yes/no as 1/0.
2. **De-duplicate before splitting.** 269 duplicates in the diabetes data and 2 in the heart data are dropped
   first, so the same record cannot appear in both train and test.
3. **One stratified 80/20 split** (seed 42). The test set is put aside and used exactly once, after all
   tuning and model selection.
4. **Preprocessing lives inside each model's scikit-learn Pipeline** (`ml/pipelines.py`):
   * numeric: median imputation (+ standard scaling for the ANN only);
   * binary: most-frequent imputation;
   * categorical (cp, restecg, slope, thal): most-frequent imputation + one-hot encoding (unknown categories
     ignored).
   Because the preprocessor is part of the pipeline, every cross-validation fold re-fits imputation, scaling
   and encoding on its own training part only. A test (`tests/ml/test_ml.py::test_preprocessing_fitted_on_training_fold_only`)
   checks that the fitted medians equal the training medians and not the full-data medians.
5. **No resampling.** Oversampling (e.g. SMOTE) was not used. Class imbalance is handled with
   `class_weight="balanced_subsample"` in the Random Forest and, for stacking candidates, an optional
   balanced logistic meta-model. Nothing is ever resampled in the test set.
6. **Same features at training and inference.** `ml/data.py` holds the single feature specification (names,
   order, codes, units, ranges). The backend validates requests against it, serves it to the frontend, and
   refuses to load a model whose saved feature list differs.

## 3. Component models

### Random Forest
`RandomForestClassifier(n_estimators=300, class_weight="balanced_subsample", random_state=42)` tuned by
5-fold stratified CV on the training set over `max_depth` {None, 8}, `min_samples_leaf` {1, 3, 6},
`max_features` {sqrt, 0.5}, scoring macro F1.

### ANN
A feed-forward multi-layer perceptron (scikit-learn `MLPClassifier`): ReLU hidden layers, Adam optimiser,
softmax/logistic output with cross-entropy loss, inputs standardised. Tuned over hidden layers {(16), (32,16)},
L2 penalty `alpha` {0.01, 0.1, 1.0} and maximum epochs {300, 1000}.

*Why not TensorFlow/Keras?* The proposal lists TensorFlow/Keras. With 200 and 734 training rows a small dense
network is the right size; scikit-learn's MLP implements the same kind of network, lets the ANN sit inside a
Pipeline (so stacking and CV stay leakage-safe without custom wrappers), keeps the install small (no 500 MB
TensorFlow wheel, which also has narrower Python/OS support), and pickles together with the rest of the model.
The trade-off is fewer architecture options (no dropout or batch normalisation). This is listed in
FINAL_RECOMMENDATIONS.md.

*Overfitting control:* L2 penalty and a tuned epoch limit. Validation-based early stopping was tried first and
rejected: with 15% of an already small fold held out, it stopped training too early (train-set CV macro F1 for
the diabetes task fell to 0.41-0.70, versus 0.90-0.92 without it).

## 4. The hybrid

The proposal asks for a hybrid of RF and ANN, preferably stacking. Two genuine combination strategies were
implemented and **the choice between them is made by cross-validation on the training set only**:

* **Stacking** (`build_hybrid`): `StackingClassifier` with the tuned RF and ANN pipelines as level-0 models and
  logistic regression as the meta-model, trained on 5-fold **out-of-fold** class probabilities
  (`cv=StratifiedKFold(5)`, `stack_method="predict_proba"`). The meta-model never sees in-sample predictions.
  Tuned: meta C {0.1, 1, 10}, class_weight {None, balanced}.
* **Weighted soft voting** (`build_voting`): the RF and ANN probability vectors are averaged with weights
  {0.3/0.7, 0.5/0.5, 0.7/0.3}.

Both use the same tuned base models. For both tasks in the shipped training run, weighted soft voting with
RF 0.3 / ANN 0.7 had the higher CV macro F1 and was selected (diabetes: 0.934 vs 0.923; heart: 0.369 vs 0.331).
A plausible reason is that with a few hundred training rows, the stacking meta-model is fitted on noisy
out-of-fold probabilities and over-adjusts, while a fixed weighted average has a single parameter.

The production endpoint loads `artifacts/models/<task>/hybrid.joblib` and the RF/ANN probabilities shown to the
user are taken from the hybrid's own fitted members (`hybrid.named_estimators_`), so they are exactly the two
inputs being combined.

## 5. Results and honest interpretation

(See MODEL_EVALUATION.md for all tables.)

**Diabetes.** In repeated cross-validation on the training set the three models are indistinguishable
(macro F1 0.917 RF, 0.913 ANN, 0.915 hybrid). On the 51-row test set the RF scored higher (macro F1 0.914 vs
0.790 for both ANN and hybrid; 4 vs 10 errors), but the bootstrap intervals overlap widely
(0.83-0.98 vs 0.66-0.90). With 16 negative test cases, one or two cases move the score by several points.
**There is no evidence that the hybrid is better than the Random Forest on this task, and the single test
split slightly favours the RF.** The hybrid is deployed because it is the proposal's design, it was selected
by a pre-declared CV protocol, and its ROC-AUC (0.946) and calibration are close to the components.

**Heart, 5 grades.** This is a hard problem: grades 1-3 overlap heavily in the 13 inputs. Test macro F1 is
0.42 RF, 0.38 ANN, 0.39 hybrid, against a "predict the majority class" baseline of about 0.12 macro F1 (0.45
accuracy). Grade 0 is recognised well (F1 about 0.78-0.81); grades 1-4 have F1 of 0.17-0.37. Grade 4 has 9
test cases and is mostly missed. **Again, no evidence that the hybrid beats the RF on macro F1.**

**Heart, any disease vs none.** Collapsing grades 1-4 gives a clinically more useful question. The hybrid
reaches ROC-AUC 0.900, accuracy 0.826, sensitivity 0.882, specificity 0.756. The app therefore uses
P(any disease) = 1 - P(grade 0) as the main risk score and shows the grade as secondary information, with a
warning when no grade has more than 50% probability.

**Calibration.** On the test sets, top-class ECE is 0.11 (diabetes hybrid) and 0.09 (heart hybrid). Small
test sets make these estimates noisy. No separate calibration step (Platt/isotonic) was applied because it
would need another held-out set the data cannot spare. The UI therefore calls the numbers "model-estimated
probabilities", shows both component probabilities, and states they are not clinically validated risks.

**Site generalisation (heart).** Leave-one-site-out results are much weaker (5-class accuracy 0.28-0.61,
any-disease accuracy 0.71-0.78), which shows that the random-split figures overstate how the model would do at
a new hospital.

**External T1D check (diabetes).** On 85 diagnosed T1D children the hybrid flagged 41-60% as positive,
depending on the assumed sex. Nine of the 14 questions were missing from that cohort and 27% of children had
none of the five mapped symptoms recorded, so this is a weak, indicative result. It does suggest the screen
would miss many children with T1D and must not be presented as a T1D detector.

## 6. Probability, risk level and uncertainty shown to users

* **Risk score:** diabetes P(positive); heart P(any disease grade 1-4).
* **Risk level:** low below 0.30, moderate 0.30-0.70, high at or above 0.70. These are fixed, documented
  screening bands chosen for this prototype, not clinically derived cut-offs.
* **Uncertainty cues:** RF vs ANN disagreement over 30 points; inputs outside the training range;
  optional heart inputs left blank (imputed); top heart grade below 50%.

## 7. Reproducing

```
python -m ml.audit_datasets          # dataset profile
python -m ml.train                   # ~10 min on 2 CPU cores; writes artifacts/models and artifacts/eval
python -m ml.external_t1d_check      # needs data/restricted/t1d_cohort_deidentified.csv
python scripts/make_eval_report.py   # regenerates docs/MODEL_EVALUATION.md
```

Seeds are fixed (42 for splits/models, 0 for SHAP). Small numeric differences can still occur across
platforms or library versions.
