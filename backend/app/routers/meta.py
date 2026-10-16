"""Public, non-personal endpoints: health, feature specs, model info, BMI and lifestyle tools."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import text

from backend.app.config import get_settings
from backend.app.db import get_engine
from backend.app.schemas import BMIIn, LifestyleIn
from backend.app.security import client_ip, limiter
from backend.app.services.inference import ModelUnavailable
from backend.app.services.recommend import DISCLAIMER
from backend.app.services.scoring import bmi, lifestyle_score
from ml.data import TASKS

router = APIRouter(prefix="/api", tags=["meta"])


@router.get("/health")
def health(request: Request):
    db_ok = True
    try:
        with get_engine().connect() as c:
            c.execute(text("SELECT 1"))
    except Exception:
        db_ok = False
    models = request.app.state.registry.status()
    ok = db_ok and all(v == "loaded" for v in models.values())
    return {"status": "ok" if ok else "degraded", "database": "ok" if db_ok else "error", "models": models,
            "email_mode": get_settings().EMAIL_MODE, "environment": get_settings().APP_ENV}


@router.get("/meta/features")
def features():
    return {t: {"title": v["title"], "features": v["features"], "spec": v["spec"],
                "class_labels": {str(k): s for k, s in v["class_labels"].items()}} for t, v in TASKS.items()} | {
        "disclaimer": DISCLAIMER}


@router.get("/meta/models/{task}")
def model_info(task: str, request: Request):
    if task not in TASKS:
        raise HTTPException(status_code=404, detail="Unknown task")
    try:
        m = request.app.state.registry.get(task)
    except ModelUnavailable as e:
        raise HTTPException(status_code=503, detail=str(e)) from None
    meta = m.meta
    slim = {k: {kk: vv for kk, vv in v.items() if kk not in ("calibration_table",)}
            for k, v in meta["test_metrics"].items()}
    return {"task": task, "title": meta["title"], "version": m.version, "split": meta["split"],
            "hybrid_strategy": m.strategy, "hybrid_description": m.strategy_text,
            "hybrid_candidates": meta.get("hybrid_candidates"),
            "class_distribution_train": meta["class_distribution_train"], "best_params": meta["best_params"],
            "cv_train_repeated": {k: {mk: {"mean": mv["mean"], "std": mv["std"]} for mk, mv in v.items()}
                                  for k, v in meta["cv_train_repeated"].items()},
            "test_metrics": slim, "calibration": {k: v["calibration_table"] for k, v in meta["test_metrics"].items()},
            "risk_thresholds": meta["risk_thresholds"], "global_shap": m.global_shap,
            "leave_one_site_out_hybrid": meta.get("leave_one_site_out_hybrid")}


@router.post("/tools/bmi")
def bmi_tool(body: BMIIn, request: Request):
    limiter.check(f"tools:{client_ip(request)}", 60)
    return bmi(body.height_cm, body.weight_kg, body.asian_bmi_cutoffs)


@router.post("/tools/lifestyle-score")
def lifestyle_tool(ls: LifestyleIn, request: Request):
    limiter.check(f"tools:{client_ip(request)}", 60)
    return {"lifestyle_score": lifestyle_score(ls.sleep_hours, ls.activity_minutes_week, ls.fruit_veg_servings_day,
                                               ls.smoking, ls.alcohol_units_week),
            "bmi": bmi(ls.height_cm, ls.weight_kg, ls.asian_bmi_cutoffs)}
