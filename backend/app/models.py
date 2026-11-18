"""ORM tables. See docs/DATABASE_SCHEMA.md."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, CheckConstraint, DateTime, Float, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(100), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(100), nullable=False)
    email_alerts_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    predictions: Mapped[list[Prediction]] = relationship(back_populates="user", cascade="all, delete-orphan",
                                                         passive_deletes=True)


class Prediction(Base):
    __tablename__ = "predictions"
    __table_args__ = (
        CheckConstraint("disease IN ('diabetes','heart','cad')", name="ck_prediction_disease"),
        CheckConstraint("risk_level IN ('low','moderate','high')", name="ck_prediction_risk"),
        CheckConstraint("risk_score >= 0 AND risk_score <= 1", name="ck_prediction_score"),
        Index("ix_predictions_user_created", "user_id", "created_at"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    disease: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    inputs: Mapped[dict] = mapped_column(JSON, nullable=False)
    lifestyle: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    predicted_class: Mapped[int] = mapped_column(Integer, nullable=False)
    risk_score: Mapped[float] = mapped_column(Float, nullable=False)
    risk_level: Mapped[str] = mapped_column(String(10), nullable=False)
    result: Mapped[dict] = mapped_column(JSON, nullable=False)  # probabilities, explanation, recommendations
    model_version: Mapped[str] = mapped_column(String(64), nullable=False)

    user: Mapped[User] = relationship(back_populates="predictions")
    alert: Mapped[EmailAlert | None] = relationship(back_populates="prediction", cascade="all, delete-orphan",
                                                    passive_deletes=True, uselist=False)


class EmailAlert(Base):
    """One row per high-risk prediction; the UNIQUE prediction_id prevents duplicate alerts."""
    __tablename__ = "email_alerts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    prediction_id: Mapped[int] = mapped_column(ForeignKey("predictions.id", ondelete="CASCADE"), unique=True,
                                               nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # sent | written_to_file | disabled | failed
    detail: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    prediction: Mapped[Prediction] = relationship(back_populates="alert")


class RevokedToken(Base):
    """Denylist of logged-out JWT ids (jti) until their natural expiry."""
    __tablename__ = "revoked_tokens"
    jti: Mapped[str] = mapped_column(String(64), primary_key=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
