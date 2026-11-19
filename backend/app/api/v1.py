"""Incremental API: per-entry CRUD with optimistic concurrency, per-day facts, recipes, the food catalogue,
change feed, estimates and insights."""
import json

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.db import get_session
from app.core.errors import ServiceError
from app.core.security import current_user
from app.models import DayLog, FoodEntry, Profile, Recipe, User
from app.schemas import (
    DayIn,
    DayOut,
    EntryIn,
    EntryOut,
    EntryUpdate,
    EstimateIn,
    MuscleSuggestIn,
    RecipeIn,
    RecipeOut,
    RecipeUpdate,
    TargetApply,
)
from app.services import catalog, estimates, insights, muscles, recipes
from app.services.common import now_ms, parse_date

router = APIRouter(prefix="/api/v1", tags=["v1"])


def _snap(lines) -> str | None:
    return json.dumps([i.model_dump() for i in lines]) if lines else None


def _out(e: FoodEntry) -> EntryOut:
    return EntryOut(id=e.id, date=e.date.isoformat(), meal=e.meal, name=e.name, label=e.label, grams=e.grams,
                    kcal=e.kcal, protein=e.protein, carbs=e.carbs, fat=e.fat,
                    ingredients=json.loads(e.ingredients) if e.ingredients else None, version=e.version,
                    updated_at=e.updated_at, deleted=e.deleted_at is not None)


def _own(db: Session, user: User, entry_id: int) -> FoodEntry:
    e = db.get(FoodEntry, entry_id)
    if not e or e.user_id != user.id or e.deleted_at is not None:
        raise HTTPException(404, "Entry not found")
    return e


def _conflict(e: FoodEntry):
    return HTTPException(409, {"message": "This entry changed on another device", "current": _out(e).model_dump()})


# ------------------------------------------------------------------ built-in food catalogue
@router.get("/foods")
def foods(response: Response, user: User = Depends(current_user)):
    """The built-in catalogue (per 100 g, with unit weights). Static, so browsers may cache it for an hour."""
    response.headers["Cache-Control"] = "private, max-age=3600"
    return catalog.load()


# ------------------------------------------------------------------ food entries
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
                  ingredients=_snap(b.ingredients), **b.model_dump(exclude={"date", "ingredients"}))
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
    for k, v in b.model_dump(exclude={"date", "version", "ingredients"}).items():
        setattr(e, k, v)
    e.ingredients = _snap(b.ingredients)
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


# ------------------------------------------------------------------ recipes
def _own_recipe(db: Session, user: User, recipe_id: int) -> Recipe:
    r = db.get(Recipe, recipe_id)
    if not r or r.owner_id != user.id:
        raise HTTPException(404, "Recipe not found")
    return r


def _name_taken(db: Session, user: User, name_norm: str, except_id: int | None = None) -> bool:
    q = select(Recipe.id).where(Recipe.owner_id == user.id, Recipe.name_norm == name_norm)
    if except_id is not None:
        q = q.where(Recipe.id != except_id)
    return db.scalar(q) is not None


NAME_TAKEN = "You already have a recipe with that name"


@router.get("/recipes", response_model=list[RecipeOut])
def list_recipes(user: User = Depends(current_user), db: Session = Depends(get_session)):
    rows = db.scalars(select(Recipe).where(Recipe.owner_id == user.id).order_by(Recipe.name_norm))
    return [recipes.to_out(r) for r in rows]


@router.post("/recipes", response_model=RecipeOut, status_code=201)
def create_recipe(b: RecipeIn, user: User = Depends(current_user), db: Session = Depends(get_session)):
    vals = recipes.values(b)
    if _name_taken(db, user, vals["name_norm"]):
        raise HTTPException(409, NAME_TAKEN)
    r = Recipe(owner_id=user.id, version=1, updated_at=now_ms(), **vals)
    db.add(r)
    try:
        db.commit()
    except IntegrityError:  # same name created on another device at the same moment
        db.rollback()
        raise HTTPException(409, NAME_TAKEN) from None
    return recipes.to_out(r)


@router.put("/recipes/{recipe_id}", response_model=RecipeOut)
def update_recipe(recipe_id: int, b: RecipeUpdate, user: User = Depends(current_user),
                  db: Session = Depends(get_session)):
    r = _own_recipe(db, user, recipe_id)
    if b.version != r.version:
        raise HTTPException(409, {"message": "This recipe changed on another device",
                                  "current": recipes.to_out(r).model_dump()})
    vals = recipes.values(b)
    if _name_taken(db, user, vals["name_norm"], except_id=r.id):
        raise HTTPException(409, NAME_TAKEN)
    for k, v in vals.items():
        setattr(r, k, v)
    r.version, r.updated_at = r.version + 1, now_ms()
    db.commit()
    return recipes.to_out(r)


@router.delete("/recipes/{recipe_id}", status_code=204)
def delete_recipe(recipe_id: int, user: User = Depends(current_user), db: Session = Depends(get_session)):
    """Entries already logged keep their own ingredient snapshot, so old days are unaffected."""
    db.delete(_own_recipe(db, user, recipe_id))
    db.commit()


# ------------------------------------------------------------------ per-day facts
def _day_out(d: DayLog) -> DayOut:
    return DayOut(date=d.date.isoformat(), target_kcal=d.target_kcal, water=d.water, weight_kg=d.weight_kg,
                  marker_type=d.marker_type, marker_note=d.marker_note, version=d.version, updated_at=d.updated_at)


@router.put("/days/{day}", response_model=DayOut)
def put_day(day: str, b: DayIn, user: User = Depends(current_user), db: Session = Depends(get_session)):
    """Save a day's water, weight, marker and target. `version` is the one the client last saw (0 for a new day)."""
    d = parse_date(day)
    if not d:
        raise HTTPException(422, "Invalid date")
    changed = {"message": "This day changed on another device"}
    row = db.get(DayLog, (user.id, d))
    if row is None and b.version != 0:
        raise HTTPException(409, {**changed, "current": None})
    if row is not None and b.version != row.version:
        raise HTTPException(409, {**changed, "current": _day_out(row).model_dump()})
    p = db.get(Profile, user.id)
    fields = {"target_kcal": b.target_kcal or (p.target_kcal if p else 2000), "water": b.water,
              "weight_kg": b.weight_kg, "marker_type": b.marker_type,
              "marker_note": (b.marker_note or "") if b.marker_type else None}
    if row is None:
        row = DayLog(user_id=user.id, date=d, version=1, updated_at=now_ms(), **fields)
        db.add(row)
    else:
        for k, v in fields.items():
            setattr(row, k, v)
        row.version += 1
        row.updated_at = now_ms()
    try:
        db.commit()
    except IntegrityError:  # two devices created the same day at the same moment
        db.rollback()
        raise HTTPException(409, {**changed, "current": None}) from None
    return _day_out(row)


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


@router.post("/exercises/suggest-muscles")
def suggest_muscles(b: MuscleSuggestIn, request: Request, user: User = Depends(current_user),
                    db: Session = Depends(get_session)):
    return muscles.suggest(db, request.app.state.settings, user.id, b.name, fetch=request.app.state.fetcher)


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