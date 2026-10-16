"""End-to-end API tests through FastAPI's TestClient with an isolated database."""
import shutil

import pytest

from tests.conftest import (HEART_HIGH, HEART_LOW, HIGH_RISK_DIABETES, LIFESTYLE, LOW_RISK_DIABETES, MODELS_DIR,
                            register_and_login)


# ------------------------------------------------------------- health/meta
def test_health_and_meta(client):
    h = client.get("/api/health").json()
    assert h["status"] == "ok" and h["models"] == {"diabetes": "loaded", "heart": "loaded"}
    f = client.get("/api/meta/features").json()
    assert f["heart"]["features"][0] == "age" and "disclaimer" in f
    m = client.get("/api/meta/models/heart").json()
    assert set(m["test_metrics"]) == {"random_forest", "ann", "hybrid"} and m["global_shap"]["features_ranked"]
    assert client.get("/api/meta/models/nope").status_code == 404


def test_security_headers(client):
    r = client.get("/api/health")
    assert r.headers["x-content-type-options"] == "nosniff" and r.headers["x-frame-options"] == "DENY"
    assert "default-src 'self'" in r.headers["content-security-policy"]
    assert r.headers["cache-control"] == "no-store"


def test_cors_only_allows_configured_origin(client):
    ok = client.options("/api/health", headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET"})
    bad = client.options("/api/health", headers={"Origin": "http://evil.example", "Access-Control-Request-Method": "GET"})
    assert ok.headers.get("access-control-allow-origin") == "http://localhost:5173"
    assert "access-control-allow-origin" not in bad.headers


# ------------------------------------------------------------------- auth
def test_register_login_me_logout_flow(client):
    h = register_and_login(client, email="Bob@Example.com")
    me = client.get("/api/auth/me", headers=h).json()
    assert me["email"] == "bob@example.com" and "password_hash" not in me
    assert client.post("/api/auth/logout", headers=h).status_code == 204
    r = client.get("/api/auth/me", headers=h)
    assert r.status_code == 401 and "logged out" in r.json()["detail"]


def test_register_validation_and_duplicates(client):
    body = {"email": "c@example.com", "password": "Passw0rd!", "full_name": "C"}
    assert client.post("/api/auth/register", json=body).status_code == 201
    assert client.post("/api/auth/register", json={**body, "email": "C@EXAMPLE.COM"}).status_code == 409
    r = client.post("/api/auth/register", json={**body, "email": "d@example.com", "password": "short"})
    assert r.status_code == 422 and r.json()["errors"][0]["field"] == "password"
    assert "short" not in r.text  # submitted values are not echoed back
    assert client.post("/api/auth/register", json={**body, "email": "not-an-email"}).status_code == 422


def test_login_failures_are_generic(client):
    register_and_login(client, email="e@example.com")
    a = client.post("/api/auth/login", json={"email": "e@example.com", "password": "WrongPass1"})
    b = client.post("/api/auth/login", json={"email": "nobody@example.com", "password": "WrongPass1"})
    assert a.status_code == b.status_code == 401 and a.json() == b.json()


def test_login_rate_limit(client, monkeypatch):
    from backend.app.config import get_settings
    monkeypatch.setattr(get_settings(), "LOGIN_RATE_LIMIT_PER_MINUTE", 3)
    codes = [client.post("/api/auth/login", json={"email": "x@example.com", "password": "Nope12345"}).status_code
             for _ in range(5)]
    assert codes[:3] == [401, 401, 401] and codes[3:] == [429, 429]


@pytest.mark.parametrize("header", [None, "Bearer garbage", "Basic abc", "Bearer "])
def test_protected_endpoints_reject_bad_auth(client, header):
    h = {"Authorization": header} if header else {}
    for method, path in [("get", "/api/auth/me"), ("get", "/api/predictions"), ("post", "/api/predict/heart"),
                         ("get", "/api/predictions/1"), ("get", "/api/predictions/1/report.pdf"),
                         ("delete", "/api/predictions/1")]:
        r = getattr(client, method)(path, headers=h) if method != "post" else client.post(path, headers=h, json={})
        assert r.status_code == 401, (path, r.status_code)


def test_profile_update_and_password_change(client):
    h = register_and_login(client, email="p@example.com")
    r = client.patch("/api/auth/me", json={"full_name": "  New   Name ", "email_alerts_enabled": False}, headers=h)
    assert r.json()["full_name"] == "New Name" and r.json()["email_alerts_enabled"] is False
    assert client.patch("/api/auth/me", json={"email": "hijack@example.com"}, headers=h).status_code == 422
    assert client.post("/api/auth/change-password", json={"current_password": "bad", "new_password": "Newpass123"},
                       headers=h).status_code == 400
    assert client.post("/api/auth/change-password", json={"current_password": "Passw0rd!", "new_password": "Newpass123"},
                       headers=h).status_code == 204
    assert client.get("/api/auth/me", headers=h).status_code == 401  # old token revoked
    assert client.post("/api/auth/login", json={"email": "p@example.com", "password": "Newpass123"}).status_code == 200


# -------------------------------------------------------------- prediction
def _check_prediction(p, task, n_classes):
    r = p["result"]
    assert p["id"] and p["disease"] == task
    assert abs(sum(r["probabilities"].values()) - 1) < 1e-6 and len(r["probabilities"]) == n_classes
    assert 0 <= p["risk_score"] <= 1 and p["risk_level"] in ("low", "moderate", "high")
    assert str(p["predicted_class"]) == max(r["probabilities"], key=r["probabilities"].get)
    e = r["explanation"]
    assert e["additivity_error"] < 1e-6 and len(e["summary"]) == 3
    assert r["recommendations"]["items"] and r["recommendations"]["disclaimer"]


def test_predict_diabetes_high_and_low(client, auth):
    hi = client.post("/api/predict/diabetes", json={"features": HIGH_RISK_DIABETES}, headers=auth)
    assert hi.status_code == 200, hi.text
    _check_prediction(hi.json(), "diabetes", 2)
    assert hi.json()["risk_level"] == "high"
    lo = client.post("/api/predict/diabetes", json={"features": LOW_RISK_DIABETES}, headers=auth).json()
    assert lo["risk_level"] == "low" and lo["risk_score"] < hi.json()["risk_score"]
    assert lo["risk_score"] == pytest.approx(lo["result"]["probabilities"]["1"])


def test_predict_heart_with_lifestyle_and_missing_optionals(client, auth):
    r = client.post("/api/predict/heart", json={"features": HEART_HIGH, "lifestyle": LIFESTYLE}, headers=auth)
    assert r.status_code == 200
    p = r.json()
    _check_prediction(p, "heart", 5)
    assert p["risk_score"] == pytest.approx(1 - p["result"]["probabilities"]["0"])
    assert p["result"]["recommendations"]["bmi"]["bmi"] == 29.4
    any_d = p["result"]["explanation"]["any_disease"]
    assert any_d["base_value"] + sum(any_d["shap"].values()) == pytest.approx(p["risk_score"], abs=1e-6)
    lo = client.post("/api/predict/heart", json={"features": HEART_LOW}, headers=auth).json()
    assert lo["risk_score"] < p["risk_score"]
    partial = {k: v for k, v in HEART_LOW.items() if k not in ("chol", "ca", "thal", "slope")}
    r2 = client.post("/api/predict/heart", json={"features": partial}, headers=auth).json()
    assert any("Not provided" in w for w in r2["result"]["warnings"])


@pytest.mark.parametrize("task,bad", [
    ("diabetes", {**HIGH_RISK_DIABETES, "age": 5}),
    ("diabetes", {**HIGH_RISK_DIABETES, "polyuria": 2}),
    ("diabetes", {k: v for k, v in HIGH_RISK_DIABETES.items() if k != "obesity"}),
    ("diabetes", {**HIGH_RISK_DIABETES, "glucose": 140}),
    ("heart", {**HEART_HIGH, "trestbps": 400}),
    ("heart", {**HEART_HIGH, "cp": 0}),
    ("heart", {**HEART_HIGH, "age": "sixty"}),
    ("heart", {**HEART_HIGH, "thal": 5}),
])
def test_predict_rejects_invalid_inputs(client, auth, task, bad):
    r = client.post(f"/api/predict/{task}", json={"features": bad}, headers=auth)
    assert r.status_code == 422 and r.json()["errors"]


def test_predict_rejects_bad_lifestyle(client, auth):
    r = client.post("/api/predict/heart", json={"features": HEART_LOW, "lifestyle": {**LIFESTYLE, "smoking": "sometimes"}},
                    headers=auth)
    assert r.status_code == 422


def test_save_false_does_not_persist(client, auth):
    r = client.post("/api/predict/heart", json={"features": HEART_LOW, "save": False}, headers=auth).json()
    assert r["id"] is None
    assert client.get("/api/predictions", headers=auth).json()["total"] == 0


# ----------------------------------------------------- history / ownership
def test_history_pagination_filter_and_delete(client, auth):
    for _ in range(3):
        client.post("/api/predict/heart", json={"features": HEART_LOW}, headers=auth)
    client.post("/api/predict/diabetes", json={"features": LOW_RISK_DIABETES}, headers=auth)
    all_ = client.get("/api/predictions?limit=2", headers=auth).json()
    assert all_["total"] == 4 and len(all_["items"]) == 2
    assert all_["items"][0]["disease"] == "diabetes"  # newest first
    heart = client.get("/api/predictions?disease=heart", headers=auth).json()
    assert heart["total"] == 3
    pid = heart["items"][0]["id"]
    assert client.delete(f"/api/predictions/{pid}", headers=auth).status_code == 204
    assert client.get(f"/api/predictions/{pid}", headers=auth).status_code == 404
    assert client.get("/api/predictions?limit=1000", headers=auth).status_code == 422


def test_users_cannot_access_each_others_records(client):
    alice = register_and_login(client, email="alice2@example.com")
    mallory = register_and_login(client, email="mallory@example.com")
    pid = client.post("/api/predict/heart", json={"features": HEART_HIGH}, headers=alice).json()["id"]
    for method, path in [("get", f"/api/predictions/{pid}"), ("get", f"/api/predictions/{pid}/report.pdf"),
                         ("delete", f"/api/predictions/{pid}")]:
        r = getattr(client, method)(path, headers=mallory)
        assert r.status_code == 404, path
    assert client.get("/api/predictions", headers=mallory).json()["total"] == 0
    assert client.get(f"/api/predictions/{pid}", headers=alice).status_code == 200


def test_report_download(client, auth):
    pid = client.post("/api/predict/diabetes", json={"features": HIGH_RISK_DIABETES}, headers=auth).json()["id"]
    r = client.get(f"/api/predictions/{pid}/report.pdf", headers=auth)
    assert r.status_code == 200 and r.headers["content-type"] == "application/pdf"
    assert r.content.startswith(b"%PDF-") and f"health-report-{pid}.pdf" in r.headers["content-disposition"]


def test_account_deletion_cascades(client):
    h = register_and_login(client, email="gone@example.com")
    pid = client.post("/api/predict/diabetes", json={"features": HIGH_RISK_DIABETES}, headers=h).json()["id"]
    assert client.request("DELETE", "/api/auth/me", json={"password": "wrong"}, headers=h).status_code == 400
    assert client.request("DELETE", "/api/auth/me", json={"password": "Passw0rd!"}, headers=h).status_code == 204
    from backend.app import db as dbmod
    from backend.app.models import EmailAlert, Prediction
    s = dbmod.session_factory()
    assert s.get(Prediction, pid) is None and s.query(EmailAlert).count() == 0
    s.close()
    assert client.post("/api/auth/login", json={"email": "gone@example.com", "password": "Passw0rd!"}).status_code == 401


# ------------------------------------------------------------------- email
def test_high_risk_triggers_single_alert_file(client, auth, settings_env):
    p = client.post("/api/predict/diabetes", json={"features": HIGH_RISK_DIABETES}, headers=auth).json()
    outbox = settings_env / "outbox"
    assert (outbox / f"alert_prediction_{p['id']}.eml").exists()
    again = client.get(f"/api/predictions/{p['id']}", headers=auth).json()
    assert again["alert_status"] == "written_to_file"
    client.post("/api/predict/diabetes", json={"features": LOW_RISK_DIABETES}, headers=auth)
    assert len(list(outbox.glob("*.eml"))) == 1  # low risk -> no alert


def test_alerts_respect_opt_out(client, auth, settings_env):
    client.patch("/api/auth/me", json={"email_alerts_enabled": False}, headers=auth)
    p = client.post("/api/predict/diabetes", json={"features": HIGH_RISK_DIABETES}, headers=auth).json()
    assert p["risk_level"] == "high"
    assert not (settings_env / "outbox").exists() or not list((settings_env / "outbox").glob("*.eml"))


def test_smtp_failure_does_not_break_prediction(client, auth, monkeypatch):
    from backend.app.config import get_settings
    monkeypatch.setattr(get_settings(), "EMAIL_MODE", "smtp")  # but SMTP_HOST is empty
    r = client.post("/api/predict/diabetes", json={"features": HIGH_RISK_DIABETES}, headers=auth)
    assert r.status_code == 200
    assert client.get(f"/api/predictions/{r.json()['id']}", headers=auth).json()["alert_status"] == "failed"


# --------------------------------------------------------------- tools
def test_tools(client):
    assert client.post("/api/tools/bmi", json={"height_cm": 170, "weight_kg": 70}).json()["bmi"] == 24.2
    assert client.post("/api/tools/bmi", json={"height_cm": 17, "weight_kg": 70}).status_code == 422
    r = client.post("/api/tools/lifestyle-score", json=LIFESTYLE).json()
    assert r["lifestyle_score"]["score"] == 40 and r["bmi"]["category"] == "Overweight"
    assert client.post("/api/tools/lifestyle-score", json={"height_cm": 170}).status_code == 422


# ------------------------------------------------------ failure handling
def test_missing_model_files_return_503(settings_env, tmp_path, monkeypatch):
    empty = tmp_path / "empty_models"
    empty.mkdir()
    monkeypatch.setenv("MODELS_DIR", str(empty))
    from backend.app.config import get_settings
    get_settings.cache_clear()
    from fastapi.testclient import TestClient
    from backend.app.main import create_app
    with TestClient(create_app()) as c:
        assert c.get("/api/health").json()["status"] == "degraded"
        h = register_and_login(c, email="m@example.com")
        r = c.post("/api/predict/heart", json={"features": HEART_LOW}, headers=h)
        assert r.status_code == 503 and "python -m ml.train" in r.json()["detail"]


def test_corrupt_model_file_returns_503(settings_env, tmp_path, monkeypatch):
    broken = tmp_path / "broken"
    shutil.copytree(MODELS_DIR, broken)
    (broken / "heart" / "hybrid.joblib").write_bytes(b"not a pickle")
    monkeypatch.setenv("MODELS_DIR", str(broken))
    from backend.app.config import get_settings
    get_settings.cache_clear()
    from fastapi.testclient import TestClient
    from backend.app.main import create_app
    with TestClient(create_app()) as c:
        h = register_and_login(c, email="n@example.com")
        assert c.post("/api/predict/heart", json={"features": HEART_LOW}, headers=h).status_code == 503
        assert c.post("/api/predict/diabetes", json={"features": LOW_RISK_DIABETES}, headers=h).status_code == 200


def test_database_failure_reported_in_health(client, monkeypatch):
    from backend.app import db as dbmod
    from sqlalchemy import create_engine
    monkeypatch.setattr(dbmod, "_engine", create_engine("sqlite:////nonexistent-dir/x/y.db"))
    assert client.get("/api/health").json()["database"] == "error"


def test_sklearn_version_mismatch_refuses_to_load(settings_env, tmp_path, monkeypatch):
    import json as _json
    other = tmp_path / "other_version"
    shutil.copytree(MODELS_DIR, other)
    meta_p = other / "heart" / "metadata.json"
    meta = _json.loads(meta_p.read_text())
    meta["versions"]["sklearn"] = "0.0.1"
    meta_p.write_text(_json.dumps(meta))
    monkeypatch.setenv("MODELS_DIR", str(other))
    from backend.app.config import get_settings
    get_settings.cache_clear()
    from fastapi.testclient import TestClient
    from backend.app.main import create_app
    with TestClient(create_app()) as c:
        status = c.get("/api/health").json()["models"]
        assert status["diabetes"] == "loaded" and "scikit-learn 0.0.1" in status["heart"]


def test_timestamps_are_utc_aware(client, auth):
    """SQLite drops tzinfo; the API must still emit explicit UTC so browsers show local time correctly."""
    p = client.post("/api/predict/heart", json={"features": HEART_LOW}, headers=auth).json()
    for ts in (p["created_at"], client.get("/api/predictions", headers=auth).json()["items"][0]["created_at"],
               client.get(f"/api/predictions/{p['id']}", headers=auth).json()["created_at"],
               client.get("/api/auth/me", headers=auth).json()["created_at"]):
        assert ts.endswith("Z") or ts.endswith("+00:00"), ts
