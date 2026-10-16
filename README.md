# Clarity Screen: explainable hybrid screening for diabetes symptoms and heart disease

Final Year Project prototype (BSDS, University of Central Punjab, Fall 2026) based on the proposal
*"Explainable AI-based hybrid model for early detection of type-1 diabetes and multiclass heart disease
classification"*.

> **Educational screening and decision-support prototype. Not a diagnosis, not a medical device, not clinically
> validated.**

> **Important scope change:** the available labelled data does not identify Type 1 Diabetes, so the diabetes model
> is a *diabetes (type unspecified) symptom screen*. See [docs/DATASET_AUDIT.md](docs/DATASET_AUDIT.md).

## What it does

* **Two assessments:** a diabetes symptom screen (age, sex, 14 symptoms) and a heart disease classifier (13
  clinical/exercise-test inputs, grades 0-4, with "any disease" probability as the headline score).
* **Hybrid ML model:** Random Forest + ANN (multi-layer perceptron), combined by the better of out-of-fold
  stacking or weighted soft voting (chosen by cross-validation on training data only). Leakage-safe pipelines.
* **Explanations:** SHAP values of the hybrid's own output for every prediction, plus global importance.
* **Honest probabilities:** hybrid and component probabilities, warnings for missing/out-of-range inputs and
  model disagreement; calibration measured and reported.
* **Recommendations:** rule-based diet, activity, sleep, risk-mitigation and follow-up advice with guideline
  sources; BMI (WHO and WHO-Asian cut-offs) and a 0-100 lifestyle score.
* **Accounts and records:** registration, login, logout with token revocation, private history, delete, account
  deletion.
* **PDF reports** and **high-risk email alerts** (disabled / local file / SMTP).

## Technology

Python 3.11-3.13, FastAPI, Pydantic, SQLAlchemy + SQLite, scikit-learn 1.9.1, SHAP 0.53, ReportLab, bcrypt, PyJWT;
React 18 + TypeScript, Vite 6, React Router 7 · pytest, Vitest, Testing Library, Playwright.

## Quick start

Requirements: Python 3.11-3.13, Node.js 20/22. Full instructions:
[docs/INSTALLATION_AND_SETUP.md](docs/INSTALLATION_AND_SETUP.md).

```bash
# 1. backend
python -m venv .venv
.venv\Scripts\activate            # Windows  (macOS/Linux: source .venv/bin/activate)
pip install -r requirements.txt
copy .env.example .env            # macOS/Linux: cp; then set SECRET_KEY

# 2. frontend (once)
cd frontend && npm ci && npm run build && cd ..

# 3. run (trained models are included in artifacts/models)
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```
Open http://127.0.0.1:8000. Health check: http://127.0.0.1:8000/api/health. API docs: http://127.0.0.1:8000/api/docs.

Development with hot reload: run Uvicorn with `--reload` and `cd frontend && npm run dev`, then open
http://localhost:5173.

## Train and evaluate the models

```bash
python -m ml.audit_datasets          # dataset profile -> artifacts/eval/dataset_profile.json
python -m ml.train                   # RF, ANN, hybrid for both tasks (~10 min on 2 cores)
python -m ml.external_t1d_check      # exploratory check on the de-identified T1D cohort
python scripts/make_eval_report.py   # regenerate docs/MODEL_EVALUATION.md
```

## Tests

```bash
pip install -r requirements-dev.txt
python -m playwright install chromium     # browser for the e2e test
./scripts/run_all_tests.sh                # Windows: .\scripts\run_all_tests.ps1
```
Last run: **117 tests, 117 passed** (unit 51, ML 16, integration 37, frontend 12, end-to-end 1 full journey).
See [docs/TEST_REPORT.md](docs/TEST_REPORT.md).

## Results in one table (held-out test sets; details in [docs/MODEL_EVALUATION.md](docs/MODEL_EVALUATION.md))

| Task | RF macro F1 | ANN macro F1 | Hybrid macro F1 | Hybrid ROC-AUC |
|---|---|---|---|---|
| Diabetes symptom screen (n=51) | 0.914 | 0.790 | 0.790 | 0.946 |
| Heart, 5 grades (n=184) | 0.422 | 0.382 | 0.385 | 0.768 (macro OvR) |
| Heart, any disease vs none | | | accuracy 0.826 | 0.900 |

In cross-validation the three models are statistically indistinguishable; the hybrid does **not** outperform the
Random Forest on these datasets. This is discussed in [docs/MODEL_METHODOLOGY.md](docs/MODEL_METHODOLOGY.md).

## Troubleshooting (most common)

| Problem | Fix |
|---|---|
| `/api/health` shows a model as not loaded | `pip install -r requirements.txt` exactly (scikit-learn 1.9.1) or `python -m ml.train` |
| `{"detail":"Not Found"}` at `/` | `cd frontend && npm run build` |
| `npm ci` crashes with `edgesOut` | keep `frontend/.npmrc` (legacy-peer-deps) |
| Logged out after every restart | set `SECRET_KEY` in `.env` |

More: [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md).

## Documentation

| Document | Contents |
|---|---|
| [PROJECT_PLAN](docs/PROJECT_PLAN.md) | phases and key decisions |
| [IMPLEMENTATION_STATUS](docs/IMPLEMENTATION_STATUS.md) | each proposal requirement: done / partial / changed / blocked |
| [DATASET_AUDIT](docs/DATASET_AUDIT.md) | dataset findings, T1D verification, privacy issue |
| [PROJECT_ARCHITECTURE](docs/PROJECT_ARCHITECTURE.md) | diagrams of system, training, prediction, auth |
| [DEVELOPER_GUIDE](docs/DEVELOPER_GUIDE.md) | code walkthrough, request trace, how to extend |
| [INSTALLATION_AND_SETUP](docs/INSTALLATION_AND_SETUP.md) | step-by-step setup (Windows, macOS, Linux) |
| [API_REFERENCE](docs/API_REFERENCE.md) | every endpoint with examples |
| [DATABASE_SCHEMA](docs/DATABASE_SCHEMA.md) | tables, constraints, ownership, backups |
| [ML_IMPLEMENTATION_GUIDE](docs/ML_IMPLEMENTATION_GUIDE.md) | training code how-to, retraining |
| [MODEL_METHODOLOGY](docs/MODEL_METHODOLOGY.md) | modelling rationale and interpretation |
| [MODEL_EVALUATION](docs/MODEL_EVALUATION.md) | all metrics (generated) |
| [SHAP_EXPLAINABILITY](docs/SHAP_EXPLAINABILITY.md) | explanation method and limits |
| [RECOMMENDATION_ENGINE](docs/RECOMMENDATION_ENGINE.md) | rules, BMI and lifestyle formulas, sources |
| [SECURITY_AND_PRIVACY](docs/SECURITY_AND_PRIVACY.md) | controls, checks, open risks |
| [TESTING_AND_QA_GUIDE](docs/TESTING_AND_QA_GUIDE.md) | how to run and debug tests |
| [TEST_REPORT](docs/TEST_REPORT.md) | results, defects fixed, performance |
| [USER_GUIDE](docs/USER_GUIDE.md) | for end users |
| [TROUBLESHOOTING](docs/TROUBLESHOOTING.md) | errors and fixes |
| [KNOWN_LIMITATIONS](docs/KNOWN_LIMITATIONS.md) | scientific, technical, clinical limits |
| [FINAL_RECOMMENDATIONS](docs/FINAL_RECOMMENDATIONS.md) | prioritised next steps |

## Project layout

```
backend/app/   FastAPI app (routers, services, security, models)
ml/            data loading, pipelines, training, evaluation, SHAP
frontend/      React + TypeScript app
data/raw/      public datasets      data/restricted/  de-identified T1D cohort (do not share)
artifacts/     models/, eval/ (plots, profiles), qa/ (test logs, screenshots, audits, performance)
tests/, e2e/   automated tests      scripts/  utilities      docs/  documentation
```

## Final acceptance checklist

| Item | Status |
|---|---|
| Proposal reviewed | Yes |
| Dataset suitability documented | Yes (DATASET_AUDIT.md) |
| Type-1 objective represented honestly | Yes: renamed task, warnings in UI and docs |
| RF and ANN baselines evaluated | Yes |
| Integrated hybrid evaluated | Yes (stacking and soft voting compared; soft voting deployed) |
| SHAP explains the deployed pipeline | Yes (additivity tested) |
| Recommendations and BMI tested | Yes |
| Authentication and persistence work | Yes |
| Frontend uses the real backend and models | Yes (e2e) |
| PDF generation works | Yes (content verified) |
| Email tested where configuration permits | File mode and simulated SMTP: yes. Real SMTP: blocked (no credentials) |
| Automated QA executed, defects fixed and regression-tested | Yes (12 defects logged) |
| Launches with documented commands | Yes on Linux; your own computer was unreachable, so not run there |
| Developer documentation complete | Yes |
| Test artifacts and real evaluation reports exist | Yes (`artifacts/`) |
| No Git repository or commits created | Yes |
| Remaining blockers reported | Yes (IMPLEMENTATION_STATUS.md) |

## Data credits
UCI Heart Disease: Andras Janosi, M.D. (Hungarian Institute of Cardiology, Budapest); William Steinbrunn, M.D.
(University Hospital, Zurich); Matthias Pfisterer, M.D. (University Hospital, Basel); Robert Detrano, M.D., Ph.D.
(V.A. Medical Center, Long Beach and Cleveland Clinic Foundation). UCI Early Stage Diabetes Risk Prediction:
Sylhet Diabetes Hospital, Bangladesh (Islam et al., 2020).
