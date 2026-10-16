import time

import jwt
import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from backend.app import schemas
from backend.app.security import RateLimiter, create_access_token, decode_token, hash_password, verify_password
from ml.data import DIABETES_SPEC, HEART_SPEC


def test_password_hash_roundtrip_and_salted():
    h1, h2 = hash_password("Secret123"), hash_password("Secret123")
    assert h1 != h2 and h1.startswith("$2b$12$")
    assert verify_password("Secret123", h1)
    assert not verify_password("secret123", h1)
    assert not verify_password("x", "not-a-hash")


def test_token_roundtrip(settings_env):
    tok, exp = create_access_token(7)
    p = decode_token(tok)
    assert p["sub"] == "7" and p["type"] == "access" and len(p["jti"]) == 32


def test_token_tampered_and_expired(settings_env):
    from backend.app.config import get_settings
    tok, _ = create_access_token(1)
    with pytest.raises(jwt.PyJWTError):
        decode_token(tok[:-2] + ("AA" if tok[-2:] != "AA" else "BB"))
    expired = jwt.encode({"sub": "1", "iat": 1, "exp": int(time.time()) - 10, "jti": "x" * 32, "type": "access"},
                         get_settings().SECRET_KEY, algorithm="HS256")
    with pytest.raises(jwt.ExpiredSignatureError):
        decode_token(expired)
    wrong_key = jwt.encode({"sub": "1", "iat": 1, "exp": int(time.time()) + 100, "jti": "y" * 32},
                           "another-key-that-is-long-enough-123456789", algorithm="HS256")
    with pytest.raises(jwt.InvalidSignatureError):
        decode_token(wrong_key)
    none_alg = jwt.encode({"sub": "1", "iat": 1, "exp": int(time.time()) + 100, "jti": "z" * 32}, None, algorithm="none")
    with pytest.raises(jwt.PyJWTError):
        decode_token(none_alg)


def test_rate_limiter():
    rl = RateLimiter()
    for _ in range(3):
        rl.check("k", 3)
    with pytest.raises(HTTPException) as e:
        rl.check("k", 3)
    assert e.value.status_code == 429 and "Retry-After" in e.value.headers
    rl.check("other", 3)  # independent keys


def test_production_requires_secret(monkeypatch):
    from backend.app.config import Settings
    with pytest.raises(ValidationError):
        Settings(APP_ENV="production", SECRET_KEY="short")
    assert len(Settings(APP_ENV="development", SECRET_KEY="").SECRET_KEY) >= 32


@pytest.mark.parametrize("pw,ok", [("abcdefg1", True), ("abcdefgh", False), ("12345678", False), ("ab1", False),
                                    ("a1" + "x" * 71, False)])
def test_password_policy(pw, ok):
    data = {"email": "a@example.com", "full_name": "A", "password": pw}
    if ok:
        schemas.RegisterIn(**data)
    else:
        with pytest.raises(ValidationError):
            schemas.RegisterIn(**data)


def test_register_rejects_extra_fields_and_blank_name():
    with pytest.raises(ValidationError):
        schemas.RegisterIn(email="a@example.com", full_name="A", password="abcdefg1", is_admin=True)
    with pytest.raises(ValidationError):
        schemas.RegisterIn(email="a@example.com", full_name="   ", password="abcdefg1")


def _field_bounds(model, name):
    f = model.model_fields[name]
    lo = hi = None
    for m in f.metadata:
        lo = getattr(m, "ge", lo)
        hi = getattr(m, "le", hi)
    return lo, hi


@pytest.mark.parametrize("model,spec", [(schemas.DiabetesFeatures, DIABETES_SPEC), (schemas.HeartFeatures, HEART_SPEC)])
def test_api_schema_matches_ml_spec(model, spec):
    """Backend validation and the served form spec must agree (names, ranges, options, required)."""
    assert list(model.model_fields) == list(spec)
    for name, s in spec.items():
        field = model.model_fields[name]
        assert field.is_required() == s["required"], name
        if s["type"] == "number":
            assert _field_bounds(model, name) == (s["min"], s["max"]), name
        else:
            allowed = {o["value"] for o in s["options"]}
            base = {"age": 50} if model is schemas.DiabetesFeatures else {}
            for v in allowed:  # each option accepted
                model.model_validate({**_valid(model), name: v})
            with pytest.raises(ValidationError):
                model.model_validate({**_valid(model), name: 99})
            _ = base


def _valid(model):
    from tests.conftest import HEART_LOW, LOW_RISK_DIABETES
    return dict(LOW_RISK_DIABETES if model is schemas.DiabetesFeatures else HEART_LOW)


def test_production_rejects_placeholder_secret():
    from backend.app.config import Settings
    with pytest.raises(ValidationError):
        Settings(APP_ENV="production", SECRET_KEY="change-me-to-a-random-string-of-at-least-32-characters")
