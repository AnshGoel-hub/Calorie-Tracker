from datetime import date, timedelta

import pytest

from app.services import tdee
from app.services.tdee import DayPoint

TODAY = date(2026, 11, 13)


def test_mifflin_matches_the_formula():
    assert tdee.mifflin_tdee(21, "male", 175, 70, "light") == pytest.approx((10 * 70 + 6.25 * 175 - 5 * 21 + 5) * 1.375)
    assert tdee.mifflin_tdee(21, "other", 175, 70, "light") is None
    assert tdee.mifflin_tdee(None, "male", 175, 70, "light") is None


def test_smoothing_damps_a_noisy_spike():
    ws = [(TODAY - timedelta(days=9 - i), w) for i, w in enumerate([70, 70, 70, 72, 70, 70, 70, 70, 70, 70])]
    trend = dict(tdee.smooth_weights(ws))
    assert trend[TODAY - timedelta(days=6)] < 71          # a 2 kg water spike moves the trend well under 1 kg


def test_no_data_returns_formula_or_nothing():
    assert tdee.estimate_tdee([], 2400, TODAY).method == "formula"
    assert tdee.estimate_tdee([], None, TODAY).confidence == "none"


def test_too_little_data_falls_back_to_the_formula():
    days = [DayPoint(TODAY - timedelta(days=i), intake=2000, weight=70) for i in range(5)]
    est = tdee.estimate_tdee(days, 2400, TODAY)
    assert est.method == "formula" and est.tdee == 2400


def test_losing_weight_on_2000_kcal_implies_higher_maintenance():
    # 0.5 kg/week loss at 2000 kcal/day  ->  maintenance about 2000 + 0.5*7700/7 = 2550
    days = [DayPoint(TODAY - timedelta(days=27 - i), intake=2000, weight=75 - 0.5 / 7 * i) for i in range(28)]
    est = tdee.estimate_tdee(days, None, TODAY)
    assert est.method == "blended" and est.empirical == pytest.approx(2550, abs=40)
    assert est.trend_kg_per_week == pytest.approx(-0.5, abs=0.05) and est.confidence == "high"


def test_short_days_are_not_counted_as_logged():
    days = [DayPoint(TODAY - timedelta(days=i), intake=300, weight=70 + i * 0.01) for i in range(28)]
    assert tdee.estimate_tdee(days, 2400, TODAY).logged_days == 0


def test_estimate_is_pulled_toward_the_formula_when_data_is_thin():
    thin = [DayPoint(TODAY - timedelta(days=i), intake=2000, weight=75 - 0.07 * (13 - i) if i % 5 == 0 else None)
            for i in range(14)]
    est = tdee.estimate_tdee(thin, 2400, TODAY, min_logged=7)
    assert est.method == "blended" and est.confidence == "low"
    assert min(est.empirical, est.prior) <= est.tdee <= max(est.empirical, est.prior)


def test_suggested_target_respects_goal_and_safety_floor():
    assert tdee.suggest_target(2600, "maintain", "male") == 2600
    assert tdee.suggest_target(2600, "lose", "male") == 2200
    assert tdee.suggest_target(2600, "gain", "male") == 2900
    assert tdee.suggest_target(1500, "lose", "female") == 1200
    assert tdee.suggest_target(1500, "lose", "male") == 1500


def test_backtest_beats_a_wrong_formula():
    r = tdee.backtest(n=100)
    assert r["engine_mae_kcal"] < 0.6 * r["formula_mae_kcal"]


def test_backtest_still_improves_when_everyone_under_reports():
    r = tdee.backtest(n=100, logging_bias=-0.15)
    assert r["engine_mae_kcal"] < r["formula_mae_kcal"]


def test_simulation_is_deterministic():
    assert tdee.simulate_user(3) == tdee.simulate_user(3)


# --- through the API
def _fill(client, days=28):
    from datetime import date as d
    log = {}
    for i in range(days):
        day = (d.today() - timedelta(days=days - 1 - i)).isoformat()
        log[day] = {"t": 2000, "w": 0, "wt": round(75 - 0.5 / 7 * i, 2),
                    "e": [{"n": "Meals", "l": "", "g": 1, "k": 2000, "p": 0, "c": 0, "f": 0, "m": "Lunch"}]}
    return log


def test_insight_endpoint_without_data_has_no_target(client, user):
    j = client.get("/api/v1/insights/tdee").json()
    assert j["tdee"] is None and j["suggested_target"] is None and j["confidence"] == "none"
    assert client.post("/api/v1/insights/tdee/apply", json={}).status_code == 409


def test_insight_endpoint_uses_logged_data_and_apply_updates_target(client, user):
    profile = {"age": 21, "sex": "male", "height": 175, "weight": 75, "activity": "light", "goal": "lose"}
    client.post("/api/data", json={"log": _fill(client), "custom": [], "target": 2000, "profile": profile,
                                   "updated": 5})
    j = client.get("/api/v1/insights/tdee").json()
    assert j["method"] == "blended" and j["confidence"] == "high" and 2300 < j["tdee"] < 2700
    assert j["suggested_target"] == tdee.suggest_target(j["tdee"], "lose", "male")
    applied = client.post("/api/v1/insights/tdee/apply", json={}).json()
    assert applied["target"] == j["suggested_target"]
    got = client.get("/api/data").json()
    assert got["target"] == applied["target"] and got["updated"] > 5   # newer than any cached browser copy
    assert client.post("/api/v1/insights/tdee/apply", json={"target": 100}).status_code == 422
