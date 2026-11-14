"""Relational schema. Rows that sync between devices carry `version`, `updated_at` (epoch ms)
and, where deletes must propagate, a `deleted_at` tombstone."""
from datetime import date

from sqlalchemy import BigInteger, Boolean, Date, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base

CASCADE = {"ondelete": "CASCADE"}


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    pw_hash: Mapped[str] = mapped_column(String(100))
    created: Mapped[int] = mapped_column(BigInteger)  # epoch seconds


class Profile(Base):
    __tablename__ = "profiles"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", **CASCADE), primary_key=True)
    age: Mapped[float | None] = mapped_column(Float)
    sex: Mapped[str | None] = mapped_column(String(10))
    height_cm: Mapped[float | None] = mapped_column(Float)
    weight_kg: Mapped[float | None] = mapped_column(Float)
    activity: Mapped[str | None] = mapped_column(String(20))
    goal: Mapped[str | None] = mapped_column(String(20))
    target_kcal: Mapped[float] = mapped_column(Float, default=2000)
    weekly_workout_goal: Mapped[int] = mapped_column(Integer, default=3)
    setup_done: Mapped[bool] = mapped_column(Boolean, default=False)
    body_weight_kg: Mapped[float] = mapped_column(Float, default=0)  # last body weight used by the workouts page
    tracker_updated: Mapped[int] = mapped_column(BigInteger, default=0)
    workouts_updated: Mapped[int] = mapped_column(BigInteger, default=0)


class Food(Base):
    """A user's own food (typed in, or estimated by Gemini). Values are per 100 g."""
    __tablename__ = "foods"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", **CASCADE), index=True)
    name: Mapped[str] = mapped_column(String(200))
    name_norm: Mapped[str] = mapped_column(String(200))
    kcal: Mapped[float] = mapped_column(Float)
    protein: Mapped[float] = mapped_column(Float, default=0)
    carbs: Mapped[float] = mapped_column(Float, default=0)
    fat: Mapped[float] = mapped_column(Float, default=0)
    source: Mapped[str] = mapped_column(String(10), default="user")  # user | ai
    kind: Mapped[str | None] = mapped_column(String(20))
    __table_args__ = (UniqueConstraint("owner_id", "name_norm", name="uq_food_owner_name"),)


class FoodUnit(Base):
    __tablename__ = "food_units"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    food_id: Mapped[int] = mapped_column(ForeignKey("foods.id", **CASCADE), index=True)
    position: Mapped[int] = mapped_column(Integer, default=0)
    name: Mapped[str] = mapped_column(String(40))
    grams: Mapped[float] = mapped_column(Float)


class FoodEntry(Base):
    __tablename__ = "food_entries"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", **CASCADE))
    date: Mapped[date] = mapped_column(Date)
    meal: Mapped[str] = mapped_column(String(20), default="Snacks")
    position: Mapped[int] = mapped_column(Integer, default=0)
    name: Mapped[str] = mapped_column(String(200))
    label: Mapped[str] = mapped_column(String(200), default="")
    grams: Mapped[float] = mapped_column(Float, default=0)
    kcal: Mapped[float] = mapped_column(Float, default=0)
    protein: Mapped[float] = mapped_column(Float, default=0)
    carbs: Mapped[float] = mapped_column(Float, default=0)
    fat: Mapped[float] = mapped_column(Float, default=0)
    version: Mapped[int] = mapped_column(Integer, default=1)
    updated_at: Mapped[int] = mapped_column(BigInteger, default=0)
    deleted_at: Mapped[int | None] = mapped_column(BigInteger)
    __table_args__ = (Index("ix_entries_user_date", "user_id", "date"),
                      Index("ix_entries_user_updated", "user_id", "updated_at"))


class DayLog(Base):
    """Per-day facts that are not food entries: target, water, weight and the calendar marker."""
    __tablename__ = "day_logs"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", **CASCADE), primary_key=True)
    date: Mapped[date] = mapped_column(Date, primary_key=True)
    target_kcal: Mapped[float] = mapped_column(Float, default=2000)
    water: Mapped[int] = mapped_column(Integer, default=0)
    weight_kg: Mapped[float | None] = mapped_column(Float)
    marker_type: Mapped[str | None] = mapped_column(String(10))
    marker_note: Mapped[str | None] = mapped_column(String(60))
    version: Mapped[int] = mapped_column(Integer, default=1)
    updated_at: Mapped[int] = mapped_column(BigInteger, default=0)
    __table_args__ = (Index("ix_daylogs_user_updated", "user_id", "updated_at"),)


class CustomExercise(Base):
    """Exercises a user created. Built-in exercises live in the client catalogue and are referenced by slug."""
    __tablename__ = "custom_exercises"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", **CASCADE), primary_key=True)
    slug: Mapped[str] = mapped_column(String(40), primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    type: Mapped[str] = mapped_column(String(4))  # wr | br | dur | dd
    met: Mapped[float] = mapped_column(Float, default=6)
    primary_muscles: Mapped[str] = mapped_column(String(60), default="")    # comma-separated codes
    secondary_muscles: Mapped[str] = mapped_column(String(120), default="")


class Workout(Base):
    __tablename__ = "workouts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", **CASCADE))
    client_id: Mapped[str] = mapped_column(String(40))
    date: Mapped[date] = mapped_column(Date)
    name: Mapped[str] = mapped_column(String(120), default="")
    duration_min: Mapped[float] = mapped_column(Float, default=0)
    kcal: Mapped[float] = mapped_column(Float, default=0)
    body_weight_kg: Mapped[float] = mapped_column(Float, default=0)
    version: Mapped[int] = mapped_column(Integer, default=1)
    updated_at: Mapped[int] = mapped_column(BigInteger, default=0)
    deleted_at: Mapped[int | None] = mapped_column(BigInteger)
    __table_args__ = (UniqueConstraint("user_id", "client_id", name="uq_workout_client"),
                      Index("ix_workouts_user_date", "user_id", "date"))


class WorkoutExercise(Base):
    __tablename__ = "workout_exercises"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workout_id: Mapped[int] = mapped_column(ForeignKey("workouts.id", **CASCADE), index=True)
    position: Mapped[int] = mapped_column(Integer, default=0)
    exercise_slug: Mapped[str] = mapped_column(String(40))


class WorkoutSet(Base):
    __tablename__ = "workout_sets"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workout_exercise_id: Mapped[int] = mapped_column(ForeignKey("workout_exercises.id", **CASCADE), index=True)
    position: Mapped[int] = mapped_column(Integer, default=0)
    kind: Mapped[str] = mapped_column(String(1), default="n")  # n normal, w warm-up, f failure, d drop
    weight: Mapped[float | None] = mapped_column(Float)
    reps: Mapped[float | None] = mapped_column(Float)
    duration: Mapped[float | None] = mapped_column(Float)     # seconds for timed moves, minutes for cardio
    distance_km: Mapped[float | None] = mapped_column(Float)


class EstimateCache(Base):
    """Shared Gemini results. `hits` counts reuse, so hit rate = hits / (hits + rows)."""
    __tablename__ = "estimate_cache"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(64), unique=True)
    name_norm: Mapped[str] = mapped_column(String(200))
    kind: Mapped[str] = mapped_column(String(20))
    payload: Mapped[str] = mapped_column(Text)
    hits: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[int] = mapped_column(BigInteger, default=0)


class Usage(Base):
    __tablename__ = "usage"
    user_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    day: Mapped[date] = mapped_column(Date, primary_key=True)
    n: Mapped[int] = mapped_column(Integer, default=0)


class LegacyDoc(Base):
    """The old one-JSON-blob-per-user table. Kept only so scripts/import_legacy.py can migrate it."""
    __tablename__ = "user_data"
    user_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kind: Mapped[str] = mapped_column(String(20), primary_key=True)
    body: Mapped[str] = mapped_column(Text)
    updated: Mapped[int] = mapped_column(BigInteger, default=0)
