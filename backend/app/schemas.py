from typing import Any

from pydantic import BaseModel, Field


class Credentials(BaseModel):
    email: str = Field(max_length=255)
    password: str = Field(max_length=200)
    invite: str = Field(default="", max_length=100)


class PasswordChange(BaseModel):
    current: str = Field(max_length=200)
    new: str = Field(max_length=200)


class PasswordOnly(BaseModel):
    password: str = Field(max_length=200)


class TrackerData(BaseModel):
    log: dict[str, Any]
    custom: list[dict[str, Any]]
    target: float
    updated: int = 0
    setup: bool = False
    profile: dict[str, Any] = {}
    marks: dict[str, Any] = {}
    goals: dict[str, Any] = {}


class WorkoutData(BaseModel):
    workouts: list[dict[str, Any]]
    custom: list[dict[str, Any]] = []
    updated: int = 0
    bw: float = 0


class EstimateIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    kind: str = Field(default="cooked", max_length=20)
    ingredients: str = Field(default="", max_length=800)


class EntryIn(BaseModel):
    date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    meal: str = Field(default="Snacks", max_length=20)
    name: str = Field(min_length=1, max_length=200)
    label: str = Field(default="", max_length=200)
    grams: float = Field(ge=0, le=20000)
    kcal: float = Field(ge=0, le=20000)
    protein: float = Field(default=0, ge=0, le=5000)
    carbs: float = Field(default=0, ge=0, le=5000)
    fat: float = Field(default=0, ge=0, le=5000)


class EntryUpdate(EntryIn):
    version: int = Field(ge=1)  # the version the client last saw: optimistic concurrency


class EntryOut(BaseModel):
    id: int
    date: str
    meal: str
    name: str
    label: str
    grams: float
    kcal: float
    protein: float
    carbs: float
    fat: float
    version: int
    updated_at: int
    deleted: bool = False


class TargetApply(BaseModel):
    target: int | None = Field(default=None, ge=800, le=10000)
