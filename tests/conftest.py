"""Shared fixtures. Tests use an isolated temporary SQLite database, a temporary
email outbox (EMAIL_MODE=file) and synthetic accounts. No real email is sent."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

os.environ.update({
    "APP_ENV": "test",
    "SECRET_KEY": "test-secret-key-that-is-long-enough-1234567890",
    "EMAIL_MODE": "file",
    "LOGIN_RATE_LIMIT_PER_MINUTE": "1000",
    "PREDICT_RATE_LIMIT_PER_MINUTE": "1000",
    "FRONTEND_DIST": str(ROOT / "nonexistent-dist"),
})

MODELS_DIR = ROOT / "artifacts" / "models"

HIGH_RISK_DIABETES = {"age": 45, "gender_male": 0, "polyuria": 1, "polydipsia": 1, "sudden_weight_loss": 1,
                      "weakness": 1, "polyphagia": 1, "genital_thrush": 0, "visual_blurring": 1, "itching": 0,
                      "irritability": 1, "delayed_healing": 0, "partial_paresis": 1, "muscle_stiffness": 0,
                      "alopecia": 0, "obesity": 0}
LOW_RISK_DIABETES = {**{k: 0 for k in HIGH_RISK_DIABETES}, "age": 35, "gender_male": 1}
HEART_HIGH = {"age": 63, "sex": 1, "cp": 4, "trestbps": 150, "chol": 280, "fbs": 1, "restecg": 2, "thalach": 105,
              "exang": 1, "oldpeak": 3.0, "slope": 2, "ca": 3, "thal": 7}
HEART_LOW = {"age": 38, "sex": 0, "cp": 3, "trestbps": 115, "chol": 190, "fbs": 0, "restecg": 0, "thalach": 175,
             "exang": 0, "oldpeak": 0.0, "slope": 1, "ca": 0, "thal": 3}
LIFESTYLE = {"height_cm": 170, "weight_kg": 85, "sleep_hours": 6, "activity_minutes_week": 60,
             "fruit_veg_servings_day": 2, "smoking": "current", "alcohol_units_week": 0, "asian_bmi_cutoffs": False}


def require_models():
    for t in ("diabetes", "heart"):
        if not (MODELS_DIR / t / "hybrid.joblib").exists():
            pytest.fail(f"Model artifacts for '{t}' missing. Run `python -m ml.train` before the test suite.")


@pytest.fixture
def settings_env(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{(tmp_path / 'test.db').as_posix()}")
    monkeypatch.setenv("EMAIL_OUTBOX_DIR", str(tmp_path / "outbox"))
    monkeypatch.setenv("MODELS_DIR", str(MODELS_DIR))
    from backend.app.config import get_settings
    get_settings.cache_clear()
    from backend.app.security import limiter
    limiter.reset()
    yield tmp_path
    get_settings.cache_clear()


@pytest.fixture
def client(settings_env):
    require_models()
    from fastapi.testclient import TestClient
    from backend.app.main import create_app
    with TestClient(create_app()) as c:
        yield c


def register_and_login(client, email="alice@example.com", password="Passw0rd!", name="Alice Test") -> dict:
    r = client.post("/api/auth/register", json={"email": email, "password": password, "full_name": name})
    assert r.status_code == 201, r.text
    r = client.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture
def auth(client):
    return register_and_login(client)
