# Project architecture

Local-first, three parts: a React single-page app, a FastAPI backend that also serves the built app, and an
offline ML training pipeline that writes model artifacts the backend loads.

## System overview

```mermaid
flowchart LR
    subgraph Browser
        UI["React + TypeScript SPA<br/>frontend/src"]
    end
    subgraph Backend["FastAPI app (backend/app)"]
        R1["routers/auth.py"]
        R2["routers/predictions.py"]
        R3["routers/meta.py"]
        SEC["security.py<br/>bcrypt, JWT, rate limit"]
        INF["services/inference.py<br/>Registry + TaskModel"]
        EXP["ml/explain.py<br/>HybridExplainer (SHAP)"]
        REC["services/recommend.py<br/>+ scoring.py"]
        PDF["services/pdf.py<br/>ReportLab"]
        MAIL["services/email.py<br/>disabled | file | smtp"]
        DB[("SQLite<br/>data/app.db")]
    end
    subgraph Offline["Training (ml/)"]
        DATA["data/raw/*"] --> TRAIN["ml/train.py"]
        TRAIN --> ART["artifacts/models/&lt;task&gt;/<br/>hybrid, rf, ann .joblib<br/>metadata.json, shap_background.csv,<br/>global_shap.json"]
    end
    UI -- "fetch /api/* (Bearer JWT)" --> R1 & R2 & R3
    R1 --> SEC --> DB
    R2 --> SEC
    R2 --> INF --> EXP
    R2 --> REC
    R2 --> DB
    R2 --> PDF
    R2 -. background task .-> MAIL --> DB
    R3 --> INF
    ART -- loaded at startup --> INF
    MAIL -- "SMTP (optional)" --> SMTPS["Mail server"]
```

## Module responsibilities

| Module | Responsibility |
|---|---|
| `ml/data.py` | Dataset loaders, cleaning, **feature specification** shared by training, API and UI |
| `ml/pipelines.py` | Preprocessors, RF, ANN, stacking and soft-voting hybrids, tuning grids |
| `ml/train.py` | Split, tune, select hybrid, CV comparison, test evaluation, SHAP global, artifacts |
| `ml/evaluate.py` | Metrics, bootstrap CIs, calibration, plots |
| `ml/explain.py` | SHAP on the hybrid output; global importance; plain-language summaries |
| `ml/audit_datasets.py`, `ml/external_t1d_check.py` | Dataset profiling; exploratory T1D cohort check |
| `backend/app/main.py` | App factory, startup (DB + model loading), CORS, security headers, error handlers, SPA serving |
| `backend/app/config.py` | Environment-based settings |
| `backend/app/security.py` | Password hashing, JWT, auth dependencies, token revocation, rate limiter |
| `backend/app/routers/*` | HTTP endpoints |
| `backend/app/services/*` | Inference, recommendations, scoring, PDF, email |
| `frontend/src/api.ts` | Typed API client, token storage |
| `frontend/src/pages/*`, `components/*` | Screens and UI components |

## Training pipeline

```mermaid
flowchart TD
    A["Load raw data<br/>(Hungarian from raw 76-attr file)"] --> B["Clean: invalid zeros -> missing"]
    B --> C["Drop exact duplicates"]
    C --> D["Stratified 80/20 split (seed 42)"]
    D -->|train| E["GridSearchCV RF (5-fold, macro F1)"]
    D -->|train| F["GridSearchCV ANN (5-fold, macro F1)"]
    E & F --> G["Hybrid candidates<br/>stacking (OOF, LR meta) vs weighted soft voting<br/>chosen by 5-fold CV on train"]
    G --> H["Repeated CV comparison on train (5x3)"]
    H --> I["Fit RF, ANN, hybrid on full train"]
    D -->|test, used once| J["Evaluate: metrics, CIs, calibration, confusion"]
    I --> J
    I --> K["Global SHAP of hybrid on test rows"]
    I --> L["Save joblib + metadata + background"]
    J & K --> M["Plots + metadata.json"]
```

## Prediction request flow

```mermaid
sequenceDiagram
    participant U as Browser
    participant A as FastAPI router
    participant S as security
    participant M as TaskModel (hybrid)
    participant X as HybridExplainer
    participant R as recommend()
    participant D as SQLite
    participant E as email (background)
    U->>A: POST /api/predict/heart {features, lifestyle}
    A->>S: verify JWT, check revoked jti, load user
    A->>A: Pydantic validation (ranges, options, extra fields)
    A->>A: rate limit per user
    A->>M: predict(features)
    M->>M: hybrid.predict_proba + member RF/ANN probabilities
    M->>X: explain_one (Permutation SHAP over full pipeline)
    M-->>A: probabilities, risk, warnings, explanation
    A->>R: recommendations (risk, inputs, top SHAP, lifestyle)
    A->>D: INSERT predictions
    A-->>U: 200 PredictionOut
    A-)E: if high risk and alerts on: send_alert
    E->>D: INSERT email_alerts (unique per prediction), status
```

## Authentication flow

```mermaid
sequenceDiagram
    participant U as Browser
    participant B as Backend
    participant D as SQLite
    U->>B: POST /api/auth/register
    B->>D: INSERT user (bcrypt hash)
    U->>B: POST /api/auth/login
    B->>D: SELECT user; bcrypt verify
    B-->>U: JWT (sub, jti, exp 60 min)
    Note over U: token kept in memory + sessionStorage
    U->>B: requests with Authorization: Bearer
    U->>B: POST /api/auth/logout
    B->>D: INSERT revoked_tokens(jti)
```

## Report generation

`GET /api/predictions/{id}/report.pdf` -> ownership check -> `services/pdf.py::build_report(prediction, user)`
reads the stored `inputs` and `result` and draws: header, result with risk band, probability table (hybrid and
both components), warnings, SHAP bar chart and summary, inputs table, BMI and lifestyle score,
recommendations with sources, model information and the disclaimer. The PDF is built in memory and streamed;
nothing is written to disk.

## Deployment shape

Development: Vite dev server on :5173 proxies `/api` to Uvicorn on :8000. Local "production": `npm run build`
once, then only Uvicorn on :8000 serves both the API and `frontend/dist`.
