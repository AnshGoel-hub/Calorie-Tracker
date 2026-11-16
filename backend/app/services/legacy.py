"""Compatibility layer: presents the normalized tables as the two JSON documents the current
frontend reads and writes (`/api/data` and `/api/workouts`).

Writes are snapshot-style: the user's rows are replaced with the submitted document inside one
transaction. Food entries and per-day facts can be left out of that replacement (`entries=False`,
`days=False`) because the frontend saves them one by one through /api/v1. This exists only until the
frontend has moved everything to the incremental endpoints."""
from sqlalchemy import delete, insert, select
from sqlalchemy.orm import Session

from app.models import CustomExercise, DayLog, Food, FoodEntry, FoodUnit, Profile, Workout, WorkoutExercise, WorkoutSet
from app.services.common import clip, norm_name, now_ms, num, opt_num, parse_date


def get_or_create_profile(db: Session, uid: int) -> Profile:
    p = db.get(Profile, uid)
    if not p:
        p = Profile(user_id=uid, target_kcal=2000, weekly_workout_goal=3, setup_done=False,
                    body_weight_kg=0, tracker_updated=0, workouts_updated=0)
        db.add(p)
        db.flush()
    return p


def _bulk(db: Session, model, rows: list[dict]) -> None:
    """Insert many rows with a single executemany (one network round trip on Postgres)."""
    if rows:
        db.execute(insert(model), rows)


# ------------------------------------------------------------------ tracker document
def read_tracker(db: Session, uid: int) -> dict:
    p = db.get(Profile, uid)
    target = p.target_kcal if p else 2000
    entries = db.scalars(select(FoodEntry).where(FoodEntry.user_id == uid, FoodEntry.deleted_at.is_(None))
                         .order_by(FoodEntry.date, FoodEntry.position, FoodEntry.id)).all()
    by_day: dict[str, list] = {}
    for e in entries:
        by_day.setdefault(e.date.isoformat(), []).append(
            {"id": e.id, "v": e.version, "n": e.name, "l": e.label, "g": e.grams, "k": e.kcal,
             "p": e.protein, "c": e.carbs, "f": e.fat, "m": e.meal})
    log, marks, dv = {}, {}, {}
    for d in db.scalars(select(DayLog).where(DayLog.user_id == uid)).all():
        k = d.date.isoformat()
        dv[k] = d.version
        if d.marker_type:
            marks[k] = {"t": d.marker_type, "n": d.marker_note or ""}
        if by_day.get(k) or d.water or d.weight_kg is not None:
            log[k] = {"t": d.target_kcal, "e": by_day.pop(k, []), "w": d.water or 0, "wt": d.weight_kg}
    for k, e in by_day.items():  # entries on a day that has no DayLog row (created through /api/v1)
        log[k] = {"t": target, "e": e, "w": 0, "wt": None}
    custom = []
    units_by_food: dict[int, list] = {}
    for u in db.scalars(select(FoodUnit).join(Food, Food.id == FoodUnit.food_id)
                        .where(Food.owner_id == uid).order_by(FoodUnit.food_id, FoodUnit.position)):
        units_by_food.setdefault(u.food_id, []).append({"n": u.name, "g": u.grams})
    for f in db.scalars(select(Food).where(Food.owner_id == uid).order_by(Food.id)).all():
        item = {"n": f.name, "k": f.kcal, "p": f.protein, "c": f.carbs, "f": f.fat,
                "units": units_by_food.get(f.id, [])}
        if f.source == "ai":
            item.update({"est": True, "kind": f.kind})
        custom.append(item)
    prof = {}
    if p:
        for key, val in (("age", p.age), ("sex", p.sex), ("height", p.height_cm), ("weight", p.weight_kg),
                         ("activity", p.activity), ("goal", p.goal)):
            if val is not None:
                prof[key] = val
    return {"log": log, "custom": custom, "target": target, "updated": p.tracker_updated if p else 0,
            "setup": bool(p and p.setup_done), "profile": prof, "marks": marks,
            "goals": {"weekly": p.weekly_workout_goal} if p else {}, "dv": dv}


def write_tracker(db: Session, uid: int, doc: dict, commit: bool = True, entries: bool = True,
                  days: bool = True) -> None:
    p = get_or_create_profile(db, uid)
    target = num(doc.get("target"), 2000) or 2000
    prof = doc.get("profile") or {}
    goals = doc.get("goals") or {}
    p.target_kcal = target
    p.setup_done = bool(doc.get("setup"))
    p.tracker_updated = int(num(doc.get("updated"), 0))
    if goals.get("weekly"):
        p.weekly_workout_goal = max(1, min(14, int(num(goals["weekly"], 3))))
    p.age, p.height_cm, p.weight_kg = (opt_num(prof.get("age")), opt_num(prof.get("height")),
                                       opt_num(prof.get("weight")))
    p.sex, p.activity, p.goal = (clip(prof.get("sex"), 10) or None, clip(prof.get("activity"), 20) or None,
                                 clip(prof.get("goal"), 20) or None)

    if entries:
        db.execute(delete(FoodEntry).where(FoodEntry.user_id == uid))
    if days:
        db.execute(delete(DayLog).where(DayLog.user_id == uid))
    db.execute(delete(Food).where(Food.owner_id == uid))  # units go with them (ON DELETE CASCADE)
    ts = now_ms()
    days_rows: dict = {}
    entry_rows: list[dict] = []
    for k, g in (doc.get("log") or {}).items():
        d = parse_date(k)
        if not d or not isinstance(g, dict):
            continue
        days_rows[d] = {"user_id": uid, "date": d, "target_kcal": num(g.get("t"), target) or target,
                        "water": int(num(g.get("w"), 0)), "weight_kg": opt_num(g.get("wt")), "marker_type": None,
                        "marker_note": None, "version": 1, "updated_at": ts}
        for i, x in enumerate(g.get("e") or []):
            entry_rows.append({"user_id": uid, "date": d, "meal": clip(x.get("m") or "Snacks", 20), "position": i,
                               "name": clip(x.get("n"), 200), "label": clip(x.get("l"), 200),
                               "grams": num(x.get("g")), "kcal": num(x.get("k")), "protein": num(x.get("p")),
                               "carbs": num(x.get("c")), "fat": num(x.get("f")), "version": 1, "updated_at": ts,
                               "deleted_at": None})
    for k, m in (doc.get("marks") or {}).items():
        d = parse_date(k)
        if not d or not isinstance(m, dict) or not m.get("t"):
            continue
        row = days_rows.setdefault(d, {"user_id": uid, "date": d, "target_kcal": target, "water": 0,
                                       "weight_kg": None, "marker_type": None, "marker_note": None, "version": 1,
                                       "updated_at": ts})
        row["marker_type"], row["marker_note"] = clip(m.get("t"), 10), clip(m.get("n"), 60)
    if days:
        _bulk(db, DayLog, list(days_rows.values()))
    if entries:
        _bulk(db, FoodEntry, entry_rows)

    seen, foods = set(), []
    for c in doc.get("custom") or []:
        nm = norm_name(c.get("n"))
        if not nm or nm in seen:
            continue
        seen.add(nm)
        foods.append((c, {"owner_id": uid, "name": clip(c.get("n"), 200).strip(), "name_norm": nm,
                          "kcal": num(c.get("k")), "protein": num(c.get("p")), "carbs": num(c.get("c")),
                          "fat": num(c.get("f")), "source": "ai" if c.get("est") else "user",
                          "kind": clip(c.get("kind"), 20) or None}))
    _bulk(db, Food, [r for _, r in foods])
    food_id = {n: i for i, n in db.execute(select(Food.id, Food.name_norm).where(Food.owner_id == uid))}  # 1 query
    _bulk(db, FoodUnit, [{"food_id": food_id[r["name_norm"]], "position": i, "name": clip(u.get("n"), 40),
                          "grams": num(u.get("g"))}
                         for c, r in foods for i, u in enumerate((c.get("units") or [])[:4])])
    db.commit() if commit else db.flush()


# ------------------------------------------------------------------ workouts document
def read_workouts(db: Session, uid: int) -> dict:
    p = db.get(Profile, uid)
    live = (Workout.user_id == uid, Workout.deleted_at.is_(None))
    workouts = db.scalars(select(Workout).where(*live).order_by(Workout.date.desc(), Workout.id.desc())).all()
    # Two more queries fetch every exercise and every set, instead of one query per workout/exercise.
    exs_by_workout: dict[int, list] = {}
    for e in db.scalars(select(WorkoutExercise).join(Workout, Workout.id == WorkoutExercise.workout_id)
                        .where(*live).order_by(WorkoutExercise.workout_id, WorkoutExercise.position)):
        exs_by_workout.setdefault(e.workout_id, []).append(e)
    sets_by_ex: dict[int, list] = {}
    for s in db.scalars(select(WorkoutSet).join(WorkoutExercise, WorkoutExercise.id == WorkoutSet.workout_exercise_id)
                        .join(Workout, Workout.id == WorkoutExercise.workout_id)
                        .where(*live).order_by(WorkoutSet.workout_exercise_id, WorkoutSet.position)):
        row = {k: v for k, v in (("w", s.weight), ("r", s.reps), ("d", s.duration), ("k", s.distance_km))
               if v is not None}
        if s.kind and s.kind != "n":
            row["t"] = s.kind
        sets_by_ex.setdefault(s.workout_exercise_id, []).append(row)
    out = [{"id": w.client_id, "date": w.date.isoformat(), "name": w.name, "dur": w.duration_min, "kcal": w.kcal,
            "bw": w.body_weight_kg,
            "ex": [{"id": e.exercise_slug, "sets": sets_by_ex.get(e.id, [])} for e in exs_by_workout.get(w.id, [])]}
           for w in workouts]
    custom = [{"id": c.slug, "n": c.name, "t": c.type, "met": c.met,
               "P": [m for m in c.primary_muscles.split(",") if m],
               "S": [m for m in c.secondary_muscles.split(",") if m]}
              for c in db.scalars(select(CustomExercise).where(CustomExercise.user_id == uid)).all()]
    return {"workouts": out, "custom": custom, "updated": p.workouts_updated if p else 0,
            "bw": p.body_weight_kg if p else 0}


def write_workouts(db: Session, uid: int, doc: dict, commit: bool = True) -> None:
    p = get_or_create_profile(db, uid)
    p.body_weight_kg = num(doc.get("bw"))
    p.workouts_updated = int(num(doc.get("updated"), 0))
    db.execute(delete(Workout).where(Workout.user_id == uid))          # sets cascade
    db.execute(delete(CustomExercise).where(CustomExercise.user_id == uid))
    ts, used = now_ms(), set()
    for c in doc.get("custom") or []:
        slug = clip(c.get("id"), 40)
        if not slug or slug in used:
            continue
        used.add(slug)
        db.add(CustomExercise(user_id=uid, slug=slug, name=clip(c.get("n"), 120), type=clip(c.get("t") or "wr", 4),
                              met=num(c.get("met"), 6), primary_muscles=",".join(map(str, c.get("P") or []))[:60],
                              secondary_muscles=",".join(map(str, c.get("S") or []))[:120]))
    ids, rows = set(), []
    for i, w in enumerate(doc.get("workouts") or []):
        d = parse_date(w.get("date"))
        cid = clip(w.get("id") or f"w{ts}{i}", 40)
        if not d or cid in ids:
            continue
        ids.add(cid)
        rows.append((w, {"user_id": uid, "client_id": cid, "date": d, "name": clip(w.get("name"), 120),
                         "duration_min": num(w.get("dur")), "kcal": num(w.get("kcal")),
                         "body_weight_kg": num(w.get("bw")), "version": 1, "updated_at": ts, "deleted_at": None}))
    _bulk(db, Workout, [r for _, r in rows])                                    # 1 statement
    wid = {c: i for i, c in db.execute(select(Workout.id, Workout.client_id).where(Workout.user_id == uid))}
    exercises = [(e, {"workout_id": wid[r["client_id"]], "position": pos, "exercise_slug": clip(e.get("id"), 40)})
                 for w, r in rows for pos, e in enumerate(w.get("ex") or [])]
    _bulk(db, WorkoutExercise, [r for _, r in exercises])                       # 1 statement
    xid = {(w_id, pos): i for i, w_id, pos in db.execute(
        select(WorkoutExercise.id, WorkoutExercise.workout_id, WorkoutExercise.position)
        .join(Workout, Workout.id == WorkoutExercise.workout_id).where(Workout.user_id == uid))}
    _bulk(db, WorkoutSet, [                                                      # 1 statement
        {"workout_exercise_id": xid[(r["workout_id"], r["position"])], "position": j,
         "kind": s.get("t") if s.get("t") in ("w", "f", "d") else "n", "weight": opt_num(s.get("w")),
         "reps": opt_num(s.get("r")), "duration": opt_num(s.get("d")), "distance_km": opt_num(s.get("k"))}
        for e, r in exercises for j, s in enumerate(e.get("sets") or [])])
    db.commit() if commit else db.flush()
