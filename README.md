# Clarity Screen: Explainable AI Hybrid Model for Early Detection of Type-1 Diabetes and Multiclass Heart Disease Classification

UCP Final Year Project F26DS003. Hybrid Random Forest + neural network models with SHAP explanations, a confidence gate,
a rule-based Type-1 pattern indicator, what-if simulator, analytics dashboard, PDF reports and email alerts.
**Educational screening tool, not a medical device.**

## Quick start
```bash
python -m venv .venv && . .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                  # set SECRET_KEY
python -m ml.train && python -m ml.oof_eval           # only if you want to retrain (models are included)
cd frontend && npm install && npm run build && cd ..
python -m uvicorn backend.app.main:app --port 8000    # app + API at http://127.0.0.1:8000
```
Development: `cd frontend && npm run dev` (Vite proxies `/api`).

## Tests
`bash scripts/run_all_tests.sh` runs unit, ML, integration (112 tests), frontend (typecheck + vitest) and the Playwright
browser journey (needs `npx playwright install chromium` or `CHROMIUM_PATH`). Screenshots land in `artifacts/qa/screenshots/`.

## Layout
`ml/` training and evaluation, `backend/` FastAPI app, `frontend/` React + Three.js + Framer Motion UI, `artifacts/`
trained models and evaluation, `docs/` API, dataset audit, methodology and `ACCURACY_AND_LIMITATIONS.md`.

## Honest accuracy
See `docs/ACCURACY_AND_LIMITATIONS.md`: diabetes about 90 % overall and 95 % when confident; heart disease-vs-none about 81 %
(90.9 % when confident); exact 5-grade heart accuracy about 52 % overall. Type 1 is rule-based because the data has no controls.


## Coronary artery screen (third model)
Besides diabetes and UCI heart disease, the app has a `cad` model trained on the Z-Alizadeh Sani angiography dataset
(88.8% cross-validated accuracy, ROC-AUC 0.92, 96% when confident). Data: `data/raw/z_alizadeh_sani/`. See
`docs/ACCURACY_AND_LIMITATIONS.md`.

## ECG heartbeat classifier (fourth model)
Multiclass MIT-BIH beat classifier: 97.6% test accuracy on 21,892 unseen beats, 85% balanced accuracy. Train with `python -m ml.ecg --data-dir <folder>`.
