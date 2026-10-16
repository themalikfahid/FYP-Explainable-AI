"""Measure startup, prediction (with/without SHAP), PDF, history and DB timings.

    python scripts/benchmark.py            -> artifacts/qa/performance.json
Uses a temporary database and synthetic inputs. Numbers depend on the machine.
"""
from __future__ import annotations

import json
import os
import platform
import statistics
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
tmp = tempfile.mkdtemp()
os.environ.update({"APP_ENV": "test", "SECRET_KEY": "bench-secret-key-0123456789-abcdefghijklmnop",
                   "DATABASE_URL": f"sqlite:///{tmp}/bench.db", "EMAIL_MODE": "disabled",
                   "PREDICT_RATE_LIMIT_PER_MINUTE": "100000", "LOGIN_RATE_LIMIT_PER_MINUTE": "100000"})

from fastapi.testclient import TestClient  # noqa: E402

from backend.app.main import create_app  # noqa: E402
from tests.conftest import HEART_HIGH, HIGH_RISK_DIABETES, LIFESTYLE  # noqa: E402


def timed(fn, n):
    out = []
    for _ in range(n):
        t = time.perf_counter()
        fn()
        out.append((time.perf_counter() - t) * 1000)
    return {"n": n, "median_ms": round(statistics.median(out), 1), "p95_ms": round(sorted(out)[int(0.95 * (n - 1))], 1),
            "max_ms": round(max(out), 1)}


def main():
    t0 = time.perf_counter()
    app = create_app()
    with TestClient(app) as c:
        startup_s = round(time.perf_counter() - t0, 2)
        c.post("/api/auth/register", json={"email": "bench@example.com", "password": "Bench1234", "full_name": "Bench"})
        tok = c.post("/api/auth/login", json={"email": "bench@example.com", "password": "Bench1234"}).json()["access_token"]
        h = {"Authorization": f"Bearer {tok}"}
        res = {"startup_seconds_incl_model_load": startup_s}
        res["login_bcrypt"] = timed(lambda: c.post("/api/auth/login", json={"email": "bench@example.com", "password": "Bench1234"}), 10)
        res["predict_diabetes_with_shap"] = timed(lambda: c.post("/api/predict/diabetes", json={"features": HIGH_RISK_DIABETES, "lifestyle": LIFESTYLE}, headers=h), 20)
        res["predict_heart_with_shap"] = timed(lambda: c.post("/api/predict/heart", json={"features": HEART_HIGH, "lifestyle": LIFESTYLE}, headers=h), 20)
        reg = app.state.registry
        res["model_only_heart_no_shap"] = timed(lambda: reg.get("heart").predict(HEART_HIGH, explain=False), 50)
        res["model_only_diabetes_no_shap"] = timed(lambda: reg.get("diabetes").predict(HIGH_RISK_DIABETES, explain=False), 50)
        pid = c.get("/api/predictions?limit=1", headers=h).json()["items"][0]["id"]
        res["pdf_report"] = timed(lambda: c.get(f"/api/predictions/{pid}/report.pdf", headers=h), 20)
        res["history_list_50"] = timed(lambda: c.get("/api/predictions?limit=50", headers=h), 50)
        res["prediction_detail"] = timed(lambda: c.get(f"/api/predictions/{pid}", headers=h), 50)
        res["health"] = timed(lambda: c.get("/api/health"), 50)
    res["machine"] = {"python": platform.python_version(), "platform": platform.platform(), "cpus": os.cpu_count()}
    out = ROOT / "artifacts" / "qa" / "performance.json"
    out.write_text(json.dumps(res, indent=2))
    print(json.dumps(res, indent=2))


if __name__ == "__main__":
    main()
