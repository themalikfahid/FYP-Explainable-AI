# Developer guide

Read README.md and INSTALLATION_AND_SETUP.md first. This guide explains how the code is organised, how a request
travels through it, and how to change it safely. Diagrams: PROJECT_ARCHITECTURE.md.

## 1. Architecture and module responsibilities

Three layers:

1. **Offline ML** (`ml/`): turns `data/raw` into model artifacts in `artifacts/models/<task>/`.
2. **Backend** (`backend/app/`): FastAPI, loads the artifacts at startup, validates input, runs inference and
   SHAP, applies recommendation rules, stores results in SQLite, renders PDFs, sends alerts.
3. **Frontend** (`frontend/`): React + TypeScript SPA; built files are served by the backend.

The one piece of shared truth is the **feature specification** in `ml/data.py` (`DIABETES_SPEC`, `HEART_SPEC`,
`TASKS`). Training uses its feature order, the backend's Pydantic models mirror it (a test enforces this), and the
frontend builds its forms from `GET /api/meta/features`.

## 2. Directory structure

```
fyp-xai-health/
├── backend/app/
│   ├── main.py            app factory, middleware, startup, SPA serving
│   ├── config.py          Settings (env / .env)
│   ├── db.py              engine, sessions, init_db
│   ├── models.py          SQLAlchemy tables
│   ├── schemas.py         Pydantic request/response models
│   ├── security.py        bcrypt, JWT, auth dependencies, rate limiter
│   ├── routers/           auth.py, predictions.py, meta.py
│   └── services/          inference.py, recommend.py, scoring.py, pdf.py, email.py
├── ml/                    data.py, pipelines.py, train.py, evaluate.py, explain.py,
│                          audit_datasets.py, external_t1d_check.py
├── frontend/
│   ├── src/api.ts         typed API client + token storage
│   ├── src/auth.tsx       AuthContext (login/logout/refresh)
│   ├── src/useMeta.ts     cached feature spec
│   ├── src/components/    Layout, Fields (form fields + validation), Explain (SHAP ledger,
│   │                      importance bars, risk badge, probability table), PredictionView
│   ├── src/pages/         Landing, AuthPages, Dashboard, Assess, ResultPage, History, Tools,
│   │                      ModelInfo, Settings
│   ├── src/styles/app.css design tokens and all styles
│   └── tests/             Vitest + Testing Library
├── data/raw/              public datasets (unchanged copies)
├── data/restricted/       de-identified T1D cohort (do not share)
├── artifacts/models/      trained models + metadata (loaded by the backend)
├── artifacts/eval/        plots, dataset profile, training log, T1D check
├── artifacts/qa/          test logs, JUnit XML, screenshots, audits, performance
├── tests/                 unit/, ml/, integration/ (pytest) + conftest.py
├── e2e/                   Playwright browser journey
├── scripts/               deidentify_t1d_cohort.py, benchmark.py, make_eval_report.py,
│                          run_all_tests.sh / .ps1
└── docs/
```

## 3. Backend

* **App factory** `create_app(settings)`: registers CORS (only `CORS_ORIGINS`), a security-headers middleware,
  a validation error handler that returns field messages without echoing values, a catch-all 500 handler that
  logs the stack trace server-side only, the three routers and, if `frontend/dist` exists, static file serving.
* **Startup (lifespan):** configure DB -> `create_all` -> `Registry(MODELS_DIR).load_all()`. A model that fails
  to load does not stop the server; its endpoints return 503 and `/api/health` shows why.
* **Routers:**
  * `meta.py`: health, feature spec, model card, BMI and lifestyle tools (public).
  * `auth.py`: register, login, logout, me (get/patch/delete), change password.
  * `predictions.py`: predict (diabetes/heart), list, get, delete, PDF.
* **Dependencies:** `get_db` yields a session per request; `get_current_user` decodes the JWT, checks the
  denylist and loads the user.

## 4. Frontend

* `api.ts` wraps `fetch`, attaches the bearer token, turns error responses into `ApiError(status, message,
  fieldErrors)`, and on a 401 clears the token and notifies `AuthProvider`.
* Token storage: in memory plus `sessionStorage` (survives reload, cleared when the tab closes). Wrapped in
  try/catch because storage can be blocked.
* Routing (`App.tsx`): public `/`, `/login`, `/register`, `/tools`, `/models`; protected `/dashboard`,
  `/assess/:task`, `/history`, `/history/:id`, `/settings` via `<Protected>`.
* Forms (`pages/Assess.tsx`) are generated from the served spec. Client-side validation (`validateField`) mirrors
  the server rules; server 422 field errors are mapped back onto fields.
* `components/PredictionView.tsx` renders a stored prediction: risk header, warnings, the SHAP "contribution
  ledger" with a class selector, probability table (hybrid + components), inputs, BMI/lifestyle score,
  grouped recommendations, PDF download and delete.
* Styling: one CSS file with tokens on `:root` (light + dark via `prefers-color-scheme`). Red/green are reserved
  for "raises/lowers probability"; risk levels always appear as words, never colour alone.

## 5. Database
See DATABASE_SCHEMA.md. Sessions are short-lived per request; background alert jobs open their own session.

## 6. Authentication and authorisation
bcrypt (cost 12) password hashes; HS256 JWT with `sub`, `iat`, `exp`, `jti`, `type`; logout and password change
insert the `jti` into `revoked_tokens`. Ownership checks live in `predictions.py::_owned`, which returns 404 for
both "missing" and "someone else's". Details: SECURITY_AND_PRIVACY.md.

## 7-13. ML: data, preprocessing, models, training, artifacts
See ML_IMPLEMENTATION_GUIDE.md (how-to) and MODEL_METHODOLOGY.md (rationale). Key points for developers:

* `load_diabetes()` / `load_heart()` return de-duplicated `X, y` in canonical feature order.
* `build_rf`, `build_ann`, `build_hybrid` (stacking), `build_voting` return full Pipelines.
* `python -m ml.train` writes, per task: `hybrid.joblib`, `random_forest.joblib`, `ann.joblib`,
  `metadata.json` (features, classes, labels, split, params, CV and test metrics, thresholds, training ranges,
  versions, data hashes), `shap_background.csv`, `global_shap.json`, `test_predictions.csv`.
* `services/inference.py::TaskModel` refuses to load if files are missing, the feature list differs from
  `ml/data.py`, the class order differs, or the scikit-learn version differs from the one in metadata.

## 14. SHAP
`ml/explain.py::HybridExplainer` (built once per model at startup). `explain_one(row)` returns per-class SHAP
values, the sorted contribution list for the predicted class, base value and an additivity check.
See SHAP_EXPLAINABILITY.md.

## 15-16. Recommendations, BMI and lifestyle score
`services/recommend.py::recommend(disease, features, risk_level, explanation, lifestyle)` and
`services/scoring.py`. Rules and formulas: RECOMMENDATION_ENGINE.md.

## 17. PDF
`services/pdf.py::build_report(prediction, user)` builds an A4 report with ReportLab platypus from the stored
record, including a vector SHAP bar chart. Returns bytes.

## 18. Email
`services/email.py::send_alert` is scheduled with FastAPI `BackgroundTasks` after a high-risk prediction is saved.
It first inserts an `email_alerts` row (unique per prediction), then delivers according to `EMAIL_MODE` and
records the outcome. Exceptions are caught and stored as `failed`; the user's request is never affected.

## 19. Error handling and logging
* Validation: 422 with field list. Business errors: `HTTPException` with a clear `detail`.
* Model problems: `ModelUnavailable` -> 503 with the reason (e.g. "Run `python -m ml.train` first").
* Unhandled exceptions: logged with stack trace (`app` logger), generic 500 to the client.
* Logs contain ids and event names only: no passwords, tokens, inputs, probabilities or risk levels.

## 20. Security measures and known limitations
See SECURITY_AND_PRIVACY.md and KNOWN_LIMITATIONS.md.

## 21. Testing strategy
* `tests/unit`: scoring, recommendations, security utilities, schema-spec consistency, email modes, PDF.
* `tests/ml`: loaders, leakage checks, hybrid shapes/class order, metric correctness, artifact reproducibility,
  SHAP additivity.
* `tests/integration`: the whole API through TestClient with an isolated DB and file-mode email.
* `frontend/tests`: components, validation, auth pages (fetch mocked).
* `e2e/`: real browser against a real server and the built frontend.
See TESTING_AND_QA_GUIDE.md.

## Tracing one request end to end

User submits the heart form:

1. `pages/Assess.tsx::submit` validates every field against the spec, converts blanks to `null`, and calls
   `api.predict("heart", features, lifestyle)`.
2. `POST /api/predict/heart` -> `routers/predictions.py::predict_heart`. FastAPI validates the body with
   `schemas.HeartRequest` (ranges, allowed codes, no extra fields) and resolves `get_current_user`
   (JWT decode, revoked check, user lookup).
3. `_run`: per-user rate limit; `request.app.state.registry.get("heart")` returns the loaded `TaskModel`.
4. `TaskModel.predict`: builds a 1-row DataFrame in canonical order (None -> NaN); `hybrid.predict_proba`
   (imputation/encoding/scaling inside each member pipeline, then the weighted combination); member RF/ANN
   probabilities; sanity checks; risk score `1 - P(0)`; risk band; warnings (missing optional inputs,
   out-of-range values, component disagreement, uncertain grade).
5. `HybridExplainer.explain_one`: permutation SHAP on the hybrid's `predict_proba`; adds `any_disease` view and
   plain-language summary.
6. `recommend(...)`: disease rules + lifestyle rules + BMI + lifestyle score, sorted by priority.
7. A `Prediction` row with inputs, lifestyle and the whole result is committed. If high risk and alerts are on,
   `_alert_job` is queued.
8. Response `PredictionOut` -> the frontend navigates to `/history/<id>`; `ResultPage` fetches
   `GET /api/predictions/<id>` and renders `PredictionView`.
9. "Download PDF report" calls `GET /api/predictions/<id>/report.pdf` -> ownership check -> `build_report`.

## Adding features and maintaining the project

**Add an input feature to a task:** update the spec in `ml/data.py` (and the loader/encoder), mirror it in
`schemas.py` (the consistency test will fail until you do), retrain, regenerate the evaluation report, update the
API docs. The frontend form updates automatically.

**Add a new disease task:** add a loader + spec + entry in `TASKS`, extend `load_task` in `ml/train.py`, add a
request schema and endpoint, extend the CHECK constraint on `predictions.disease` (needs a migration on existing
DBs), add rules in `recommend.py`, add tests.

**Change a recommendation rule:** edit `recommend.py`, update RECOMMENDATION_ENGINE.md, run
`pytest tests/unit/test_scoring_and_recommend.py`.

**Change models/hyperparameters:** edit grids in `ml/pipelines.py`, run `python -m ml.train`, then
`python scripts/make_eval_report.py`, then the full test suite (artifact tests check reproducibility).

**Upgrade scikit-learn:** update `requirements.txt`, retrain (the API refuses old pickles), rerun tests.

**Coding conventions:** type hints, small pure functions in services, no secrets in code, never log health data.
