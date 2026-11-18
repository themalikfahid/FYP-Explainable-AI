"""Extra modules: Type-1 pattern indicator, what-if simulation and the personal analytics summary."""
from __future__ import annotations

from collections import Counter, defaultdict
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.config import get_settings
from backend.app.db import get_db
from backend.app.models import Prediction, User
from backend.app.schemas import CadFeatures, DiabetesFeatures, EcgIn, HeartFeatures, T1DIn, WhatIfIn
from backend.app.security import get_current_user, limiter
from backend.app.services import ecg as ecg_service
from backend.app.services import t1d
from backend.app.services.inference import ModelUnavailable
from ml.data import TASKS

router = APIRouter(prefix="/api", tags=["insights"])
_SCHEMAS = {"diabetes": DiabetesFeatures, "heart": HeartFeatures, "cad": CadFeatures}


@router.post("/assess/t1d")
def assess_t1d(body: T1DIn, user: User = Depends(get_current_user)):
    limiter.check(f"t1d:{user.id}", get_settings().PREDICT_RATE_LIMIT_PER_MINUTE)
    return t1d.assess(body.model_dump())


@router.post("/assess/ecg")
def assess_ecg(body: EcgIn, request: Request, user: User = Depends(get_current_user)):
    limiter.check(f"ecg:{user.id}", get_settings().PREDICT_RATE_LIMIT_PER_MINUTE)
    try:
        model = ecg_service.get_model(get_settings().MODELS_DIR)
    except ecg_service.EcgUnavailable as e:
        raise HTTPException(status_code=503, detail=str(e)) from None
    return model.classify(body.beat)


@router.get("/meta/ecg")
def ecg_info(user: User = Depends(get_current_user)):
    try:
        m = ecg_service.get_model(get_settings().MODELS_DIR)
    except ecg_service.EcgUnavailable as e:
        raise HTTPException(status_code=503, detail=str(e)) from None
    return {"dataset": m.report["dataset"], "classes": m.short, "report": m.report, "samples": m.samples,
            "threshold": m.threshold}


def _slim(model, features: dict) -> dict:
    r = model.predict(features, explain=False)
    return {"risk_score": r["risk_score"], "risk_level": r["risk_level"], "predicted_class": r["predicted_class"],
            "predicted_label": r["predicted_label"], "confidence": r["confidence"], "probabilities": r["probabilities"]}


@router.post("/whatif/{task}")
def what_if(task: Literal["diabetes", "heart", "cad"], body: WhatIfIn, request: Request,
            user: User = Depends(get_current_user)):
    limiter.check(f"whatif:{user.id}", get_settings().PREDICT_RATE_LIMIT_PER_MINUTE * 2)
    schema = _SCHEMAS[task]
    unknown = [k for k in {*body.features, *body.changes} if k not in TASKS[task]["features"]]
    if unknown:
        raise HTTPException(status_code=422, detail=f"Unknown feature(s): {', '.join(sorted(unknown))}")
    try:
        base = schema(**body.features).model_dump()
        changed = schema(**{**body.features, **body.changes}).model_dump()
    except ValidationError as e:
        raise HTTPException(status_code=422, detail="; ".join(f"{'.'.join(map(str, x['loc']))}: {x['msg']}"
                                                              for x in e.errors())) from None
    try:
        model = request.app.state.registry.get(task)
    except ModelUnavailable as e:
        raise HTTPException(status_code=503, detail=str(e)) from None

    b, c = _slim(model, base), _slim(model, changed)
    # one-at-a-time sensitivity: what happens if each input alone is changed by the amount requested
    spec = TASKS[task]["spec"]
    sens = []
    for f in body.changes:
        solo = schema(**{**body.features, f: body.changes[f]}).model_dump()
        s = _slim(model, solo)
        sens.append({"feature": f, "label": spec[f]["label"], "from": base[f], "to": body.changes[f],
                     "risk_score": s["risk_score"], "delta": s["risk_score"] - b["risk_score"]})
    sens.sort(key=lambda d: abs(d["delta"]), reverse=True)
    return {"task": task, "baseline": b, "scenario": c, "delta": c["risk_score"] - b["risk_score"],
            "per_change": sens,
            "note": "A what-if shows how the MODEL's score changes with different inputs. It does not mean that "
                    "changing the input in real life would change a person's actual risk by this amount."}


@router.get("/analytics/summary")
def analytics(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(Prediction).where(Prediction.user_id == user.id).order_by(Prediction.created_at)).all()
    by_disease: dict[str, list[Prediction]] = defaultdict(list)
    for r in rows:
        by_disease[r.disease].append(r)

    def point(r: Prediction) -> dict:
        ts = r.created_at if r.created_at.tzinfo else r.created_at.replace(tzinfo=__import__("datetime").timezone.utc)
        return {"id": r.id, "at": ts.isoformat(), "risk_score": r.risk_score, "risk_level": r.risk_level}

    series = {d: [point(r) for r in rs] for d, rs in by_disease.items()}
    latest = {}
    for d, rs in by_disease.items():
        last = rs[-1]
        trend = None
        if len(rs) >= 2:
            diff = last.risk_score - rs[-2].risk_score
            trend = "up" if diff > 0.05 else "down" if diff < -0.05 else "steady"
        latest[d] = {**point(last), "trend": trend, "assessments": len(rs),
                     "average_score": sum(r.risk_score for r in rs) / len(rs),
                     "confidence_tier": (last.result.get("confidence") or {}).get("tier")}
    levels = Counter(r.risk_level for r in rows)
    ordered = rows[-8:][::-1]
    return {
        "total_assessments": len(rows),
        "risk_distribution": {k: levels.get(k, 0) for k in ("low", "moderate", "high")},
        "latest": latest, "series": series,
        "recent": [{**point(r), "disease": r.disease} for r in ordered],
        "top_drivers": _top_drivers(by_disease),
    }


def _top_drivers(by_disease: dict[str, list[Prediction]]) -> dict:
    """Features that pushed the latest result of each task up the most (from stored SHAP values)."""
    out = {}
    for d, rs in by_disease.items():
        expl = rs[-1].result.get("explanation") or {}
        spec = TASKS[d]["spec"]
        items = [c for c in expl.get("contributions", []) if c["shap"] > 0][:4]
        out[d] = [{"feature": c["feature"], "label": spec[c["feature"]]["label"], "shap": c["shap"]} for c in items]
    return out
