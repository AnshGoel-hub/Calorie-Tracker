"""Snapshot endpoints the current frontend uses. Deprecated in favour of /api/v1."""
import json

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.db import get_session
from app.core.security import current_user
from app.models import User
from app.schemas import TrackerData, WorkoutData
from app.services import legacy

router = APIRouter(prefix="/api", tags=["legacy"])


def _check_size(request: Request, doc: dict) -> None:
    if len(json.dumps(doc)) > request.app.state.settings.max_payload:
        raise HTTPException(413, "Data too large")


@router.get("/data")
def get_data(user: User = Depends(current_user), db: Session = Depends(get_session)):
    return legacy.read_tracker(db, user.id)


@router.post("/data")
def post_data(data: TrackerData, request: Request, user: User = Depends(current_user),
              db: Session = Depends(get_session)):
    doc = data.model_dump()
    _check_size(request, doc)
    legacy.write_tracker(db, user.id, doc)
    return {"status": "success"}


@router.get("/workouts")
def get_workouts(user: User = Depends(current_user), db: Session = Depends(get_session)):
    return legacy.read_workouts(db, user.id)


@router.post("/workouts")
def post_workouts(data: WorkoutData, request: Request, user: User = Depends(current_user),
                  db: Session = Depends(get_session)):
    doc = data.model_dump()
    _check_size(request, doc)
    legacy.write_workouts(db, user.id, doc)
    return {"status": "success"}
