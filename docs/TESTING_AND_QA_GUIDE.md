# Testing and QA guide

All commands run from the project root with the virtual environment active, after
`pip install -r requirements-dev.txt`. Results of the last full run: TEST_REPORT.md.

## Test layers

| Layer | Location | Command | Needs |
|---|---|---|---|
| Unit | `tests/unit/` | `python -m pytest tests/unit -q` | trained models for the PDF content test only |
| ML | `tests/ml/` | `python -m pytest tests/ml -q` | trained models for artifact/SHAP tests |
| Backend integration | `tests/integration/` | `python -m pytest tests/integration -q` | trained models |
| Frontend | `frontend/tests/` | `cd frontend && npx tsc --noEmit && npx vitest run` | `npm ci` |
| End-to-end | `e2e/test_e2e.py` | `python -m pytest e2e -q` | trained models, `npm run build`, Chromium (`python -m playwright install chromium`, or set `CHROMIUM_PATH`) |
| Everything + evidence | | `./scripts/run_all_tests.sh` or `.\scripts\run_all_tests.ps1` | all of the above |

`run_all_tests` writes `artifacts/qa/log_<layer>.txt` and `artifacts/qa/junit_<layer>.xml`.

Isolation: pytest fixtures create a fresh SQLite database and email outbox in a temp folder per test,
set `EMAIL_MODE=file` (no real email is ever sent) and use synthetic `@example.com` accounts. The e2e test starts
its own Uvicorn server on a free port with a temp database and passes every relevant setting explicitly.

## Model evaluation
```
python -m ml.train
python scripts/make_eval_report.py
```
Training is the evaluation: it prints CV and test metrics and writes `artifacts/models/*/metadata.json`, plots in
`artifacts/eval/` and the log `artifacts/eval/training_log.txt`. `tests/ml/test_ml.py::test_artifacts_reproduce_saved_test_predictions_and_metrics`
reloads the saved models and recomputes the metrics to confirm they match.

## Performance
```
python scripts/benchmark.py     # -> artifacts/qa/performance.json
```

## Security checks
```
pip-audit -r requirements.txt
cd frontend && npm audit
```

## Inspecting failures

* Run one test verbosely: `python -m pytest tests/integration/test_api.py::test_report_download -vv`
* Show print/log output: add `-s` or `-o log_cli=true --log-cli-level=INFO`.
* Stop at first failure: `-x`; rerun only last failures: `--lf` (do not use `-p no:cacheprovider` then).
* Frontend: `npx vitest run -t "ShapLedger"`; watch mode `npx vitest`.
* E2E: screenshots are saved to `artifacts/qa/screenshots/` as the journey proceeds, so the last screenshot
  shows how far it got. To watch the browser locally, change `p.chromium.launch(...)` to
  `p.chromium.launch(headless=False, slow_mo=300)` in `_launch`.

## Diagnosing common problems

| Symptom | Likely cause | Fix |
|---|---|---|
| `Model artifacts for 'heart' missing` | models not trained | `python -m ml.train` |
| Many integration tests 503 | scikit-learn version differs from training | install `requirements.txt` exactly or retrain |
| e2e: `Frontend not built` | no `frontend/dist` | `cd frontend && npm run build` |
| e2e: browser executable not found | Playwright browser not installed | `python -m playwright install chromium` or set `CHROMIUM_PATH` |
| e2e fails only when run together with `tests/` | an environment variable leaked into the server | the e2e fixture now sets `FRONTEND_DIST`, `MODELS_DIR` and limits explicitly; keep that pattern for new settings |
| 422 for an email in tests | `email-validator` rejects reserved domains like `.test`/`.local` | use `@example.com` |

## Verifying a fix

1. Reproduce with the narrowest failing test.
2. Fix the root cause (not the assertion).
3. Rerun that test, then its whole layer, then `run_all_tests` for regressions.
4. Record the change in TEST_REPORT.md (defect log).

## Generating QA reports

`run_all_tests` produces JUnit XML, which most CI tools and IDEs can display. TEST_REPORT.md is maintained by
hand from those files: copy the totals, keep the PASS/FAIL/BLOCKED/NOT EXECUTED table up to date, and add any
defect found to the defect log.
