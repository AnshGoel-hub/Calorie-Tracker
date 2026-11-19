import json
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.db import get_session
from app.core.security import check_pw, current_user, hash_pw, set_session
from app.models import LegacyDoc, Recipe, Usage, User
from app.schemas import PasswordChange, PasswordOnly
from app.services import legacy, recipes

router = APIRouter(prefix="/api/account", tags=["account"])


def verify_password(request: Request, user: User, password: str) -> None:
    s, limiter = request.app.state.settings, request.app.state.limiter
    key = f"acct:{user.id}"
    if limiter.count(key, s.login_window_s) >= s.login_attempts:
        raise HTTPException(429, "Too many attempts. Try again in a few minutes.")
    if not check_pw(password, user.pw_hash):
        limiter.incr(key, s.login_window_s)
        raise HTTPException(403, "Wrong password")


@router.post("/password")
def change_password(p: PasswordChange, request: Request, response: Response,
                    user: User = Depends(current_user), db: Session = Depends(get_session)):
    verify_password(request, user, p.current)
    if len(p.new) < 8:
        raise HTTPException(400, "New password must be at least 8 characters")
    user.pw_hash = hash_pw(p.new)
    db.commit()
    set_session(response, request.app.state.settings, user.id, user.pw_hash)  # this device stays signed in
    return {"status": "ok"}


@router.get("/export")
def export_data(user: User = Depends(current_user), db: Session = Depends(get_session)):
    mine = db.scalars(select(Recipe).where(Recipe.owner_id == user.id).order_by(Recipe.id)).all()
    doc = {"email": user.email, "exported": datetime.now(UTC).isoformat(),
           "tracker": legacy.read_tracker(db, user.id), "workouts": legacy.read_workouts(db, user.id),
           "recipes": [recipes.to_out(r).model_dump() for r in mine]}
    return Response(json.dumps(doc, indent=1), media_type="application/json",
                    headers={"Content-Disposition": 'attachment; filename="calorie-tracker-export.json"'})


@router.post("/delete")
def delete_account(p: PasswordOnly, request: Request, response: Response,
                   user: User = Depends(current_user), db: Session = Depends(get_session)):
    verify_password(request, user, p.password)
    db.execute(delete(Usage).where(Usage.user_id == user.id))
    db.execute(delete(LegacyDoc).where(LegacyDoc.user_id == user.id))
    db.delete(user)  # every other table cascades from users.id
    db.commit()
    response.delete_cookie("session", path="/")
    return {"status": "deleted"}