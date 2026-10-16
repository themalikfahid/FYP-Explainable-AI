# Dataset audit

Every number below comes from `python -m ml.audit_datasets` (output: `artifacts/eval/dataset_profile.json`)
or from the de-identification script. Re-run them to reproduce.

## Summary of decisions

| Dataset | Source | Used for | Verdict |
|---|---|---|---|
| UCI Heart Disease, 4 sites (Cleveland, Hungary, Switzerland, VA Long Beach) | Uploaded `heartdisease.zip` (UCI repository files) | Multiclass heart disease model | Suitable for 5-class (0-4) classification after fixing the Hungarian labels and invalid zeros |
| UCI Early Stage Diabetes Risk Prediction (Sylhet Diabetes Hospital, Bangladesh) | `diabetes_data_upload.csv`, obtained from the public GitHub repo `nadaalay/Early_Stage_Diabetes_Prediction` because the UCI site was not reachable from the build environment | Diabetes screening model | Suitable for **diabetes (type unspecified)** symptom screening, **not** for Type-1-specific detection |
| `PATIENT_DATA_T1D.xlsx` (local cohort, 85 children with T1D) | Uploaded by the project team | Exploratory sensitivity check only | Cannot train a T1D classifier: no non-diabetic controls. Contained direct identifiers of minors, which were removed |
| DiaData (`Beyza-Cinar/DiaData`, linked in `type_1_diabtes.txt`) | GitHub repository | Not used | Repository contains only integration code; the CGM data must be requested from third parties and is all T1D patients, so it supports glucose forecasting, not detection |
| Kaggle Cardiovascular Disease (`cardio_train.csv`, linked via `RobinsonCW/CardiovascularDiseaseClassification`) | GitHub repository | Not used for the models; profiled only | Binary target, so it cannot support the multiclass objective |

## 1. UCI Heart Disease (multiclass)

**Files:** `data/raw/heart_uci/processed.cleveland.data`, `processed.switzerland.data`, `processed.va.data`,
`hungarian.data` (raw 76-attribute file), plus `processed.hungarian.data` kept for the audit only, and the
original `heart-disease.names` documentation. The archive's `WARNING` file states that `cleveland.data`
(76 attributes) is corrupted and `processed.cleveland.data` is the usable copy, so the processed file is used
for Cleveland.

**Provenance:** Detrano et al., collected at the Cleveland Clinic Foundation, Hungarian Institute of
Cardiology (Budapest), V.A. Medical Center (Long Beach) and University Hospital Zurich. Principal investigators
(as requested by the donors): Andras Janosi, M.D.; William Steinbrunn, M.D.; Matthias Pfisterer, M.D.;
Robert Detrano, M.D., Ph.D.

**Schema:** 13 inputs (age, sex, cp, trestbps, chol, fbs, restecg, thalach, exang, oldpeak, slope, ca, thal)
and target `num` = angiographic disease status: 0 = less than 50% diameter narrowing in any major vessel;
1-4 = increasing disease grades. The documentation does not define grades 1-4 in more detail, so the app
labels them "grade 1 (mildest)" to "grade 4 (most severe)" and never as named clinical stages.

**Size:** 920 rows (Cleveland 303, Hungarian 294, VA 200, Switzerland 123); 918 after removing 2 exact
duplicates.

**Target distribution (all sites):** 0: 411, 1: 196, 2: 135, 3: 135, 4: 43. Class 4 is rare (4.7%).

| Site | 0 | 1 | 2 | 3 | 4 |
|---|---|---|---|---|---|
| Cleveland | 164 | 55 | 36 | 35 | 13 |
| Hungarian | 188 | 37 | 26 | 28 | 15 |
| Switzerland | 8 | 48 | 32 | 30 | 5 |
| VA Long Beach | 51 | 56 | 41 | 42 | 10 |

### Finding: the distributed Hungarian file collapses the grades

`processed.hungarian.data` only contains labels 0 and 1. The raw `hungarian.data` (76 attributes) contains
grades 0-4. Matching the 293 rows by their 13 feature values shows that every processed "0" is raw 0 and every
processed "1" is raw 1, 2, 3 or 4 (crosstab in `dataset_profile.json -> heart_uci.hungarian_label_check`).
Training on the processed file would have taught the model that all Hungarian patients with disease are
"grade 1", which is wrong. **The raw Hungarian file is therefore parsed directly** (`ml/data.py::parse_raw76`).

### Missing and invalid values

| Feature | Missing (raw) | Notes |
|---|---|---|
| ca (vessels by fluoroscopy) | 610 | Almost absent outside Cleveland (99% missing in Hungary and VA) |
| thal | 486 | 90.5% missing in Hungary, 83% in VA |
| slope | 309 | |
| fbs | 90 | |
| oldpeak, trestbps, thalach, exang | 55-62 each | |
| chol | 30 missing **plus 172 recorded as 0** | All 123 Swiss rows and 49 VA rows have chol = 0, which is impossible; treated as missing |
| trestbps | 1 row recorded as 0 | Treated as missing |
| oldpeak | 12 negative values | Kept: ST elevation can be recorded as a negative depression |

Missingness is strongly tied to site, and the sites have very different disease prevalence (Switzerland is
93% diseased). A model can partly learn "which hospital" from missingness patterns. Mitigations: no
missing-indicator features are added, and a leave-one-site-out analysis is reported in MODEL_EVALUATION.md.
This remains a limitation.

## 2. Early Stage Diabetes Risk Prediction

**File:** `data/raw/early_stage_diabetes/diabetes_data_upload.csv`. 520 rows, 17 columns: Age, Gender and 14
yes/no symptom questions (Polyuria, Polydipsia, sudden weight loss, weakness, Polyphagia, Genital thrush,
visual blurring, Itching, Irritability, delayed healing, partial paresis, muscle stiffness, Alopecia, Obesity),
target `class` Positive/Negative. The row counts (320 positive, 200 negative) match the UCI description
(dataset id 529, Islam et al., 2020, collected by questionnaire at Sylhet Diabetes Hospital and approved by
a doctor).

**Data quality:**

* No missing values.
* **269 of 520 rows (52%) are exact duplicates.** With duplicates, identical records end up in both train
  and test sets and inflate scores. They are removed before splitting, leaving **251 rows (173 positive,
  78 negative)**. No identical feature set has conflicting labels.
* Age 16-90 (median 47.5). Adult-only population.
* Sex imbalance in the label: 90.1% of female rows are positive vs 44.8% of male rows. This is a sampling
  artefact of a hospital-based dataset, not a biological rule. The model learns it (sex is the third most
  important SHAP feature), which means **women receive higher scores for the same symptoms**. This is
  disclosed in the app's model page, here, and in KNOWN_LIMITATIONS.md.

### Mandatory Type-1 verification: result

The target says only "Positive" or "Negative" for diabetes. Neither the file nor the UCI documentation states
the type, and the population is adult (median 47.5 years), where type 2 is far more common. **There is no
evidence that the positive labels are Type 1 Diabetes.** The model is therefore named and presented
everywhere as "Diabetes symptom-based risk screening (type not specified by the data)". The landing page and
the assessment page tell the user it cannot distinguish type 1 from type 2.

The symptom set (thirst, urination, weight loss, blurred vision) does overlap with classic T1D presentation
(the Diabetes UK "4Ts"), which is why the exploratory check below was done.

## 3. Local T1D cohort (`PATIENT_DATA_T1D.xlsx`)

**Contents:** one sheet, header on row 3, 85 patient rows, 34 columns including NAME, PHONE NO., ADDRESS,
PICTURE, ETHNICITY (family/caste names), EDUCATION, age, weight, height, onset, family history,
consanguinity, fasting blood glucose, HbA1c, insulin use, 13 symptom/comorbidity flags.

**Privacy finding (critical):** the sheet contains direct identifiers of children (names, phone numbers,
addresses). These are not needed for any analysis. `scripts/deidentify_t1d_cohort.py` drops NAME, PHONE NO.,
ADDRESS, PICTURE, ETHNICITY, EDUCATION and SR. NO, replaces IDs with random pseudonyms, shuffles row order and
writes `data/restricted/t1d_cohort_deidentified.csv`. **The original workbook is not copied into the
project.** The team should store the original securely and confirm it was collected with consent/ethics
approval before any further use.

**Label finding:** every row is a diagnosed T1D patient (insulin use recorded for 83 of 85). There are no
non-diabetic controls, so no classifier can be trained on it. It can only estimate how often a screen flags
known patients (sensitivity), and only roughly.

**Quality issues found:**

| Issue | Count |
|---|---|
| HbA1c missing ("nill") | 27 |
| HbA1c implausible (> 20%, likely 59.1 typed for 5.91) | 1 |
| HbA1c < 4% | 1 |
| Fasting BG < 70 mg/dL (possible hypoglycaemia at measurement) | 6 |
| Unparseable/typo values ("YS", "MO", "2 month", "kg", "prep") | Normalised where unambiguous ("YS" = yes, "2 month" = 0.17 years); otherwise set missing |
| Near-duplicate row (identical except pseudonym) | 1 |
| Ages | 4-18 years |

**Use in this project:** exploratory check only (`python -m ml.external_t1d_check`), results in
MODEL_EVALUATION.md. Five symptoms map onto the screening questionnaire (urination, thirst, loss of weight,
blurry vision, itching); the other nine questions are absent and set to "No", and sex is absent so both values
are reported. Ages are below the training range. The result is indicative only.

## 4. DiaData (Beyza-Cinar/DiaData)

The repository (README, `data_integration.py`, an exploration notebook) describes an integrated CGM dataset
built from 15 T1D studies. The data itself is not in the repository: a partial version is on Zenodo
(doi 10.5281/zenodo.16874128) and several sources require data-use agreements. All subjects have T1D, so it
suits hypoglycaemia or glucose forecasting, not detection of T1D in the general population. It was not
used. It is listed in FINAL_RECOMMENDATIONS.md as an option if the project's objective is reframed.

## 5. Kaggle cardiovascular dataset (cardio_train.csv)

70,000 rows, binary `cardio` target (35,021 / 34,979), age in days, height, weight, systolic/diastolic BP,
cholesterol and glucose in 3 levels, smoking, alcohol, activity. Quality issues: 229 implausible systolic
values, 1,012 implausible diastolic values, 1,234 rows with diastolic > systolic, 24 duplicates. **Binary only,
so it cannot support the proposal's multiclass objective.** It is kept in `data/raw/cardio_kaggle/` for
reference but not used by the models.

The same repository also contains `diabetic_data.csv` (UCI "Diabetes 130-US hospitals"), which includes
ICD-9 codes from which type 1 (250.x1 / 250.x3) can be distinguished, but every patient in it is already
diabetic and the features are hospital-encounter data (medications, admissions), so it does not fit a
self-screening form. Not used; noted as a possible type 1 vs type 2 research extension.

## 6. Impact on the original objectives

| Proposal objective | Status |
|---|---|
| Early detection of Type-1 Diabetes | **Not achievable with the available data.** Replaced by diabetes (type unspecified) symptom screening; documented in the UI and docs. |
| Multiclass heart disease classification | Achieved on UCI 0-4 grades, with modest per-grade performance (see MODEL_EVALUATION.md) |
| "Early detection" | The models are trained on retrospective, cross-sectional data. They classify current status; they do not predict future disease. The app uses "screening", not "prediction of future risk". |
