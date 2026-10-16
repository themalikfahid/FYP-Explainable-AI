# Project plan

## Goal
A working, local, explainable screening application matching the BSDS FYP proposal "Explainable AI-based hybrid
model for early detection of type-1 diabetes and multiclass heart disease classification" (UCP, Fall 2026), built
honestly against the data actually available.

## Inputs reviewed
* Proposal PDF (12 pages): objectives, features list, tools, milestones, success criteria, references.
* Datasets: UCI Heart Disease archive (zip), local T1D spreadsheet, links to DiaData and a cardiovascular
  repository (which also held the Kaggle cardio data and the UCI 130-hospital diabetes data).
* Additional public dataset obtained: UCI Early Stage Diabetes Risk Prediction (via a GitHub mirror).

## Phases as executed

| Phase | Output |
|---|---|
| 1. Inspect proposal and data | DATASET_AUDIT.md, de-identification script, dataset profile |
| 2. Architecture | PROJECT_ARCHITECTURE.md; FastAPI + SQLite + React/TS; scikit-learn + SHAP |
| 3. Preprocessing | `ml/data.py`, `ml/pipelines.py` |
| 4. RF, ANN, hybrid | `ml/train.py`, artifacts, MODEL_METHODOLOGY.md, MODEL_EVALUATION.md |
| 5. SHAP | `ml/explain.py`, SHAP_EXPLAINABILITY.md |
| 6. Recommendations, BMI, lifestyle | `services/recommend.py`, `scoring.py`, RECOMMENDATION_ENGINE.md |
| 7. Backend, DB, auth | `backend/app/*`, API_REFERENCE.md, DATABASE_SCHEMA.md |
| 8. Frontend | `frontend/src/*` |
| 9. PDF and email | `services/pdf.py`, `services/email.py` |
| 10. Security | SECURITY_AND_PRIVACY.md, audits |
| 11. QA | 117 automated tests, TEST_REPORT.md |
| 12. Performance | `scripts/benchmark.py`, performance.json |
| 13. Documentation | README + docs/ |
| 14. Release verification | clean-environment test run, acceptance checklist in README |

## Key decisions
1. Diabetes task renamed (no T1D labels). 2. Raw Hungarian file parsed for graded labels. 3. Duplicates removed
before splitting. 4. scikit-learn MLP for the ANN. 5. Hybrid strategy chosen by training CV between stacking and
soft voting. 6. SHAP on the full hybrid output via permutation SHAP. 7. Heart headline score = P(any disease).
8. Local-first SQLite; no Git, per the brief. 9. Email content excludes health data.
