"""Adaptive maintenance-calorie engine.

Idea: energy balance. If you eat X kcal/day on average and your *trend* weight changes by s kg/day,
your maintenance (TDEE) is  X - s * 7700.  Daily scale weights are noisy (water, food in the gut), so the
weight trend is an exponentially smoothed series, and the slope is a least-squares fit over a window.
Sparse or noisy data is blended with the Mifflin-St Jeor formula estimate, so the answer degrades
gracefully to the formula and gains weight as more days are logged.

Everything here is pure (no database), which is what makes it testable and backtestable."""
import random
from dataclasses import dataclass
from datetime import date, timedelta
from statistics import mean

KCAL_PER_KG = 7700
MIN_LOGGED_KCAL = 800  # a day below this is treated as partially logged, not as real intake
ACTIVITY = {"sedentary": 1.2, "light": 1.375, "moderate": 1.55, "very": 1.725}


@dataclass
class DayPoint:
    day: date
    intake: float | None = None     # total kcal logged that day
    weight: float | None = None     # scale weight, kg


@dataclass
class Estimate:
    tdee: float | None
    method: str                     # formula | blended | none
    confidence: str                 # none | low | medium | high
    empirical: float | None = None
    prior: float | None = None
    trend_kg_per_week: float | None = None
    logged_days: int = 0
    weigh_ins: int = 0


def mifflin_tdee(age, sex, height_cm, weight_kg, activity) -> float | None:
    try:
        age, height_cm, weight_kg = float(age), float(height_cm), float(weight_kg)
    except (TypeError, ValueError):
        return None
    if sex not in ("male", "female") or min(age, height_cm, weight_kg) <= 0:
        return None
    bmr = 10 * weight_kg + 6.25 * height_cm - 5 * age + (5 if sex == "male" else -161)
    return bmr * ACTIVITY.get(activity, 1.2)


def smooth_weights(weigh_ins: list[tuple[date, float]], alpha: float = 0.25) -> list[tuple[date, float]]:
    """Time-aware exponential smoothing: a gap of n days moves the trend by 1-(1-alpha)^n."""
    out, trend, last = [], None, None
    for d, w in sorted(weigh_ins):
        if trend is None:
            trend = w
        else:
            a = 1 - (1 - alpha) ** max((d - last).days, 1)
            trend += a * (w - trend)
        out.append((d, trend))
        last = d
    return out


def _slope(points: list[tuple[date, float]]) -> float:
    """Least-squares slope in kg/day."""
    x0 = points[0][0]
    xs = [(d - x0).days for d, _ in points]
    ys = [w for _, w in points]
    mx, my = mean(xs), mean(ys)
    den = sum((x - mx) ** 2 for x in xs)
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=True)) / den if den else 0.0


def estimate_tdee(days: list[DayPoint], prior: float | None, today: date, window: int = 28,
                  min_logged: int = 7, min_weigh_ins: int = 3, min_span: int = 10, shrink_k: float = 14.0) -> Estimate:
    start = today - timedelta(days=window - 1)
    win = [d for d in days if start <= d.day <= today]
    intakes = [d.intake for d in win if d.intake is not None and d.intake >= MIN_LOGGED_KCAL]
    weighs = [(d.day, d.weight) for d in win if d.weight is not None]
    base = Estimate(tdee=prior, method="formula" if prior else "none", confidence="low" if prior else "none",
                    prior=prior, logged_days=len(intakes), weigh_ins=len(weighs))
    span = (max(d for d, _ in weighs) - min(d for d, _ in weighs)).days if len(weighs) > 1 else 0
    if len(intakes) < min_logged or len(weighs) < min_weigh_ins or span < min_span:
        return base
    trend = smooth_weights(weighs)
    slope = _slope(trend)
    empirical = mean(intakes) - slope * KCAL_PER_KG
    lo, hi = (0.6 * prior, 1.6 * prior) if prior else (1000, 5000)  # physiologically sane band
    empirical = min(max(empirical, lo), hi)
    w = len(intakes) / (len(intakes) + shrink_k)
    tdee = w * empirical + (1 - w) * prior if prior else empirical
    conf = ("high" if len(intakes) >= 21 and len(weighs) >= 8
            else "medium" if len(intakes) >= 14 and len(weighs) >= 5 else "low")
    return Estimate(tdee=round(tdee), method="blended", confidence=conf, empirical=round(empirical), prior=prior,
                    trend_kg_per_week=round(slope * 7, 2), logged_days=len(intakes), weigh_ins=len(weighs))


def suggest_target(tdee: float, goal: str | None, sex: str | None) -> int:
    delta = -min(400, round(.2 * tdee)) if goal == "lose" else 300 if goal == "gain" else 0
    floor = 1500 if sex == "male" else 1200
    return max(floor, int(round((tdee + delta) / 50) * 50))


# ------------------------------------------------------------------ simulation / backtest
def simulate_user(seed: int, true_tdee: float = 2600, days: int = 56, start_weight: float = 75.0,
                  intake_mean: float = 2200, log_prob: float = 0.85, weigh_prob: float = 0.7,
                  weight_noise_sd: float = 0.6, logging_bias: float = -0.05, intake_noise_sd: float = 250.0,
                  today: date = date(2026, 11, 13)) -> list[DayPoint]:
    """A synthetic user whose weight really follows energy balance. Logged intake is biased
    (people under-report) and scale readings carry water-weight noise."""
    rng, w, out = random.Random(seed), start_weight, []
    first = today - timedelta(days=days - 1)
    for i in range(days):
        eaten = max(1200, rng.gauss(intake_mean, intake_noise_sd))
        w += (eaten - true_tdee) / KCAL_PER_KG
        out.append(DayPoint(
            day=first + timedelta(days=i),
            intake=eaten * (1 + logging_bias) if rng.random() < log_prob else None,
            weight=w + rng.gauss(0, weight_noise_sd) if rng.random() < weigh_prob else None))
    return out


def backtest(n: int = 200, true_tdee: float = 2600, prior_error: float = 0.15, **kw) -> dict:
    """Compare the engine with the formula alone when the formula is off by +/- prior_error."""
    rng = random.Random(7)
    eng, form = [], []
    for seed in range(n):
        prior = true_tdee * (1 + rng.choice([-1, 1]) * prior_error)
        est = estimate_tdee(simulate_user(seed, true_tdee=true_tdee, **kw), prior, date(2026, 11, 13))
        eng.append(abs(est.tdee - true_tdee))
        form.append(abs(prior - true_tdee))
    return {"runs": n, "engine_mae_kcal": round(mean(eng)), "formula_mae_kcal": round(mean(form)),
            "improvement_pct": round(100 * (1 - mean(eng) / mean(form)), 1)}
