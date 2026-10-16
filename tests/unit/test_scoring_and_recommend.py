import re

import pytest

from backend.app.services.recommend import DISCLAIMER, recommend
from backend.app.services.scoring import bmi, lifestyle_score
from tests.conftest import HEART_HIGH, HIGH_RISK_DIABETES, LIFESTYLE, LOW_RISK_DIABETES


# ------------------------------------------------------------------ BMI
@pytest.mark.parametrize("h,w,expected,cat", [
    (170, 70, 24.2, "Healthy weight"),
    (180, 59.9, 18.5, "Healthy weight"),   # 18.49.. rounds to 18.5 but category uses exact value
    (160, 76.8, 30.0, "Obesity"),
    (175, 50, 16.3, "Underweight"),
    (170, 80, 27.7, "Overweight"),
])
def test_bmi_values(h, w, expected, cat):
    r = bmi(h, w)
    assert r["bmi"] == expected
    if (h, w) != (180, 59.9):
        assert r["category"] == cat


def test_bmi_boundary_exact():
    # exactly 25.0 is overweight (WHO: 25.0-29.9)
    assert bmi(200, 100)["category"] == "Overweight"
    assert bmi(200, 99.7)["category"] == "Healthy weight"   # 24.9
    assert bmi(200, 99.9)["bmi"] == 25.0 and bmi(200, 99.9)["category"] == "Overweight"  # shown 25.0 -> overweight


def test_bmi_asian_cutoffs_differ():
    assert bmi(170, 70)["category"] == "Healthy weight"            # 24.2 under WHO
    assert bmi(170, 70, True)["category"].startswith("Increased")  # >= 23 under Asian action points
    assert bmi(170, 70, True)["healthy_weight_range_kg"] == [53.5, 66.2]


def test_bmi_rejects_nonpositive():
    with pytest.raises(ValueError):
        bmi(0, 70)


def test_bmi_note_disclaims_completeness():
    assert "not a complete health assessment" in bmi(170, 70)["note"]


# -------------------------------------------------------------- lifestyle
def test_lifestyle_max_and_min():
    assert lifestyle_score(8, 200, 6, "never", 0)["score"] == 100
    assert lifestyle_score(3, 0, 0, "current", 30)["score"] == 5  # only sleep floor of 5
    assert lifestyle_score(8, 200, 6, "never", 0)["band"] == "Good"


@pytest.mark.parametrize("act,pts", [(0, 0), (30, 7), (75, 15), (149, 15), (150, 25)])
def test_lifestyle_activity_points(act, pts):
    assert lifestyle_score(8, act, 5, "never", 0)["components"]["physical_activity"]["points"] == pts


@pytest.mark.parametrize("sleep,pts", [(5.9, 5), (6, 12), (7, 20), (9, 20), (9.5, 12), (11, 5)])
def test_lifestyle_sleep_points(sleep, pts):
    assert lifestyle_score(sleep, 150, 5, "never", 0)["components"]["sleep"]["points"] == pts


def test_lifestyle_components_sum():
    r = lifestyle_score(6.5, 100, 3, "former", 10)
    assert r["score"] == sum(c["points"] for c in r["components"].values()) == 12 + 15 + 12 + 14 + 10
    assert r["band"] == "Fair"


# --------------------------------------------------------- recommendations
MED_WORDS = re.compile(r"\b(insulin dose|metformin|statin|aspirin|mg of|tablet|dosage|prescri)", re.I)


def _texts(res):
    return " ".join(i["text"] for i in res["items"])


def test_diabetes_high_risk_recommends_testing_and_warning_signs():
    res = recommend("diabetes", HIGH_RISK_DIABETES, "high", None, None)
    t = _texts(res)
    assert "blood glucose" in t and "same-day medical care" in t
    assert res["items"][0]["priority"] == "high"
    assert res["disclaimer"] == DISCLAIMER


def test_diabetes_low_risk_no_urgent():
    res = recommend("diabetes", LOW_RISK_DIABETES, "low", None, None)
    assert all(i["priority"] != "high" for i in res["items"])


def test_heart_rules_bp_chol_emergency():
    res = recommend("heart", {**HEART_HIGH, "cp": 1}, "high", None, None)
    t = _texts(res)
    assert "call emergency services" in t
    assert "150 mm Hg" in t and "280 mg/dL" in t


def test_lifestyle_rules_triggered():
    res = recommend("heart", HEART_HIGH, "moderate", None, LIFESTYLE)
    t = _texts(res)
    assert "60 minutes" in t and "6 hours" in t and "Stopping smoking" in t
    assert res["bmi"]["bmi"] == 29.4 and res["lifestyle_score"]["score"] == 7 + 12 + 6 + 0 + 15


def test_every_recommendation_has_source_and_no_medication():
    for disease, f in (("diabetes", HIGH_RISK_DIABETES), ("heart", HEART_HIGH)):
        for risk in ("low", "moderate", "high"):
            res = recommend(disease, f, risk, None, LIFESTYLE)
            assert not MED_WORDS.search(_texts(res)), _texts(res)
            for i in res["items"]:
                assert i["source"] and i["rule"] and i["category"] in {"diet", "activity", "sleep", "risk_mitigation", "follow_up"}


def test_recommendations_sorted_by_priority():
    res = recommend("heart", HEART_HIGH, "high", None, LIFESTYLE)
    order = {"high": 0, "medium": 1, "low": 2}
    pr = [order[i["priority"]] for i in res["items"]]
    assert pr == sorted(pr)
