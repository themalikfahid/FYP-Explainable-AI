# Accuracy and limitations (read this before quoting any number)

All figures are **out-of-fold** results (3 x 5-fold stratified CV over every de-duplicated record, `python -m ml.oof_eval`),
saved in `artifacts/models/<task>/oof_report.json` and shown live on the *Model transparency* page.

| Model | Records | Overall CV accuracy | Confident-prediction accuracy (coverage) |
|---|---|---|---|
| Diabetes symptom screen (hybrid RF + ANN) | 251 unique | **90.0 %** (ROC-AUC 0.96) | **95.0 %** on 88 % of cases (gate >= 60 %) |
| Heart: disease vs none (hybrid) | 918 | 81.0 % (AUC 0.88, sens 86 %, spec 74 %) | 90.9 % on 55 % of cases (gate >= 85 %) |
| Heart: exact grade 0-4 (hybrid) | 918 | 52.4 % | 90.3 % on 28 % of cases (gate >= 75 %) |
| Type 1 indicator | 85 (positives only) | not applicable: rule-based | n/a |

## Why heart grade accuracy is not 90 %
The five-grade target from 11 routine inputs is intrinsically noisy in the public UCI data (four hospitals, different
labelling practice, many missing values). Tuned RF/XGBoost/ANN/stacking and feature engineering all stay near 50-55 %
under honest cross-validation; numbers above 90 % in this setting come from leakage (duplicates in train and test) or
from evaluating on a subset. We therefore report the achievable figures and add a **confidence gate**: below the gate the
app says "inconclusive" instead of guessing, and above it the measured accuracy reaches the target at reduced coverage.

## Type 1 diabetes
The local cohort has 85 children, all positive, with no controls, so no classifier can be trained or validated.
The app offers a transparent rule-based clinical-pattern indicator with a DKA emergency warning; it is not an AI model
and never claims a diagnosis. Collecting matched controls would allow a real model.

## Other limits
Public research data from specific populations (1980s US/European hospitals, one Bangladeshi clinic), small samples,
no external clinical validation, educational use only, not a medical device.


## Coronary artery disease screen (Z-Alizadeh Sani, added later)

A third model, `cad`, is trained on the Z-Alizadeh Sani dataset (UCI #412): 303 patients referred for angiography
(216 with >= 50% narrowing, 87 without), 27 practical inputs (risk factors, chest-pain type, resting ECG flags, vitals,
optional blood tests and ejection fraction). It is a **separate binary model**; its features differ from the UCI
heart cohort, so the two cannot be merged.

Out-of-fold (3 x 5-fold) results, hybrid RF + ANN stacking:

| Measure | Value |
|---|---|
| Overall accuracy | 88.8% (majority-class baseline 71.3%) |
| ROC-AUC | 0.919 |
| Balanced accuracy | 84.6% |
| Confident predictions (gate >= 85%) | 96.1% accurate, covering 58.7% of patients |
| Confidence >= 80% | 94.0% accurate, 71.6% coverage |

Caveats: one hospital, patients already referred for angiography (so higher prior disease rate than the general
population), no external validation. The labelled accuracy is a cross-validated estimate, not a clinical claim.
Run `python -m ml.train --task cad` then `python -m ml.oof_eval` to reproduce.


## ECG heartbeat classifier (MIT-BIH, multiclass, added later)

Task `ecg` classifies one heartbeat (187 samples) into 5 AAMI classes: normal, supraventricular, ventricular, fusion,
unknown/paced. Data: Kaggle "ECG Heartbeat Categorization Dataset" (MIT-BIH), 87,554 training and 21,892 official test
beats. Hybrid = soft voting of Random Forest (150 trees) and ANN (128-64). Protocol: 85/15 split of the training file
(fit / validation, the confidence gate is chosen on validation), the official test file is used once.

| Test measure (21,892 unseen beats) | Value |
|---|---|
| Accuracy | 97.6% (RF 97.6%, ANN 96.8%) |
| Balanced accuracy (mean class recall) | 85.3% |
| Macro F1 | 88.1% |
| Abnormal vs normal | 97.8% (sensitivity 92.8%, specificity 98.8%) |
| Confident predictions (>= 90%) | 99.7% accurate |

Caveats: 83% of test beats are normal, so accuracy flatters the model; rare classes (supraventricular, fusion) have
about 68% recall. The files are not split by patient (47 patients), so accuracy on new patients is likely lower.
Explanations use occlusion saliency (not SHAP). Run `python -m ml.ecg --data-dir <folder with the csv files>`.
The ~500 MB CSVs are not stored in the repo; keep them in the Datasets folder or `data/raw/mitbih/`.
