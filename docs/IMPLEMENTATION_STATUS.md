# Implementation status

Legend: **Done (verified)** = implemented and confirmed by executed tests or measurements.
**Partial** = works with stated restrictions. **Blocked** = needs something outside this build.
**Changed** = implemented differently from the proposal, with reasons.

| # | Proposal requirement | Status | Notes |
|---|---|---|---|
| 1 | Type-1 Diabetes risk classification | **Changed** | Data does not identify T1D. Implemented as diabetes (type unspecified) symptom screening; T1D cohort used for an exploratory check. DATASET_AUDIT.md |
| 2 | Multiclass heart disease classification | Done (verified) | 5 grades (0-4) on UCI 4-site data; any-disease score as headline |
| 3 | Hybrid RF + ANN | Done (verified) | Stacking and weighted soft voting both implemented; soft voting selected by train CV for both tasks |
| 4 | Leakage-safe ensemble | Done (verified) | OOF stacking, preprocessing inside pipelines, dedup before split, test used once |
| 5 | Probabilities and qualified confidence | Done (verified) | Hybrid + component probabilities, disagreement/out-of-range/missing warnings, calibration reported |
| 6 | SHAP explainable AI | Done (verified) | Permutation SHAP on the hybrid output, additivity tested |
| 7 | Global + individual explanations | Done (verified) | Model page, landing page, result page, PDF |
| 8 | Personalised recommendations | Done (verified) | Rule engine with sources; no medication |
| 9 | BMI and lifestyle score | Done (verified) | WHO and WHO-Asian cut-offs; documented 0-100 score |
| 10 | Secure registration/login | Done (verified) | bcrypt, JWT, revocation, rate limiting |
| 11 | Dashboard and forms | Done (verified) | Forms generated from backend spec, responsive |
| 12 | History and protected records | Done (verified) | Owner-only access, delete, pagination |
| 13 | PDF reports | Done (verified) | Content checked against stored record |
| 14 | Email alerts for high risk | **Partial** | Disabled/file/SMTP modes, duplicate prevention, failure handling verified; real SMTP delivery **blocked** (no credentials) |
| 15 | Secure data handling | Done (verified) for a local prototype | See SECURITY_AND_PRIVACY.md for remaining production gaps |
| 16 | Evaluation and testing | Done (verified) | 117 automated tests passing; MODEL_EVALUATION.md from real runs |
| 17 | Documentation | Done | README + 20 documents in docs/ |
| | TensorFlow/Keras ANN | **Changed** | scikit-learn MLP (justified in MODEL_METHODOLOGY.md) |
| | PostgreSQL/MongoDB, cloud | **Changed** | SQLite local-first (the brief allowed SQLite); SQLAlchemy keeps PostgreSQL possible |
| | Jira/GitHub | Not used | Git/GitHub explicitly excluded by the brief |
| | Install on the user's desktop | **Blocked during build** | Computer unreachable; delivered as a project folder/zip with instructions |
