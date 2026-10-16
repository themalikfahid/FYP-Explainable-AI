# Troubleshooting

"Verified" means the problem was reproduced and the fix confirmed during this build. Other entries are standard
fixes that were not reproduced here.

## Installation and dependencies

| Error | Diagnosis | Solution |
|---|---|---|
| `No matching distribution found for scikit-learn==1.9.1` (or numpy/pandas) | Python version without wheels for the pins | Use Python 3.12 or 3.13; or `pip install -r requirements-flexible.txt` and retrain |
| `npm ci` / `npm install`: `Cannot read properties of null (reading 'edgesOut')` | npm arborist bug with vitest's optional peer dependencies | Keep `frontend/.npmrc` (`legacy-peer-deps=true`) or add `--legacy-peer-deps`. **Verified.** |
| `ModuleNotFoundError: No module named 'backend'` / `'ml'` | Command not run from the project root | `cd` to `fyp-xai-health` and run `python -m ...` |
| PowerShell won't activate the venv | Execution policy | `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` |

## Startup

| Symptom | Diagnosis | Solution |
|---|---|---|
| Log: `SECRET_KEY not set; using an ephemeral random key` | No `.env` | Create `.env` from `.env.example` with a real key. Without it users are logged out on every restart |
| `ValidationError ... SECRET_KEY` on start | `APP_ENV=production` with a short or placeholder key | Generate a key: `python -c "import secrets; print(secrets.token_urlsafe(48))"` |
| `[Errno 98/10048] address already in use` | Port 8000 busy | `--port 8010` |
| Browser shows `{"detail":"Not Found"}` at `/` | Frontend not built | `cd frontend && npm run build`, restart backend |

## Database

| Symptom | Solution |
|---|---|
| `sqlite3.OperationalError: unable to open database file` | The folder in `DATABASE_URL` must exist and be writable; the default `data/` is created automatically |
| `no such column` after changing `models.py` | No migrations: delete `data/app.db` in development (loses data) or add Alembic |
| `/api/health` shows `"database": "error"` | Check `DATABASE_URL`, file permissions, disk space |

## Models and API

| Symptom | Diagnosis | Solution |
|---|---|---|
| 503 `Model artifacts for 'heart' are missing` | `artifacts/models/heart/*` absent | `python -m ml.train`. **Verified** (test) |
| Health: `trained with scikit-learn X but Y is installed` | Version mismatch; API refuses to load pickles | `pip install -r requirements.txt` or retrain. **Verified** (test) |
| 503 `Failed to load 'heart' model: UnpicklingError` | Corrupt file | Retrain. **Verified** (test) |
| 422 on prediction | Value outside range / unknown option / extra field | Read `errors[].field`; ranges are in API_REFERENCE.md |
| 401 `Session has been logged out` / `Session expired` | Token revoked or older than 60 min | Log in again |
| 429 `Too many requests` | Rate limit | Wait for `Retry-After` seconds; raise limits in `.env` for local testing |
| Prediction takes ~1 s | SHAP is computed per request (about 0.5-0.7 s on 2 cores) | Expected; see performance numbers in TEST_REPORT.md |

## SHAP

| Symptom | Solution |
|---|---|
| Contribution for a blank optional field | Expected: shows the effect of "not provided" (imputed value) |
| Explanation numbers differ after retraining | Base values and attributions depend on the model and background sample; expected |
| `additivity_error` larger than 1e-6 | Should not happen; indicates a model/explainer mismatch. Retrain and run `pytest tests/ml` |

## Frontend

| Symptom | Solution |
|---|---|
| Blank page in dev at :5173 | Backend not running on :8000 (Vite proxies `/api`) |
| "Can't reach the server" banner | Backend stopped or wrong port |
| Logged out after reload in a new tab | Tokens are per tab (sessionStorage) by design |
| Old UI after code changes on :8000 | Re-run `npm run build`; hard-refresh the browser |

## PDF

| Symptom | Solution |
|---|---|
| 404 on download | Record deleted or belongs to another account |
| Garbled characters | ReportLab's built-in Helvetica covers Latin-1; non-Latin names may not render. Register a TTF font in `pdf.py` if needed |

## Email

| `alert_status` | Meaning / fix |
|---|---|
| none | Result was not high risk, or the user turned alerts off |
| `disabled` | `EMAIL_MODE=disabled` |
| `written_to_file` | `EMAIL_MODE=file`; see `EMAIL_OUTBOX_DIR` |
| `failed` + "not configured" | Set `SMTP_HOST` and `SMTP_FROM`. **Verified** (test) |
| `failed` + `SMTPAuthenticationError` | Wrong credentials; Gmail and Outlook need an app password |
| `failed` + timeout/connection refused | Wrong host/port or firewall; port 587 with `SMTP_USE_TLS=true` is typical |

## Tests
See TESTING_AND_QA_GUIDE.md, "Diagnosing common problems".
