"""Glue between the database and the pure TDEE engine."""
from collections import defaultdict
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import DayLog, FoodEntry, Profile
from app.services import tdee as engine
from app.services.common import now_ms


def tdee_insight(db: Session, uid: int, today: date | None = None, window: int = 28) -> dict:
    today = today or date.today()
    start = today - timedelta(days=window - 1)
    intake = dict(db.execute(
        select(FoodEntry.date, func.sum(FoodEntry.kcal)).where(
            FoodEntry.user_id == uid, FoodEntry.deleted_at.is_(None), FoodEntry.date >= start,
            FoodEntry.date <= today).group_by(FoodEntry.date)).all())
    weights = dict(db.execute(select(DayLog.date, DayLog.weight_kg).where(
        DayLog.user_id == uid, DayLog.weight_kg.is_not(None), DayLog.date >= start, DayLog.date <= today)).all())
    pts = defaultdict(engine.DayPoint)
    for d in set(intake) | set(weights):
        pts[d] = engine.DayPoint(day=d, intake=intake.get(d), weight=weights.get(d))
    p = db.get(Profile, uid)
    latest_w = weights[max(weights)] if weights else (p.weight_kg if p else None)
    prior = engine.mifflin_tdee(p.age, p.sex, p.height_cm, latest_w, p.activity) if p else None
    est = engine.estimate_tdee(list(pts.values()), prior, today, window=window)
    out = {**est.__dict__, "window_days": window, "current_target": p.target_kcal if p else 2000}
    out["suggested_target"] = engine.suggest_target(est.tdee, p.goal if p else None, p.sex if p else None) \
        if est.tdee else None
    return out


def apply_target(db: Session, uid: int, target: int, today: date | None = None) -> None:
    today = today or date.today()
    p = db.get(Profile, uid)
    p.target_kcal = target
    p.tracker_updated = now_ms()  # newer than any browser-cached copy, so clients pick it up
    row = db.get(DayLog, (uid, today))
    if row:
        row.target_kcal = target
        row.version += 1
        row.updated_at = now_ms()
    db.commit()
