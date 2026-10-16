from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.config import get_settings
from backend.app.db import get_db, session_factory
from backend.app.models import Prediction, User
from backend.app.schemas import DiabetesRequest, HeartRequest, PredictionOut, PredictionSummary
from backend.app.security import get_current_user, limiter
from backend.app.services import email as email_service
from backend.app.services.inference import ModelUnavailable
from backend.app.services.pdf import build_report
from backend.app.services.recommend import recommend

router = APIRouter(prefix="/api", tags=["predictions"])
log = logging.getLogger("app.predictions")


def _alert_job(prediction_id: int, user_id: int) -> None:
    """Runs after the response is sent, with its own DB session."""
    db = session_factory()
    try:
        pred, user = db.get(Prediction, prediction_id), db.get(User, user_id)
        if pred and user:
            email_service.send_alert(db, get_settings(), user, pred)
    finally:
        db.close()


def _to_out(p: Prediction) -> PredictionOut:
    return PredictionOut(id=p.id, disease=p.disease, created_at=p.created_at, inputs=p.inputs, lifestyle=p.lifestyle,
                         predicted_class=p.predicted_class, risk_score=p.risk_score, risk_level=p.risk_level,
                         result=p.result, model_version=p.model_version,
                         alert_status=p.alert.status if p.alert else None)


def _run(task: str, body, request: Request, bg: BackgroundTasks, user: User, db: Session) -> PredictionOut:
    limiter.check(f"predict:{user.id}", get_settings().PREDICT_RATE_LIMIT_PER_MINUTE)
    features = body.features.model_dump()
    lifestyle = body.lifestyle.model_dump() if body.lifestyle else None
    try:
        model = request.app.state.registry.get(task)
    except ModelUnavailable as e:
        raise HTTPException(status_code=503, detail=str(e)) from None
    result = model.predict(features, explain=True)
    result["recommendations"] = recommend(task, features, result["risk_level"], result.get("explanation"), lifestyle)
    pred = Prediction(user_id=user.id, disease=task, inputs=features, lifestyle=lifestyle,
                      predicted_class=result["predicted_class"], risk_score=result["risk_score"],
                      risk_level=result["risk_level"], result=result, model_version=model.version,
                      created_at=datetime.now(timezone.utc))
    if not body.save:
        out = _to_out(pred)
        return out
    db.add(pred)
    db.commit()
    db.refresh(pred)
    log.info("prediction saved id=%s user=%s task=%s", pred.id, user.id, task)  # no health values in logs
    if email_service.should_alert(pred, user):
        bg.add_task(_alert_job, pred.id, user.id)
    return _to_out(pred)


@router.post("/predict/diabetes", response_model=PredictionOut)
def predict_diabetes(body: DiabetesRequest, request: Request, bg: BackgroundTasks,
                     user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _run("diabetes", body, request, bg, user, db)


@router.post("/predict/heart", response_model=PredictionOut)
def predict_heart(body: HeartRequest, request: Request, bg: BackgroundTasks,
                  user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _run("heart", body, request, bg, user, db)


def _owned(db: Session, user: User, pid: int) -> Prediction:
    p = db.get(Prediction, pid)
    if p is None or p.user_id != user.id:  # identical 404 for "missing" and "not yours"
        raise HTTPException(status_code=404, detail="Prediction not found")
    return p


@router.get("/predictions")
def list_predictions(disease: Literal["diabetes", "heart"] | None = None,
                     limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0),
                     user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    q = select(Prediction).where(Prediction.user_id == user.id)
    cq = select(func.count()).select_from(Prediction).where(Prediction.user_id == user.id)
    if disease:
        q, cq = q.where(Prediction.disease == disease), cq.where(Prediction.disease == disease)
    rows = db.scalars(q.order_by(Prediction.created_at.desc(), Prediction.id.desc()).limit(limit).offset(offset)).all()
    return {"total": db.scalar(cq), "items": [PredictionSummary.model_validate(r).model_dump() for r in rows]}


@router.get("/predictions/{pid}", response_model=PredictionOut)
def get_prediction(pid: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _to_out(_owned(db, user, pid))


@router.delete("/predictions/{pid}", status_code=204)
def delete_prediction(pid: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    db.delete(_owned(db, user, pid))
    db.commit()
    return Response(status_code=204)


@router.get("/predictions/{pid}/report.pdf")
def report(pid: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p = _owned(db, user, pid)
    pdf = build_report(p, user)
    return Response(content=pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="health-report-{p.id}.pdf"',
                             "Cache-Control": "no-store"})
