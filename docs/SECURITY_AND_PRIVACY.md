# Security and privacy

Scope: a local, single-machine prototype handling synthetic or volunteer health inputs. This review covers what
was implemented, what was tested, and what remains before any real deployment.

## Controls

| Area | Implementation | Evidence |
|---|---|---|
| Password storage | bcrypt, cost 12, random salt per hash (`security.py`). Passwords 8-72 bytes with a letter and a digit. | `test_password_hash_roundtrip_and_salted`, `test_password_policy` |
| Login enumeration | Same 401 message for unknown email and wrong password; dummy bcrypt check equalises timing | `test_login_failures_are_generic` |
| Brute force | Sliding-window limit per IP and per email on login, per IP on register (`LOGIN_RATE_LIMIT_PER_MINUTE`, default 10); per-user limit on predictions (30/min); tools 60/min per IP | `test_login_rate_limit`, `test_rate_limiter` |
| Tokens | HS256 JWT with `exp` (60 min), `iat`, `jti`, `sub`, `type`; required claims enforced; `alg=none` and wrong keys rejected | `test_token_tampered_and_expired` |
| Logout / password change | `jti` added to `revoked_tokens`; checked on every request | `test_register_login_me_logout_flow`, `test_profile_update_and_password_change` |
| Signing key | `SECRET_KEY` from env; production refuses keys < 32 chars and the `.env.example` placeholder; development uses a random ephemeral key with a warning | `test_production_requires_secret`, `test_production_rejects_placeholder_secret` |
| Authorisation | All record queries filter by owner; other users' records return 404 (no existence leak); no admin endpoints | `test_users_cannot_access_each_others_records` |
| Report access | PDF endpoint uses the same ownership check; `Cache-Control: no-store`; built in memory, never written to disk | same test, `test_report_download` |
| Input validation | Pydantic models with ranges, allowed codes and `extra="forbid"`; 422 responses do not echo submitted values | `test_predict_rejects_invalid_inputs`, `test_register_validation_and_duplicates` |
| Mass assignment | Profile update accepts only `full_name` and `email_alerts_enabled` | `test_profile_update_and_password_change` |
| SQL injection | SQLAlchemy ORM with bound parameters only; no raw SQL besides `SELECT 1` | code review |
| CORS | Only origins in `CORS_ORIGINS`; no credentials mode | `test_cors_only_allows_configured_origin` |
| Headers | `X-Content-Type-Options`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`, CSP (`default-src 'self'`, no inline scripts), `Cache-Control: no-store` on API | `test_security_headers` |
| XSS | React escapes all rendered text; no `dangerouslySetInnerHTML`; CSP blocks inline/external scripts; fonts are bundled locally | code review |
| Static files | SPA handler only serves files inside `frontend/dist` (resolved-path check) | code review |
| Error handling | Unhandled errors return a generic 500; stack traces only in server logs | code review |
| API docs | `/api/docs` and OpenAPI disabled when `APP_ENV=production`; `/redoc` disabled | code review |
| Model files | Refuses to load on feature/class/scikit-learn version mismatch (prevents silent wrong predictions) | `test_sklearn_version_mismatch_refuses_to_load`, `test_corrupt_model_file_returns_503` |
| Dependencies | `pip-audit -r requirements.txt`: no known vulnerabilities. `npm audit` (all deps, after upgrading react-router to 7.18.4, vite 6.4.4, vitest 4.1.11): 0 vulnerabilities | `artifacts/qa/pip_audit.txt`, `npm_audit_all.txt`, `npm_audit_prod.txt` (run 2026-10-15) |
| Secrets in code | Manual grep for hard-coded keys/passwords: none; `.env.example` has placeholders only | code review |

## Privacy

* **Local by default.** Data stays in `data/app.db` on the machine running the backend. No analytics, no
  third-party scripts, no external fonts or CDNs at runtime.
* **Minimal email content.** Alert emails say only that an assessment was flagged and ask the user to sign in.
  No inputs, probabilities or disease names are included. Users can turn alerts off.
* **Logs** contain event names and numeric ids only (no passwords, tokens, inputs, probabilities or risk levels).
* **Right to erasure.** Users can delete single assessments or their whole account (cascade delete, tested).
* **Token storage.** The JWT is kept in memory and `sessionStorage` (cleared when the tab closes). This is
  readable by JavaScript on the same origin, so an XSS bug would expose it; the CSP and React escaping reduce
  that risk. An HttpOnly cookie with CSRF protection would be stronger (see recommendations).
* **Test data.** All automated tests use synthetic accounts (`@example.com`) and synthetic inputs.
* **The T1D spreadsheet** contained names, phone numbers and addresses of children. Only a de-identified
  derivative is in the project (`data/restricted/`); the original was not copied. The team should keep the
  original access-controlled, confirm consent/ethics approval, and avoid sharing either file.

## Development vs production configuration

| Setting | Development default | Production requirement |
|---|---|---|
| `APP_ENV` | development | production |
| `SECRET_KEY` | random per start if unset | >= 32 random chars, not the placeholder (enforced) |
| API docs | on (`/api/docs`) | off (automatic) |
| `CORS_ORIGINS` | localhost:5173 | exact public origin |
| Transport | plain HTTP on 127.0.0.1 | HTTPS via a reverse proxy (not included) |
| `EMAIL_MODE` | disabled | smtp with an app password |

## Unresolved risks and recommended improvements

1. **No HTTPS** in the local setup. Do not expose port 8000 to a network without a TLS reverse proxy.
2. **Rate limiting is in-memory** and per process; it resets on restart and does not work across multiple
   workers. Use Redis or a gateway limiter for multi-process deployment.
3. **No account verification or password reset by email**, no MFA, no account lockout beyond rate limiting.
4. **Bearer token in sessionStorage** (see above).
5. **Data at rest is not encrypted.** SQLite file is plain; use disk encryption or an encrypted database for real
   health data.
6. **No audit log** of who viewed which record.
7. **SQLite `create_all` without migrations**; schema changes need Alembic.
8. **Real SMTP delivery not tested** (no credentials). The status `sent` means the SMTP server accepted the
   message, not that it reached the inbox.
9. Formal penetration testing and a clinical-safety/privacy impact assessment were not performed.
