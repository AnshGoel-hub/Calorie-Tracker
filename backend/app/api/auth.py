import re
import secrets
import time

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_session
from app.core.security import check_pw, current_user, hash_pw, set_session
from app.models import User
from app.schemas import Credentials

router = APIRouter(prefix="/api", tags=["auth"])
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@router.post("/signup")
def signup(c: Credentials, request: Request, response: Response, db: Session = Depends(get_session)):
    s = request.app.state.settings
    email = c.email.strip().lower()
    if s.invite_code and not secrets.compare_digest(c.invite.strip(), s.invite_code):
        raise HTTPException(403, "Wrong invite code")
    if not EMAIL_RE.match(email):
        raise HTTPException(400, "Enter a valid email address")
    if len(c.password) < 8:
        raise HTTPException(400, "Password must be at least 8 characters")
    if db.scalar(select(User.id).where(User.email == email)):
        raise HTTPException(409, "That email is already registered")
    user = User(email=email, pw_hash=hash_pw(c.password), created=int(time.time()))
    db.add(user)
    db.commit()
    set_session(response, s, user.id, user.pw_hash)
    return {"id": user.id, "email": email}


@router.post("/login")
def login(c: Credentials, request: Request, response: Response, db: Session = Depends(get_session)):
    s, limiter = request.app.state.settings, request.app.state.limiter
    email = c.email.strip().lower()
    key = f"login:{email}|{request.client.host if request.client else ''}"
    if limiter.count(key, s.login_window_s) >= s.login_attempts:
        raise HTTPException(429, "Too many attempts. Try again in a few minutes.")
    user = db.scalar(select(User).where(User.email == email))
    if not user or not check_pw(c.password, user.pw_hash):
        limiter.incr(key, s.login_window_s)
        raise HTTPException(401, "Wrong email or password")
    limiter.reset(key)
    set_session(response, s, user.id, user.pw_hash)
    return {"id": user.id, "email": user.email}


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie("session", path="/")
    return {"status": "ok"}


@router.get("/me")
def me(user: User = Depends(current_user)):
    return {"id": user.id, "email": user.email}
