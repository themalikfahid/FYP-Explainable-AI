"""High-risk email alerts.

Modes (EMAIL_MODE):
  disabled - no email; alert row recorded with status 'disabled'
  file     - message written as .eml to EMAIL_OUTBOX_DIR (QA / local capture); status 'written_to_file'
  smtp     - sent via SMTP; status 'sent' only when the server accepted every recipient

Privacy: the email does NOT contain inputs, probabilities or the disease
result; it only asks the user to sign in and view the report.
Duplicates: email_alerts.prediction_id is UNIQUE, so one prediction can
trigger at most one alert.
"""
from __future__ import annotations

import logging
import smtplib
import ssl
from email.message import EmailMessage
from pathlib import Path

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.config import Settings
from backend.app.models import EmailAlert, Prediction, User

log = logging.getLogger("app.email")


def should_alert(pred: Prediction, user: User) -> bool:
    return pred.risk_level == "high" and user.email_alerts_enabled


def build_message(settings: Settings, user: User, pred: Prediction) -> EmailMessage:
    msg = EmailMessage()
    msg["Subject"] = "Your recent health screening needs attention"
    msg["From"] = settings.SMTP_FROM or "no-reply@localhost"
    msg["To"] = user.email
    msg.set_content(
        f"Hello {user.full_name},\n\n"
        "A screening assessment you completed was flagged as HIGH risk by the model.\n"
        "For your privacy this email does not include the details.\n\n"
        f"Please sign in to view the result, its explanation and recommendations:\n"
        f"{settings.APP_PUBLIC_URL}/history/{pred.id}\n\n"
        "This is an educational screening prototype, not a diagnosis. Please discuss the result with a "
        "qualified health professional. If you feel unwell, seek medical care.\n\n"
        "You can turn these alerts off in Account settings.\n"
    )
    return msg


def send_alert(db: Session, settings: Settings, user: User, pred: Prediction) -> EmailAlert | None:
    """Create the alert row (idempotent) and attempt delivery. Never raises."""
    if not should_alert(pred, user):
        return None
    if db.query(EmailAlert).filter_by(prediction_id=pred.id).first():
        return None  # already handled
    alert = EmailAlert(prediction_id=pred.id, status="pending", detail="")
    db.add(alert)
    try:
        db.commit()
    except IntegrityError:  # concurrent duplicate
        db.rollback()
        return None

    mode = settings.EMAIL_MODE
    try:
        if mode == "disabled":
            alert.status, alert.detail = "disabled", "EMAIL_MODE=disabled; no email sent"
        elif mode == "file":
            outbox = Path(settings.EMAIL_OUTBOX_DIR)
            outbox.mkdir(parents=True, exist_ok=True)
            path = outbox / f"alert_prediction_{pred.id}.eml"
            path.write_bytes(bytes(build_message(settings, user, pred)))
            alert.status, alert.detail = "written_to_file", path.name
        else:
            if not (settings.SMTP_HOST and settings.SMTP_FROM):
                raise RuntimeError("SMTP_HOST / SMTP_FROM not configured")
            msg = build_message(settings, user, pred)
            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=settings.SMTP_TIMEOUT_SECONDS) as s:
                if settings.SMTP_USE_TLS:
                    s.starttls(context=ssl.create_default_context())
                if settings.SMTP_USERNAME:
                    s.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
                refused = s.send_message(msg)
            if refused:
                raise RuntimeError(f"recipient refused by server: {list(refused)}")
            alert.status, alert.detail = "sent", "accepted by SMTP server"
    except Exception as e:  # report, never crash the request
        alert.status, alert.detail = "failed", f"{type(e).__name__}: {str(e)[:300]}"
        log.warning("Email alert for prediction %s failed: %s", pred.id, type(e).__name__)
    db.commit()
    return alert
