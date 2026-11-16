"""Incremental API: per-entry CRUD with optimistic concurrency, change feed, estimates and insights."""
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_session
from app.core.errors import ServiceError
from app.core.security import current_user
from app.models import DayLog, FoodEntry, User
from app.schemas import EntryIn, EntryOut, EntryUpdate, EstimateIn, TargetApply
from app.services import estimates, insights
from app.services.common import now_ms, parse_date

router = APIRouter(prefix="/api/v1", tags=["v1"])


def _out(e: FoodEntry) -> EntryOut:
    return EntryOut(id=e.id, date=e.date.isoformat(), meal=e.meal, name=e.name, label=e.label, grams=e.grams,
                    kcal=e.kcal, protein=e.protein, carbs=e.carbs, fat=e.fat, version=e.version,
                    updated_at=e.updated_at, deleted=e.deleted_at is not None)


def _own(db: Session, user: User, entry_id: int) -> FoodEntry:
    e = db.get(FoodEntry, entry_id)
    if not e or e.user_id != user.id or e.deleted_at is not None:
        raise HTTPException(404, "Entry not found")
    return e


def _conflict(e: FoodEntry):
    return HTTPException(409, {"message": "This entry changed on another device", "current": _out(e).model_dump()})


@router.get("/entries", response_model=list[EntryOut])
def list_entries(date: str = Query(pattern=r"^\d{4}-\d{2}-\d{2}$"), user: User = Depends(current_user),
                 db: Session = Depends(get_session)):
    q = select(FoodEntry).where(FoodEntry.user_id == user.id, FoodEntry.date == parse_date(date),
                                FoodEntry.deleted_at.is_(None)).order_by(FoodEntry.position, FoodEntry.id)
    rows = db.scalars(q)
    return [_out(e) for e in rows]


@router.post("/entries", response_model=EntryOut, status_code=201)
def create_entry(b: EntryIn, user: User = Depends(current_user), db: Session = Depends(get_session)):
    d = parse_date(b.date)
    if not d:
        raise HTTPException(422, "Invalid date")
    pos = len(db.scalars(select(FoodEntry.id).where(FoodEntry.user_id == user.id, FoodEntry.date == d)).all())
    e = FoodEntry(user_id=user.id, date=d, position=pos, version=1, updated_at=now_ms(),
                  **b.model_dump(exclude={"date"}))
    db.add(e)
    db.commit()
    return _out(e)


@router.put("/entries/{entry_id}", response_model=EntryOut)
def update_entry(entry_id: int, b: EntryUpdate, user: User = Depends(current_user), db: Session = Depends(get_session)):
    e = _own(db, user, entry_id)
    if b.version != e.version:
        raise _conflict(e)
    d = parse_date(b.date)
    if not d:
        raise HTTPException(422, "Invalid date")
    for k, v in b.model_dump(exclude={"date", "version"}).items():
        setattr(e, k, v)
    e.date, e.version, e.updated_at = d, e.version + 1, now_ms()
    db.commit()
    return _out(e)


@router.delete("/entries/{entry_id}", status_code=204)
def delete_entry(entry_id: int, version: int = Query(ge=1), user: User = Depends(current_user),
                 db: Session = Depends(get_session)):
    e = _own(db, user, entry_id)
    if version != e.version:
        raise _conflict(e)
    e.deleted_at = e.updated_at = now_ms()  # tombstone: other devices learn about the delete via /sync
    e.version += 1
    db.commit()


@router.get("/sync")
def sync(since: int = Query(default=0, ge=0), user: User = Depends(current_user), db: Session = Depends(get_session)):
    """Everything that changed after `since` (epoch ms). Store `server_time` and send it back next time."""
    server_time = now_ms()
    entries = db.scalars(select(FoodEntry).where(FoodEntry.user_id == user.id, FoodEntry.updated_at > since)
                         .order_by(FoodEntry.updated_at)).all()
    days = db.scalars(select(DayLog).where(DayLog.user_id == user.id, DayLog.updated_at > since)).all()
    return {"server_time": server_time, "entries": [_out(e).model_dump() for e in entries],
            "day_logs": [{"date": d.date.isoformat(), "target_kcal": d.target_kcal, "water": d.water,
                          "weight_kg": d.weight_kg, "marker_type": d.marker_type, "marker_note": d.marker_note,
                          "version": d.version, "updated_at": d.updated_at} for d in days]}


@router.post("/estimate")
def estimate_food(b: EstimateIn, request: Request, user: User = Depends(current_user),
                  db: Session = Depends(get_session)):
    return estimates.estimate(db, request.app.state.settings, user.id, b.name, b.kind, b.ingredients,
                              fetch=request.app.state.fetcher)


@router.get("/insights/cache")
def cache_stats(user: User = Depends(current_user), db: Session = Depends(get_session)):
    return estimates.cache_stats(db)


@router.get("/insights/tdee")
def tdee(user: User = Depends(current_user), db: Session = Depends(get_session)):
    return insights.tdee_insight(db, user.id)


@router.post("/insights/tdee/apply")
def apply_tdee(b: TargetApply, user: User = Depends(current_user), db: Session = Depends(get_session)):
    target = b.target or insights.tdee_insight(db, user.id)["suggested_target"]
    if not target:
        raise ServiceError(409, "Not enough data to suggest a target yet")
    insights.apply_target(db, user.id, int(target))
    return {"target": int(target)}
