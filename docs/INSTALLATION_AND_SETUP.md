# Installation and setup

The project was built and verified on Linux (Python 3.13.16, Node 22.22.0, npm 10.9.4). Your computer could not
be reached during the build, so the Windows commands below follow standard Python/Node usage but were not run
on your machine. Each step has a check so you can confirm it worked.

Commands assume the project folder is `fyp-xai-health` on your Desktop. Adjust the path if you put it elsewhere.

## 1. Prerequisites

| Tool | Version | Check |
|---|---|---|
| Python | 3.11, 3.12 or 3.13 (64-bit) | `python --version` (Windows) / `python3 --version` |
| Node.js | 20 or 22 LTS (npm 10+) | `node --version`, `npm --version` |
| Disk | about 1.5 GB for both environments | |

Windows: install Python from python.org and tick "Add python.exe to PATH". Install Node.js LTS from nodejs.org.

## 2. Backend environment

**Windows (PowerShell)**
```powershell
cd $HOME\Desktop\fyp-xai-health
python -m venv .venv
.\.venv\Scripts\Activate.ps1          # if blocked: Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
python -m pip install --upgrade pip
pip install -r requirements.txt
```

**macOS / Linux**
```bash
cd ~/Desktop/fyp-xai-health
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Check: `python -c "import sklearn, shap, fastapi; print(sklearn.__version__)"` prints `1.9.1`.

If pip cannot find a wheel for your Python version, use the fallback (then you **must** retrain in step 5):
```
pip install -r requirements-flexible.txt
```

For running the tests also install: `pip install -r requirements-dev.txt` and, for the browser test,
`python -m playwright install chromium`.

## 3. Configuration

```powershell
copy .env.example .env        # macOS/Linux: cp .env.example .env
python -c "import secrets; print(secrets.token_urlsafe(48))"
```
Paste the printed value as `SECRET_KEY` in `.env`. Leave `EMAIL_MODE=disabled` unless you want alerts (step 7).
Without a `.env`, development mode still runs with a random key that changes on every restart (users must log in
again after each restart).

## 4. Frontend

```bash
cd frontend
npm ci            # installs the exact versions from package-lock.json (.npmrc sets legacy-peer-deps)
npm run build     # creates frontend/dist, served by the backend
cd ..
```
Check: `frontend/dist/index.html` exists.

## 5. Models

Trained models are already included in `artifacts/models/`. They load only with scikit-learn 1.9.1. To retrain
(required after `requirements-flexible.txt`, or after changing data/code):
```bash
python -m ml.train          # about 10 minutes on 2 CPU cores
python scripts/make_eval_report.py
```
Optional: `python -m ml.audit_datasets` (dataset profile) and `python -m ml.external_t1d_check` (needs the
de-identified cohort in `data/restricted/`).

## 6. Start the application

From the project root with the virtual environment active:
```bash
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```
Open http://127.0.0.1:8000. The database `data/app.db` is created on first start.

Check: http://127.0.0.1:8000/api/health shows `"status": "ok"` and both models `"loaded"`.

**Development mode with hot reload** (two terminals):
```bash
# terminal 1
python -m uvicorn backend.app.main:app --reload --port 8000
# terminal 2
cd frontend && npm run dev
```
Then open http://localhost:5173 (Vite proxies `/api` to port 8000).

## 7. Email alerts (optional)

For local testing without sending anything: `EMAIL_MODE=file`. Alerts are written as `.eml` files to
`artifacts/qa/email_outbox/` (or `EMAIL_OUTBOX_DIR`).

For real email, set in `.env`:
```
EMAIL_MODE=smtp
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USE_TLS=true
SMTP_USERNAME=your.address@gmail.com
SMTP_PASSWORD=<an app password, not your normal password>
SMTP_FROM=your.address@gmail.com
APP_PUBLIC_URL=http://127.0.0.1:8000
```
Restart the server. An alert is attempted once per high-risk prediction for users who keep alerts switched on.
The result page and `GET /api/predictions/{id}` show the alert status. Real SMTP sending was **not** tested in
this build (no credentials were available); the SMTP code path was tested with a simulated server.

## 8. Run the tests

```bash
./scripts/run_all_tests.sh          # macOS/Linux
.\scripts\run_all_tests.ps1         # Windows
```
See TESTING_AND_QA_GUIDE.md. Requires trained models and a built frontend.

## Common installation problems

| Problem | Fix |
|---|---|
| `python` opens the Microsoft Store (Windows) | Install Python from python.org, tick "Add to PATH", or use `py -3.12` instead of `python` |
| `Activate.ps1 cannot be loaded` | `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`, then reopen PowerShell |
| `No matching distribution found for scikit-learn==1.9.1` | Your Python is too old/new for the pinned wheels: use Python 3.12/3.13, or install `requirements-flexible.txt` and retrain |
| `npm ci` fails with `edgesOut` error | Make sure `frontend/.npmrc` exists (it sets `legacy-peer-deps=true`), or run `npm install --legacy-peer-deps` |
| Health shows a model as "trained with scikit-learn X" | Install `requirements.txt` exactly, or retrain with `python -m ml.train` |
| Port 8000 in use | Add `--port 8010` and open that port (also update `APP_PUBLIC_URL`) |

More in TROUBLESHOOTING.md.
