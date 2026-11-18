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


class CadFeatures(BaseModel):
    """Coronary artery disease screening inputs (Z-Alizadeh Sani model). Lab/echo values are optional."""
    model_config = ConfigDict(extra="forbid")
    age: float = Field(ge=18, le=100, description="years")
    sex: YesNo
    bmi: float = Field(ge=12, le=60, description="kg/m2")
    diabetes_hx: YesNo
    hypertension: YesNo
    current_smoker: YesNo
    family_history: YesNo
    dyslipidemia: YesNo
    bp_systolic: float = Field(ge=70, le=250, description="mm Hg")
    pulse: float = Field(ge=30, le=200, description="bpm")
    typical_chest_pain: YesNo
    atypical_chest_pain: YesNo
    nonanginal_pain: YesNo
    dyspnea: YesNo
    function_class: Literal[0, 1, 2, 3]
    q_wave: YesNo
    st_elevation: YesNo
    st_depression: YesNo
    t_inversion: YesNo
    lvh: YesNo
    fbs_mgdl: float | None = Field(default=None, ge=40, le=600, description="mg/dL (optional)")
    ldl: float | None = Field(default=None, ge=10, le=400, description="mg/dL (optional)")
    hdl: float | None = Field(default=None, ge=10, le=150, description="mg/dL (optional)")
    triglycerides: float | None = Field(default=None, ge=20, le=2000, description="mg/dL (optional)")
    esr: float | None = Field(default=None, ge=0, le=150, description="mm/h (optional)")
    hemoglobin: float | None = Field(default=None, ge=5, le=20, description="g/dL (optional)")
    ef_tte: float | None = Field(default=None, ge=10, le=80, description="% (optional)")


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


class CadRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    features: CadFeatures
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


# ------------------------------------------------------------ extra modules
class T1DIn(BaseModel):
    """Inputs of the rule-based Type-1 pattern indicator (nothing here is stored)."""
    model_config = ConfigDict(extra="forbid")
    age: float = Field(ge=1, le=100)
    polyuria: YesNo = 0
    polydipsia: YesNo = 0
    weight_loss: YesNo = 0
    fatigue: YesNo = 0
    blurred_vision: YesNo = 0
    bedwetting: YesNo = 0
    recurrent_infections: YesNo = 0
    abdominal_pain_vomiting: YesNo = 0
    fruity_breath_or_fast_breathing: YesNo = 0
    symptom_weeks: float | None = Field(default=None, ge=0, le=520)
    family_history_t1d: YesNo = 0
    other_autoimmune: YesNo = 0
    bmi_category: Literal["underweight", "normal", "overweight", "obese", "unknown"] = "unknown"
    fasting_glucose: float | None = Field(default=None, ge=20, le=1000, description="mg/dL")
    random_glucose: float | None = Field(default=None, ge=20, le=1000, description="mg/dL")
    hba1c: float | None = Field(default=None, ge=3, le=20, description="percent")


class EcgIn(BaseModel):
    """One heartbeat: 187 samples scaled to 0-1 (MIT-BIH heartbeat format)."""
    model_config = ConfigDict(extra="forbid")
    beat: list[float] = Field(min_length=187, max_length=187)

    @field_validator("beat")
    @classmethod
    def finite_in_range(cls, v: list[float]) -> list[float]:
        import math
        if any(not math.isfinite(x) or x < -0.5 or x > 1.5 for x in v):
            raise ValueError("beat values must be finite numbers, scaled to roughly 0-1")
        return v


class WhatIfIn(BaseModel):
    """Re-run a model with some inputs changed; nothing is saved."""
    model_config = ConfigDict(extra="forbid")
    features: dict[str, float | int | None]
    changes: dict[str, float | int | None] = Field(default_factory=dict)
