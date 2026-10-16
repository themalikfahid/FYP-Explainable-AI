# SHAP explainability

## What is explained

The **final hybrid output**: the probability vector returned by `hybrid.predict_proba`, which already
includes preprocessing, both the Random Forest and the ANN, and their combination. The app does not show
a Random Forest TreeExplainer and call it an explanation of the ensemble.

## Method

`ml/explain.py::HybridExplainer` wraps `shap.PermutationExplainer` (SHAP 0.53):

* **Model function:** raw feature row(s) as a DataFrame in the canonical feature order -> `hybrid.predict_proba`.
  Output has one column per class, in `hybrid.classes_` order ([0, 1] or [0, 1, 2, 3, 4]).
* **Masker:** `shap.maskers.Independent` over a fixed background of 50 training rows
  (`artifacts/models/<task>/shap_background.csv`, sampled with seed 42 at training time). A "missing" feature
  is replaced by background values and the whole pipeline is re-run. This is the interventional
  (marginal) form of SHAP.
* **Budget:** `max_evals = 10 x (2 x n_features + 1)`, i.e. 330 model evaluations per row for diabetes
  (16 features) and 270 for heart (13 features), each over the 50 background rows.
* **Seed:** 0, so repeated explanations of the same input are identical.

Why model-agnostic permutation SHAP: TreeExplainer only covers the forest, DeepExplainer/GradientExplainer
need a differentiable framework model, and KernelExplainer is slower and only approximately additive.
Permutation SHAP with antithetic permutations is **exactly additive**:

```
base_value[c] + sum over features of shap[feature, c] == predicted_probability[c]
```

This is checked in `tests/ml/test_ml.py::test_shap_explains_hybrid_output_additively` (error < 1e-6 for
every class) and the API returns `additivity_error` with each explanation (typically about 1e-16).

## Units and reading the output

Values are in **probability units**. +0.096 for "Polyuria = Yes" means: compared with the average
prediction over the background sample, knowing this answer moved the estimated probability of the explained
class up by 9.6 percentage points (given the other answers). The app shows them as "pp".

* **Diabetes:** the explained class is the predicted class; the UI lets the user switch to the other class
  (values are mirror images because the two probabilities sum to 1).
* **Heart:** the API returns SHAP values for all five classes (`per_class`) plus an **any-disease** view.
  Because P(any) = 1 - P(grade 0), its SHAP values are exactly the negated grade-0 values and its base value is
  1 - base(grade 0). The result page opens on "Any heart disease" because that is the headline risk score;
  the user can switch to any grade.
* **Missing optional heart inputs:** the input is NaN, which the pipeline imputes. SHAP still attributes a
  contribution to that feature (the effect of "not provided, filled with the median/most frequent value"),
  and the UI labels it "Not provided".

## Global importance

During training, `ml/train.py` explains up to 120 test rows (all 51 for diabetes) and stores mean |SHAP| per
feature and class in `global_shap.json`. The "How the models work" page and the landing page display it, and
`artifacts/eval/<task>_global_shap.png` is the static figure. Current ranking (see MODEL_EVALUATION.md):

* Diabetes: polyuria, polydipsia, sex, itching, polyphagia, ...
* Heart: chest-pain type, ST depression (oldpeak), max heart rate, sex, cholesterol, age, ...

These broadly agree with the literature cited in the proposal (glucose-related symptoms for diabetes; chest
pain and exercise-test findings for heart disease). The high rank of **sex** in the diabetes model reflects a
sampling bias of the dataset (DATASET_AUDIT.md), which SHAP makes visible. That is a useful outcome of
explainability, not a medical finding.

## Human-readable summary

`humanize()` turns the top three contributions into sentences such as
"Polyuria = Yes raised the estimated probability of 'Positive (diabetes-consistent symptom profile)' by 9.6
percentage points." Option codes are converted to labels and units are added from the feature spec.

## Performance

Measured with `python scripts/benchmark.py` on a 2-core cloud VM (`artifacts/qa/performance.json`): full
prediction requests including SHAP took a median of about 0.5 s (diabetes) and 0.6 s (heart); prediction
without SHAP about 50-60 ms. Global SHAP during training: 20 s (diabetes, 51 rows) and 62 s (heart, 120 rows).
The explainer object is built once per model at startup and reused; explanations are computed per request and
never cached across users.

## Limitations

* SHAP explains the **model**, not the patient's biology. It does not show causes, and features correlated
  with each other share credit in ways that depend on the background sample.
* The Independent masker evaluates combinations of feature values that may be unrealistic (e.g. high max
  heart rate with severe ST depression), a known limitation of interventional SHAP.
* Values depend on the background sample; a different background gives different base values and somewhat
  different attributions (the predicted probability does not change).
* With a 330-evaluation budget the attributions for low-impact features carry some sampling noise; additivity
  still holds exactly.
* The global ranking is computed on small test sets (51 and 120 rows).
