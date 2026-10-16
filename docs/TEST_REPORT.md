# Test report

Date: 2026-10-15. Environment: Linux x86-64 (2 vCPU, 7 GB RAM), Python 3.13.16, Node 22.22.0, Chromium 1194
(Playwright). Command: `./scripts/run_all_tests.sh`. Evidence: `artifacts/qa/log_*.txt`, `junit_*.xml`,
`screenshots/`, `downloads/`.

Software correctness, predictive performance and clinical validity are reported separately. Passing tests
show the software behaves as specified; they say nothing about clinical usefulness.

## 1. Totals

| Layer | Tests | PASS | FAIL | BLOCKED | NOT EXECUTED |
|---|---|---|---|---|---|
| Python unit (`tests/unit`) | 51 | 51 | 0 | 0 | 0 |
| ML (`tests/ml`) | 16 | 16 | 0 | 0 | 0 |
| Backend integration (`tests/integration`) | 37 | 37 | 0 | 0 | 0 |
| Frontend unit/component (`frontend/tests`, plus `tsc --noEmit`) | 12 | 12 | 0 | 0 | 0 |
| End-to-end browser journey (`e2e/`) | 1 (covers 11 required steps + extras) | 1 | 0 | 0 | 0 |
| **Total** | **117** | **117** | **0** | **0** | **0** |

Additional verification: a clean virtual environment created from `requirements-dev.txt` ran the 104 Python
tests: 104 passed.

## 2. Requirement coverage

| Requirement | Status | Evidence |
|---|---|---|
| Registration / login / logout / token revocation | PASS | `test_register_login_me_logout_flow`, e2e |
| Password policy, hashing, generic login errors, rate limiting | PASS | unit + integration security tests |
| Cross-user access blocked (record, PDF, delete) | PASS | `test_users_cannot_access_each_others_records` |
| Unauthenticated access to protected endpoints rejected | PASS | `test_protected_endpoints_reject_bad_auth` (4 auth variants x 6 endpoints), e2e step 11 |
| Diabetes prediction with real model output | PASS | `test_predict_diabetes_high_and_low`, e2e |
| Heart prediction (5 classes), missing optional inputs | PASS | `test_predict_heart_with_lifestyle_and_missing_optionals`, e2e |
| Invalid inputs rejected (range, option, missing, extra, type) | PASS | `test_predict_rejects_invalid_inputs` (8 cases) |
| Probabilities valid, multiclass dimensions, class order | PASS | ML tests + `_check_prediction` |
| Leakage-safe preprocessing; OOF stacking configuration | PASS | `test_preprocessing_fitted_on_training_fold_only`, `test_stacking_uses_out_of_fold_cv` |
| Saved models reproduce stored test predictions and metrics | PASS | `test_artifacts_reproduce_saved_test_predictions_and_metrics` |
| Metric calculations correct on known examples | PASS | `test_metrics_on_known_example`, `test_multiclass_metrics_any_disease` |
| SHAP explains the hybrid output, additive per class | PASS | `test_shap_explains_hybrid_output_additively`, API `additivity_error` |
| SHAP visible in UI, class switch works | PASS | e2e |
| Recommendations: rules fire, sources present, no medication | PASS | 6 recommendation tests |
| BMI and lifestyle score formulas and boundaries | PASS | 22 scoring tests |
| History list, filter, pagination, delete, persistence | PASS | `test_history_pagination_filter_and_delete`, e2e |
| PDF generated, opens, content matches stored prediction | PASS | `test_pdf_report_contents` (text extracted with pypdf), e2e download starts with `%PDF-` |
| Email alert once per high-risk prediction, opt-out respected | PASS | `test_high_risk_triggers_single_alert_file`, `test_alerts_respect_opt_out`, unit email tests |
| Email failure does not break prediction | PASS | `test_smtp_failure_does_not_break_prediction`, unreachable/unconfigured/refused tests |
| Real SMTP delivery | **BLOCKED** | No SMTP credentials available. SMTP path tested only with a simulated server |
| Missing / corrupt model files, version mismatch | PASS | three 503/health tests |
| Database failure reported | PASS | `test_database_failure_reported_in_health` |
| Account deletion cascades | PASS | `test_account_deletion_cascades` |
| UTC timestamps in API | PASS | `test_timestamps_are_utc_aware` |
| Security headers, CORS restriction | PASS | two integration tests |
| Responsive layout at 390 px (no horizontal scroll) | PASS | e2e (landing + result page) |
| Installation on the user's own computer | **NOT EXECUTED** | Computer not reachable during the build |

## 3. End-to-end journey (e2e/test_e2e.py)

Landing page with live global SHAP -> protected route redirects to login -> register (weak password rejected,
then accepted) -> log in -> diabetes form (empty submit shows errors; errors clear as fields are filled) ->
real model result with SHAP ledger, recommendations, BMI -> PDF downloaded and checked -> heart form with
optional fields blank -> result shows missing-input warning, explanation switched between grade 0 and "any
disease" -> history shows 2 records -> BMI/lifestyle calculator -> model information page -> mobile layout
checks -> log out -> protected page redirects and `/api/predictions` returns 401. No unexpected console errors.

Screenshots: `artifacts/qa/screenshots/01_landing_desktop.png` ... `09_result_mobile.png`.

## 4. Defects found and fixed during QA

| # | Defect | Found by | Root cause | Fix | Regression test |
|---|---|---|---|---|---|
| 1 | ANN scored far below RF (CV macro F1 0.69 vs 0.92) | training run | Validation-based early stopping on tiny folds stopped training too early | Removed early stopping; tune L2 and epoch cap | CV numbers in metadata |
| 2 | Hungarian disease grades collapsed to 0/1 | dataset audit | Distributed processed file | Parse raw 76-attribute file | `test_heart_loader_graded_labels_and_cleaning` |
| 3 | BMI 30.0 shown but labelled "Overweight" | unit test | Category computed on unrounded float (29.999...) | Categorise the displayed (rounded) value | `test_bmi_values`, `test_bmi_boundary_exact` |
| 4 | Registration rejected test emails | unit test | `email-validator` rejects reserved `.test` TLD | Tests use `@example.com` | all auth tests |
| 5 | Horizontal scroll on mobile result page | e2e | Long option text in the "Explain" select | `max-width/min-width` on inline select | e2e mobile check |
| 6 | e2e failed only when run after the other suites | full run | `tests/conftest.py` sets `FRONTEND_DIST` in `os.environ`, inherited by the e2e server | e2e passes all relevant settings explicitly | full `run_all_tests` |
| 7 | Timestamps returned without timezone (shown 5 h off in Pakistan) | API review | SQLite drops tzinfo | `UTCDateTime` type in schemas | `test_timestamps_are_utc_aware` |
| 8 | Field errors stayed visible after the user fixed the field | screenshot review | Errors only recalculated on submit | Clear a field's error on change | e2e assertion |
| 9 | Headline score "100%" while the ledger showed 99.8% | screenshot review | `toFixed(0)` | One decimal | visual check |
| 10 | 3 high + 2 critical npm advisories (react-router, vitest/tinypool, esbuild) | `npm audit` | Outdated packages | react-router-dom 7.18.4, vite 6.4.4, vitest 4.1.11 | `npm audit`: 0 |
| 11 | Risk level written to server logs | security review | Log statement | Log ids only | code review |
| 12 | `/redoc` exposed even in production | route review | FastAPI default | `redoc_url=None` | code review |

No test was weakened to make it pass. One expectation was corrected (defect 3: 99.9 kg at 200 cm is shown as BMI
25.0 and is now consistently "Overweight").

## 5. Model evaluation (summary, see MODEL_EVALUATION.md)

| Task | Model | Test accuracy | Test macro F1 | Test ROC-AUC | CV macro F1 (train) |
|---|---|---|---|---|---|
| Diabetes (n=51) | RF | 0.922 | 0.914 | 0.966 | 0.917 ± 0.043 |
| | ANN | 0.804 | 0.790 | 0.941 | 0.913 ± 0.057 |
| | Hybrid | 0.804 | 0.790 | 0.946 | 0.915 ± 0.056 |
| Heart 5-class (n=184) | RF | 0.538 | 0.422 | 0.777 (macro OvR) | 0.371 ± 0.037 |
| | ANN | 0.533 | 0.382 | 0.760 | 0.359 ± 0.039 |
| | Hybrid | 0.527 | 0.385 | 0.768 | 0.361 ± 0.038 |
| Heart any disease | Hybrid | 0.826 | n/a | 0.900 | n/a |

## 6. Performance (artifacts/qa/performance.json, same 2-vCPU machine)

| Operation | Median | p95 |
|---|---|---|
| Startup incl. loading both models and explainers | 0.32 s | |
| Login (bcrypt cost 12) | 324 ms | |
| Diabetes prediction incl. SHAP, recommendations, DB write | 498 ms | |
| Heart prediction incl. SHAP | 586 ms | |
| Model inference only (no SHAP), heart / diabetes | 64 / 49 ms | |
| PDF report | 35 ms | |
| History list (50) | 10 ms | |
| Prediction detail | 5 ms | |
| Health check | 2 ms | |

Optimisation attempted: reusing the hybrid's fitted members instead of separately loaded RF/ANN for the
component probabilities. Measured effect on model-only latency: none (about 60 ms before and after, see
`performance_before_optimisation.json`). It was kept because it guarantees the displayed component probabilities
are exactly the hybrid's inputs. No caching of results across users is done.

## 7. Security checks
`pip-audit`: no known vulnerabilities. `npm audit`: 0 vulnerabilities. See SECURITY_AND_PRIVACY.md.
