import io
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from pypdf import PdfReader

from backend.app import db as dbmod
from backend.app.config import Settings
from backend.app.models import EmailAlert, Prediction, User
from backend.app.services import email as email_service


@pytest.fixture
def session(tmp_path):
    dbmod.configure(f"sqlite:///{(tmp_path / 'u.db').as_posix()}")
    dbmod.init_db()
    s = dbmod.session_factory()
    yield s
    s.close()


def _user_pred(s, risk="high", alerts=True):
    u = User(email=f"u{risk}{alerts}@example.com", full_name="Unit User", password_hash="x", email_alerts_enabled=alerts)
    s.add(u)
    s.commit()
    p = Prediction(user_id=u.id, disease="diabetes", inputs={}, predicted_class=1, risk_score=0.9, risk_level=risk,
                   result={}, model_version="t")
    s.add(p)
    s.commit()
    return u, p


def _settings(tmp_path, **kw):
    return Settings(APP_ENV="test", SECRET_KEY="k" * 40, EMAIL_OUTBOX_DIR=str(tmp_path / "out"), **kw)


def test_file_mode_writes_once_and_hides_details(session, tmp_path):
    u, p = _user_pred(session)
    st = _settings(tmp_path, EMAIL_MODE="file")
    a = email_service.send_alert(session, st, u, p)
    assert a.status == "written_to_file"
    files = list((tmp_path / "out").glob("*.eml"))
    assert len(files) == 1
    body = files[0].read_text()
    assert "HIGH risk" in body and "does not include the details" in body
    assert "0.9" not in body and "polyuria" not in body.lower()
    # duplicate prevention
    assert email_service.send_alert(session, st, u, p) is None
    assert session.query(EmailAlert).count() == 1 and len(list((tmp_path / "out").glob("*.eml"))) == 1


def test_no_alert_when_not_high_or_opted_out(session, tmp_path):
    st = _settings(tmp_path, EMAIL_MODE="file")
    u, p = _user_pred(session, risk="moderate")
    assert email_service.send_alert(session, st, u, p) is None
    u2, p2 = _user_pred(session, risk="high", alerts=False)
    assert email_service.send_alert(session, st, u2, p2) is None
    assert session.query(EmailAlert).count() == 0


def test_disabled_mode_records_status(session, tmp_path):
    u, p = _user_pred(session)
    a = email_service.send_alert(session, _settings(tmp_path, EMAIL_MODE="disabled"), u, p)
    assert a.status == "disabled"


def test_smtp_unconfigured_fails_gracefully(session, tmp_path):
    u, p = _user_pred(session)
    a = email_service.send_alert(session, _settings(tmp_path, EMAIL_MODE="smtp"), u, p)
    assert a.status == "failed" and "not configured" in a.detail


def test_smtp_unreachable_fails_gracefully(session, tmp_path):
    u, p = _user_pred(session)
    st = _settings(tmp_path, EMAIL_MODE="smtp", SMTP_HOST="127.0.0.1", SMTP_PORT=1, SMTP_FROM="a@example.com",
                   SMTP_TIMEOUT_SECONDS=2)
    a = email_service.send_alert(session, st, u, p)
    assert a.status == "failed"


def test_smtp_success_path_with_fake_server(session, tmp_path, monkeypatch):
    sent = {}

    class FakeSMTP:
        def __init__(self, host, port, timeout):
            sent["host"] = host
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def starttls(self, context): sent["tls"] = True
        def login(self, u, pw): sent["login"] = u
        def send_message(self, msg): sent["to"] = msg["To"]; return {}

    monkeypatch.setattr(email_service.smtplib, "SMTP", FakeSMTP)
    u, p = _user_pred(session)
    st = _settings(tmp_path, EMAIL_MODE="smtp", SMTP_HOST="smtp.example.com", SMTP_FROM="no-reply@example.com",
                   SMTP_USERNAME="user", SMTP_PASSWORD="pw")
    a = email_service.send_alert(session, st, u, p)
    assert a.status == "sent" and sent == {"host": "smtp.example.com", "tls": True, "login": "user", "to": u.email}


def test_smtp_refused_recipient_is_failure(session, tmp_path, monkeypatch):
    class Refusing:
        def __init__(self, *a, **k): pass
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def starttls(self, context): pass
        def send_message(self, msg): return {msg["To"]: (550, b"no such user")}

    monkeypatch.setattr(email_service.smtplib, "SMTP", Refusing)
    u, p = _user_pred(session)
    st = _settings(tmp_path, EMAIL_MODE="smtp", SMTP_HOST="h", SMTP_FROM="f@example.com")
    assert email_service.send_alert(session, st, u, p).status == "failed"


def test_pdf_report_contents(client, auth):
    """Build a report from a real prediction and check the text matches the stored result."""
    from tests.conftest import HEART_HIGH, LIFESTYLE
    r = client.post("/api/predict/heart", json={"features": HEART_HIGH, "lifestyle": LIFESTYLE}, headers=auth)
    pred = r.json()
    pdf = client.get(f"/api/predictions/{pred['id']}/report.pdf", headers=auth)
    assert pdf.status_code == 200 and pdf.content[:5] == b"%PDF-"
    text = " ".join(page.extract_text() for page in PdfReader(io.BytesIO(pdf.content)).pages)
    assert pred["risk_level"].upper() in text
    assert f"{pred['risk_score']:.1%}" in text
    assert "Alice Test" in text and "not a substitute" in text
    assert "Resting blood pressure" in text and "Lifestyle score" in text


def test_pdf_handles_missing_optional_and_no_lifestyle():
    from backend.app.services.pdf import build_report
    from tests.conftest import HEART_LOW
    inputs = {**HEART_LOW, "chol": None, "ca": None, "thal": None, "slope": None}
    result = {
        "risk_score_definition": "x", "predicted_label": "No significant disease (<50% narrowing)",
        "risk_thresholds": {"low_below": .3, "high_at_or_above": .7}, "probability_note": "n",
        "probabilities": {str(c): .2 for c in range(5)},
        "components": {"random_forest": {str(c): .2 for c in range(5)}, "ann": {str(c): .2 for c in range(5)}},
        "warnings": ["w"], "model": {"version": "v", "production_model": "p", "test_metrics": {"accuracy": .5, "n_test": 10}},
        "recommendations": {"items": [], "bmi": None, "lifestyle_score": None},
    }
    pred = SimpleNamespace(id=1, disease="heart", inputs=inputs, result=result, risk_level="low", risk_score=0.2,
                           created_at=datetime.now(timezone.utc))
    out = build_report(pred, SimpleNamespace(full_name="Synthetic Person"))
    assert "Not provided" in " ".join(p.extract_text() for p in PdfReader(io.BytesIO(out)).pages)
