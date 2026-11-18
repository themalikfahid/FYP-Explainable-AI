# API reference

Base URL: `http://127.0.0.1:8000` (same origin as the web app). All paths start with `/api`.
Interactive OpenAPI docs: `http://127.0.0.1:8000/api/docs` (disabled when `APP_ENV=production`).

Conventions

* JSON in and out (except the PDF endpoint). Unknown fields in request bodies are rejected (422).
* **Auth:** `Authorization: Bearer <access_token>` from `/api/auth/login`. Tokens are HS256 JWTs, expire after
  `ACCESS_TOKEN_EXPIRE_MINUTES` (default 60) and are revoked by logout or password change.
* **Validation errors** (422) never echo submitted values:
  ```json
  {"detail": "Validation failed", "errors": [{"field": "features.trestbps", "message": "Input should be less than or equal to 250"}]}
  ```
* Other errors: `{"detail": "<message>"}`. 401 = not authenticated / expired / revoked; 404 = not found **or not
  yours** (identical response, so record ids cannot be probed); 409 = duplicate email; 429 = rate limited
  (`Retry-After` header); 503 = model not available; 500 = unexpected error (details only in the server log).
* Timestamps are ISO 8601 UTC (`...Z`).
* Every response carries `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`,
  `Referrer-Policy: no-referrer`, a Content-Security-Policy, and `Cache-Control: no-store` on `/api/*`.

## Public endpoints

### GET /api/health
Service status. DB connectivity check (`SELECT 1`) and model registry status.
```json
{"status": "ok", "database": "ok", "models": {"diabetes": "loaded", "heart": "loaded"}, "email_mode": "disabled", "environment": "development"}
```
`status` is `degraded` if the DB check fails or a model is not loaded (the model entry then contains the reason,
e.g. missing files or a scikit-learn version mismatch).

### GET /api/meta/features
The feature specification used by the forms and the validators: for each task `title`, ordered `features`,
`spec` (label, type `number|select`, unit, min, max, step, required, options, help) and `class_labels`, plus the
`disclaimer` text. Source: `ml/data.py`.

### GET /api/meta/models/{task}
`task` = `diabetes` | `heart`. Model card data read from `artifacts/models/<task>/metadata.json`:
`version`, `hybrid_strategy`, `hybrid_description`, `hybrid_candidates`, `split`, `class_distribution_train`,
`best_params`, `cv_train_repeated` (mean/std), `test_metrics` (all three models, incl. per-class, confusion
matrix, bootstrap CIs), `calibration`, `risk_thresholds`, `global_shap`, `leave_one_site_out_hybrid` (heart).
404 unknown task; 503 model unavailable.

### POST /api/tools/bmi
Body: `{"height_cm": 100-250, "weight_kg": 25-350, "asian_bmi_cutoffs": false}`
```json
{"bmi": 24.2, "category": "Healthy weight", "cutoffs": "WHO adult (18.5 / 25 / 30)", "healthy_weight_range_kg": [53.5, 72.0], "note": "BMI is a screening measure ..."}
```
Rate limit 60/min per IP. Nothing is stored.

### POST /api/tools/lifestyle-score
Body = the **Lifestyle object**:

| Field | Type / range |
|---|---|
| height_cm | 100-250 |
| weight_kg | 25-350 |
| sleep_hours | 0-24 |
| activity_minutes_week | 0-3000 |
| fruit_veg_servings_day | 0-20 |
| smoking | `"never"` \| `"former"` \| `"current"` |
| alcohol_units_week | 0-200 |
| asian_bmi_cutoffs | boolean, default false |

Returns `{"lifestyle_score": {score, band, components, note}, "bmi": {...}}`. Formula: RECOMMENDATION_ENGINE.md.

## Authentication

### POST /api/auth/register → 201
Body `{"email", "full_name" (1-100 chars), "password" (8-72 bytes, at least one letter and one digit)}`.
Email is lower-cased. Returns the user (`id, email, full_name, email_alerts_enabled, created_at`); never the hash.
409 if the email exists. Rate limit per IP (`LOGIN_RATE_LIMIT_PER_MINUTE`).

### POST /api/auth/login
Body `{"email", "password"}` →
```json
{"access_token": "eyJhbGciOiJIUzI1NiIs...", "token_type": "bearer", "expires_at": "2026-10-15T12:12:16Z"}
```
Wrong email and wrong password give the same 401 `"Incorrect email or password"` with similar timing.
Rate limited per IP and per email.

### POST /api/auth/logout → 204 (auth)
Adds the token's `jti` to the `revoked_tokens` table; the token stops working immediately.

### GET /api/auth/me (auth)
Current user.

### PATCH /api/auth/me (auth)
Body (all optional) `{"full_name": str, "email_alerts_enabled": bool}`. Email cannot be changed (422).

### POST /api/auth/change-password → 204 (auth)
Body `{"current_password", "new_password"}`. 400 if current is wrong. Revokes the current token; log in again.

### DELETE /api/auth/me → 204 (auth)
Body `{"password"}`. Deletes the account and, by cascade, all predictions and alert records. 400 if the
password is wrong.

## Predictions (all require auth)

### POST /api/predict/diabetes
```json
{
  "features": {"age": 45, "gender_male": 0, "polyuria": 1, "polydipsia": 1, "sudden_weight_loss": 1,
               "weakness": 1, "polyphagia": 1, "genital_thrush": 0, "visual_blurring": 1, "itching": 0,
               "irritability": 1, "delayed_healing": 0, "partial_paresis": 1, "muscle_stiffness": 0,
               "alopecia": 0, "obesity": 0},
  "lifestyle": null,
  "save": true
}
```
All 16 features required; `age` 16-90; others 0 or 1 (`gender_male` 1 = male).

### POST /api/predict/heart
```json
{"features": {"age": 63, "sex": 1, "cp": 4, "trestbps": 150, "chol": 280, "fbs": 1, "restecg": 2,
              "thalach": 105, "exang": 1, "oldpeak": 3.0, "slope": 2, "ca": 3, "thal": 7},
 "lifestyle": {"height_cm": 170, "weight_kg": 85, "sleep_hours": 6, "activity_minutes_week": 60,
               "fruit_veg_servings_day": 2, "smoking": "current", "alcohol_units_week": 0, "asian_bmi_cutoffs": false}}
```

| Field | Values | Required |
|---|---|---|
| age | 18-100 | yes |
| sex | 1 male, 0 female | yes |
| cp | 1 typical angina, 2 atypical, 3 non-anginal, 4 asymptomatic | yes |
| trestbps | 70-250 mm Hg | yes |
| chol | 80-700 mg/dL or null | no |
| fbs | 1 if fasting sugar > 120 mg/dL | yes |
| restecg | 0 normal, 1 ST-T abnormality, 2 LV hypertrophy | yes |
| thalach | 50-230 bpm | yes |
| exang | 0/1 | yes |
| oldpeak | -3 to 7 | yes |
| slope | 1 up, 2 flat, 3 down, or null | no |
| ca | 0-3 or null | no |
| thal | 3 normal, 6 fixed, 7 reversible, or null | no |

`lifestyle` is optional and only feeds BMI, lifestyle score and recommendations. `save=false` returns a result
with `"id": null` and stores nothing (no history, no alert).

**Response (both tasks, abridged real output from `artifacts/qa/example_prediction_response.json`):**
```json
{
  "id": 1, "disease": "heart", "created_at": "2026-10-15T11:12:16.985027Z",
  "inputs": {"age": 63.0, "sex": 1, "...": "..."}, "lifestyle": {"...": "..."},
  "predicted_class": 3, "risk_score": 0.9928, "risk_level": "high",
  "model_version": "heart-hybrid-2026-10-15T10:49:54+00:00", "alert_status": null,
  "result": {
    "predicted_label": "Disease grade 3",
    "probabilities": {"0": 0.0072, "1": 0.1180, "2": 0.1130, "3": 0.4486, "4": 0.3132},
    "risk_score_definition": "estimated probability of any heart disease grade (1-4)",
    "risk_thresholds": {"low_below": 0.3, "high_at_or_above": 0.7},
    "components": {"random_forest": {"0": 0.0159, "...": "..."}, "ann": {"0": 0.0035, "...": "..."}, "max_disagreement": 0.229},
    "warnings": ["No disease grade is clearly favoured (top probability 45%); ..."],
    "probability_note": "Probabilities are model estimates ...",
    "model": {"version": "...", "production_model": "Hybrid RF + ANN (weighted soft voting, RF 0.3 / ANN 0.7)",
              "test_metrics": {"accuracy": 0.527, "f1_macro": 0.385, "any_disease_roc_auc": 0.900, "n_test": 184}},
    "explanation": {
      "method": "SHAP PermutationExplainer on the full RF+ANN hybrid pipeline (probability units)",
      "explained_class": 3, "base_value": 0.142, "predicted_probability": 0.4486,
      "contributions": [{"feature": "ca", "value": 3.0, "shap": 0.214}, {"feature": "oldpeak", "value": 3.0, "shap": 0.118}],
      "summary": ["Major vessels coloured by fluoroscopy = 3 raised the estimated probability of 'Disease grade 3' by 21.4 percentage points.", "..."],
      "per_class": {"0": {"base_value": 0.484, "shap": {"age": -0.017, "...": "..."}}, "...": "..."},
      "any_disease": {"base_value": 0.516, "shap": {"...": "..."}},
      "additivity_error": 5.6e-17
    },
    "recommendations": {
      "items": [{"category": "follow_up", "priority": "high", "text": "Arrange a review with a doctor ...",
                 "rule": "risk_level == high", "source": "ACC/AHA Guideline on the Primary Prevention of Cardiovascular Disease (2019)"}],
      "lifestyle_score": {"score": 40, "band": "Needs improvement", "components": {"...": "..."}},
      "bmi": {"bmi": 29.4, "category": "Overweight", "...": "..."},
      "top_risk_factors": ["ca", "oldpeak", "exang"], "disclaimer": "This application is an educational ..."
    }
  }
}
```
`risk_score` = P(positive) for diabetes, 1 - P(grade 0) for heart. `explanation.any_disease` exists for heart
only. Errors: 401, 422, 429 (`PREDICT_RATE_LIMIT_PER_MINUTE` per user), 503 (model missing/corrupt/version
mismatch). Side effects when `save` is true: inserts a `predictions` row; if `risk_level == "high"` and the user
has alerts enabled, schedules one email alert (see SECURITY_AND_PRIVACY.md).

The combination strategy actually deployed (stacking or weighted soft voting) is given in `model.production_model`.

### GET /api/predictions
Query: `disease` (`diabetes`|`heart`, optional), `limit` 1-100 (default 20), `offset` >= 0. Newest first.
```json
{"total": 1, "items": [{"id": 1, "disease": "heart", "created_at": "2026-10-15T11:12:16.985027Z", "predicted_class": 3, "risk_score": 0.9928, "risk_level": "high"}]}
```

### GET /api/predictions/{id}
The full stored record (same shape as the prediction response, including `alert_status`:
`null` | `pending` | `sent` | `written_to_file` | `disabled` | `failed`). 404 if missing or owned by another user.

### DELETE /api/predictions/{id} → 204
Deletes the record and its alert row. 404 if missing or not yours.

### GET /api/predictions/{id}/report.pdf
`application/pdf`, `Content-Disposition: attachment; filename="health-report-<id>.pdf"`, `Cache-Control: no-store`.
Built on request from the stored record (never cached on disk). 404 if missing or not yours.

## Insights (all require auth; added in v2)

### POST /api/assess/t1d
Rule-based Type-1 clinical-pattern indicator (no ML; see KNOWN_LIMITATIONS). Body: `age` (1-100) plus 0/1 symptom flags
(`polyuria, polydipsia, weight_loss, fatigue, blurred_vision, bedwetting, recurrent_infections, abdominal_pain_vomiting,
fruity_breath_or_fast_breathing, family_history_t1d, other_autoimmune`), optional `symptom_weeks`, `bmi_category`,
`fasting_glucose`, `random_glucose` (mg/dL), `hba1c` (%). Nothing is stored. Returns `score` 0-100, `band`
(`low|possible|strong`), `contributions`, `lab_flags`, `meets_diagnostic_range`, `emergency_warning` (bool) with
`emergency_signs`, `next_steps`, `cohort_comparison` and `limitations`.

### POST /api/whatif/{diabetes|heart}
Body `{features, changes}`. Re-runs the hybrid model with `changes` applied; nothing is saved. Returns `baseline`,
`scenario`, `delta` and `per_change` (one-at-a-time sensitivity). Unknown features or out-of-range values are rejected.

### GET /api/analytics/summary
Per-user totals, `risk_distribution`, `latest` per disease with `trend`, time `series`, `recent` rows and `top_drivers`
(top SHAP factors of the latest result per disease).

### Confidence block
Every prediction result now carries `confidence` = `{tier: confident|inconclusive|unrated, value, threshold,
expected_accuracy_if_confident, coverage_at_threshold, overall_cv_accuracy, note}` and `model.cross_validated`
(out-of-fold accuracy and the confident-subset accuracy). `GET /api/meta/models/{task}` returns the full
`cross_validated` report including the accuracy/coverage table.

## Frontend routes served by the backend
When `frontend/dist/index.html` exists, every non-`/api` path returns the single-page app (static files from
`frontend/dist`, path traversal outside that folder is refused).


## Coronary artery screen

`POST /api/predict/cad` takes `{features, lifestyle?, save?}` like the other tasks. Required: age, sex, bmi, diabetes_hx,
hypertension, current_smoker, family_history, dyslipidemia, bp_systolic, pulse, typical_chest_pain, atypical_chest_pain,
nonanginal_pain, dyspnea, function_class (0-3), q_wave, st_elevation, st_depression, t_inversion, lvh. Optional:
fbs_mgdl, ldl, hdl, triglycerides, esr, hemoglobin, ef_tte. `disease=cad` works in `GET /api/predictions`,
`/api/whatif/cad` and `/api/meta/models/cad`.


## ECG heartbeat classifier

`POST /api/assess/ecg` with `{"beat": [187 floats scaled 0-1]}` returns the predicted class, class probabilities,
confidence tier, abnormal probability and a 17-window occlusion saliency. Nothing is saved. `GET /api/meta/ecg` returns
the test report and one real sample beat per class.
