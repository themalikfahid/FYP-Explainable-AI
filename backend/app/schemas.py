"""Pydantic request/response models. Field ranges mirror ml/data.py specs
(a test asserts they stay in sync)."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, EmailStr, Field, field_validator

YesNo = Literal[0, 1]
# SQLite returns naive datetimes; all stored times are UTC, so mark them as such in API output
UTCDateTime = Annotated[datetime, AfterValidator(lambda d: d if d.tzinfo else d.replace(tzinfo=timezone.utc))]


# ------------------------------------------------------------------ auth
class RegisterIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=8, max_length=72)

    @field_validator("password")
    @classmethod
    def strong_enough(cls, v: str) -> str:
        if len(v.encode("utf-8")) > 72:
            raise ValueError("Password is too long (max 72 bytes)")
        if not re.search(r"[A-Za-z]", v) or not re.search(r"\d", v):
            raise ValueError("Password must contain at least one letter and one number")
        return v

    @field_validator("full_name")
    @classmethod
    def strip_name(cls, v: str) -> str:
        v = " ".join(v.split())
        if not v:
            raise ValueError("Name cannot be blank")
        return v


class LoginIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: EmailStr
    password: str = Field(min_length=1, max_length=72)


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: datetime


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: str
    full_name: str
    email_alerts_enabled: bool
    created_at: UTCDateTime


class UserUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    full_name: str | None = Field(default=None, min_length=1, max_length=100)
    email_alerts_enabled: bool | None = None


class PasswordChange(BaseModel):
    model_config = ConfigDict(extra="forbid")
    current_password: str = Field(min_length=1, max_length=72)
    new_password: str = Field(min_length=8, max_length=72)

    _check = field_validator("new_password")(RegisterIn.strong_enough.__func__)


class AccountDelete(BaseModel):
    model_config = ConfigDict(extra="forbid")
    password: str = Field(min_length=1, max_length=72)


# --------------------------------------------------------------- features
class DiabetesFeatures(BaseModel):
    model_config = ConfigDict(extra="forbid")
    age: float = Field(ge=16, le=90, description="years")
    gender_male: YesNo
    polyuria: YesNo
    polydipsia: YesNo
    sudden_weight_loss: YesNo
    weakness: YesNo
    polyphagia: YesNo
    genital_thrush: YesNo
    visual_blurring: YesNo
    itching: YesNo
    irritability: YesNo
    delayed_healing: YesNo
    partial_paresis: YesNo
    muscle_stiffness: YesNo
    alopecia: YesNo
    obesity: YesNo


class HeartFeatures(BaseModel):
    model_config = ConfigDict(extra="forbid")
    age: float = Field(ge=18, le=100, description="years")
    sex: YesNo
    cp: Literal[1, 2, 3, 4]
    trestbps: float = Field(ge=70, le=250, description="mm Hg")
    chol: float | None = Field(default=None, ge=80, le=700, description="mg/dL (optional)")
    fbs: YesNo
    restecg: Literal[0, 1, 2]
    thalach: float = Field(ge=50, le=230, description="bpm")
    exang: YesNo
    oldpeak: float = Field(ge=-3, le=7)
    slope: Literal[1, 2, 3] | None = None
    ca: Literal[0, 1, 2, 3] | None = None
    thal: Literal[3, 6, 7] | None = None


class LifestyleIn(BaseModel):
    """Optional lifestyle inputs used for BMI, lifestyle score and recommendations
    (NOT used by the ML models)."""
    model_config = ConfigDict(extra="forbid")
    height_cm: float = Field(ge=100, le=250)
    weight_kg: float = Field(ge=25, le=350)
    sleep_hours: float = Field(ge=0, le=24)
    activity_minutes_week: float = Field(ge=0, le=3000, description="moderate-intensity equivalent minutes")
    fruit_veg_servings_day: float = Field(ge=0, le=20)
    smoking: Literal["never", "former", "current"]
    alcohol_units_week: float = Field(ge=0, le=200)
    asian_bmi_cutoffs: bool = False


class DiabetesRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    features: DiabetesFeatures
    lifestyle: LifestyleIn | None = None
    save: bool = True


class HeartRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    features: HeartFeatures
    lifestyle: LifestyleIn | None = None
    save: bool = True


class BMIIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    height_cm: float = Field(ge=100, le=250)
    weight_kg: float = Field(ge=25, le=350)
    asian_bmi_cutoffs: bool = False


# --------------------------------------------------------------- outputs
class PredictionSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    disease: str
    created_at: UTCDateTime
    predicted_class: int
    risk_score: float
    risk_level: str


class PredictionOut(BaseModel):
    id: int | None
    disease: str
    created_at: UTCDateTime
    inputs: dict
    lifestyle: dict | None
    predicted_class: int
    risk_score: float
    risk_level: str
    result: dict
    model_version: str
    alert_status: str | None = None
