"""Password hashing, session cookies and the current-user dependency."""
import hashlib
from datetime import UTC, datetime, timedelta

import bcrypt
import jwt
from fastapi import Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_session
from app.models import User


def hash_pw(pw: str) -> str:
    return bcrypt.hashpw(pw.encode()[:72], bcrypt.gensalt()).decode()


def check_pw(pw: str, h: str) -> bool:
    try:
        return bcrypt.checkpw(pw.encode()[:72], h.encode())
    except ValueError:
        return False


def pw_fingerprint(pw_hash: str) -> str:
    """Embedded in the token: changing the password invalidates every older session."""
    return hashlib.sha256(pw_hash.encode()).hexdigest()[:12]


def set_session(resp: Response, settings, uid: int, pw_hash: str) -> None:
    exp = datetime.now(UTC) + timedelta(days=settings.jwt_days)
    token = jwt.encode({"sub": str(uid), "pv": pw_fingerprint(pw_hash), "exp": exp},
                       settings.jwt_secret, algorithm="HS256")
    resp.set_cookie("session", token, max_age=settings.jwt_days * 86400, httponly=True,
                    samesite="lax", secure=settings.cookie_secure, path="/")


def current_user(request: Request, db: Session = Depends(get_session)) -> User:
    token = request.cookies.get("session")
    if not token:
        raise HTTPException(401, "Not logged in")
    try:
        payload = jwt.decode(token, request.app.state.settings.jwt_secret, algorithms=["HS256"])
        uid = int(payload["sub"])
    except Exception:
        raise HTTPException(401, "Session expired") from None
    user = db.scalar(select(User).where(User.id == uid))
    if not user:
        raise HTTPException(401, "Account not found")
    if payload.get("pv") != pw_fingerprint(user.pw_hash):
        raise HTTPException(401, "Please sign in again")
    return user
