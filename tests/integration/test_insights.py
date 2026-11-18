"""Tests for the v2 modules: confidence gate, Type-1 indicator, what-if simulator, analytics."""
from __future__ import annotations

from tests.conftest import HEART_HIGH, HIGH_RISK_DIABETES, LOW_RISK_DIABETES, register_and_login

T1D_CLASSIC = {"age": 9, "polyuria": 1, "polydipsia": 1, "weight_loss": 1, "fatigue": 1, "bedwetting": 1,
               "abdominal_pain_vomiting": 1, "fruity_breath_or_fast_breathing": 1, "symptom_weeks": 3}
T1D_NONE = {"age": 55, "bmi_category": "obese"}


def test_prediction_includes_confidence_and_cv_headline(client, auth):
    r = client.post("/api/predict/diabetes", json={"features": HIGH_RISK_DIABETES, "save": False}, headers=auth)
    assert r.status_code == 200, r.text
    res = r.json()["result"]
    c = res["confidence"]
    assert c["tier"] in ("confident", "inconclusive", "unrated")
    assert 0.5 <= c["value"] <= 1.0
    cv = res["model"]["cross_validated"]
    assert 0.8 < cv["cv_accuracy"] <= 1.0
    assert cv["confident_accuracy"] >= cv["cv_accuracy"]


def test_model_info_exposes_out_of_fold_report(client):
    for task, n in (("diabetes", 251), ("heart", 918), ("cad", 303)):
        r = client.get(f"/api/meta/models/{task}")
        assert r.status_code == 200
        cv = r.json()["cross_validated"]
        assert cv["n_records"] == n and cv["gate"]["table"]
        # accuracy must be non-decreasing-ish with the gate: highest confidence bin beats the overall figure
        assert cv["gate"]["table"][-1]["accuracy"] >= cv["overall"]["accuracy"] - 1e-9


def test_t1d_indicator_classic_vs_unlikely(client, auth):
    hi = client.post("/api/assess/t1d", json=T1D_CLASSIC, headers=auth)
    assert hi.status_code == 200, hi.text
    h = hi.json()
    assert h["band"] == "strong" and h["emergency_warning"] is True and h["emergency_signs"]
    lo = client.post("/api/assess/t1d", json=T1D_NONE, headers=auth).json()
    assert lo["band"] == "low" and lo["score"] < h["score"] and lo["emergency_warning"] is False
    assert "limitations" in lo and lo["limitations"]


def test_t1d_lab_flags_and_validation(client, auth):
    r = client.post("/api/assess/t1d", json={"age": 30, "hba1c": 9.0, "fasting_glucose": 150}, headers=auth).json()
    assert r["meets_diagnostic_range"] is True and r["lab_flags"]
    assert client.post("/api/assess/t1d", json={"age": 0}, headers=auth).status_code == 422
    assert client.post("/api/assess/t1d", json={"age": 20, "bogus": 1}, headers=auth).status_code == 422
    assert client.post("/api/assess/t1d", json=T1D_NONE).status_code == 401


def test_whatif_changes_score_in_expected_direction(client, auth):
    r = client.post("/api/whatif/heart", json={"features": HEART_HIGH, "changes": {"exang": 0, "oldpeak": 0.0, "thalach": 170}}, headers=auth)
    assert r.status_code == 200, r.text
    w = r.json()
    assert w["scenario"]["risk_score"] < w["baseline"]["risk_score"] and w["delta"] < 0
    assert {c["feature"] for c in w["per_change"]} == {"exang", "oldpeak", "thalach"}


def test_whatif_validation_and_no_persistence(client, auth):
    assert client.post("/api/whatif/heart", json={"features": HEART_HIGH, "changes": {"nope": 1}}, headers=auth).status_code in (400, 422)
    assert client.post("/api/whatif/heart", json={"features": HEART_HIGH, "changes": {"age": 500}}, headers=auth).status_code in (400, 422)
    assert client.post("/api/whatif/unknown", json={"features": {}, "changes": {}}, headers=auth).status_code in (404, 422)
    assert client.get("/api/predictions", headers=auth).json()["total"] == 0


def test_analytics_summary_empty_and_populated(client, auth):
    empty = client.get("/api/analytics/summary", headers=auth).json()
    assert empty["total_assessments"] == 0 and empty["recent"] == []
    client.post("/api/predict/diabetes", json={"features": LOW_RISK_DIABETES, "save": True}, headers=auth)
    client.post("/api/predict/diabetes", json={"features": HIGH_RISK_DIABETES, "save": True}, headers=auth)
    client.post("/api/predict/heart", json={"features": HEART_HIGH, "save": True}, headers=auth)
    a = client.get("/api/analytics/summary", headers=auth).json()
    assert a["total_assessments"] == 3 and sum(a["risk_distribution"].values()) == 3
    assert set(a["latest"]) == {"diabetes", "heart"} and a["latest"]["diabetes"]["assessments"] == 2
    assert a["latest"]["diabetes"]["trend"] in ("up", "down", "steady")
    assert len(a["series"]["diabetes"]) == 2 and a["top_drivers"]


def test_analytics_is_per_user(client):
    a = register_and_login(client, "a@example.com")
    b = register_and_login(client, "b@example.com", name="Bob Test")
    client.post("/api/predict/diabetes", json={"features": HIGH_RISK_DIABETES, "save": True}, headers=a)
    assert client.get("/api/analytics/summary", headers=b).json()["total_assessments"] == 0
    assert client.get("/api/analytics/summary").status_code == 401
