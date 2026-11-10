import json
import os
import re
import time
import urllib.error
import urllib.request
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import bcrypt
import jwt
from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import (BigInteger, Column, Date, Integer, MetaData, String, Table,
                        Text, create_engine, select, text)
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

BASE_DIR = Path(__file__).parent


def _load_env():
    """Tiny .env loader so secrets can live in a git-ignored file locally."""
    f = BASE_DIR / ".env"
    if f.exists():
        for line in f.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip("\"'"))


_load_env()

GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash")
INVITE_CODE = os.environ.get("INVITE_CODE", "")          # required at signup when set
ESTIMATES_PER_DAY = int(os.environ.get("ESTIMATES_PER_DAY", "30"))
SECURE_COOKIE = os.environ.get("COOKIE_SECURE", "0") == "1"  # set to 1 on https hosting
JWT_DAYS = 30
MAX_PAYLOAD = 2_000_000  # bytes of JSON per user per blob

JWT_SECRET = os.environ.get("JWT_SECRET")
if not JWT_SECRET:
    # Dev only: a random secret means logins reset on every restart.
    JWT_SECRET = os.urandom(32).hex()
    print("[auth] JWT_SECRET not set, using a temporary one (fine locally, not for deployment)")

# ---------------------------------------------------------------- database
DB_URL = os.environ.get("DATABASE_URL", "")
if DB_URL.startswith("postgres://"):
    DB_URL = "postgresql://" + DB_URL[len("postgres://"):]
if DB_URL.startswith("postgresql://"):
    DB_URL = "postgresql+psycopg://" + DB_URL[len("postgresql://"):]
if not DB_URL:
    DB_URL = f"sqlite:///{BASE_DIR / 'local.db'}"  # local development fallback
IS_PG = DB_URL.startswith("postgresql")

engine = create_engine(DB_URL, pool_pre_ping=True, future=True)
meta = MetaData()
users = Table(
    "users", meta,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("email", String(255), unique=True, nullable=False),
    Column("pw_hash", String(100), nullable=False),
    Column("created", BigInteger, nullable=False),
)
# One JSON document per user per kind ("tracker" or "workouts").
user_data = Table(
    "user_data", meta,
    Column("user_id", Integer, primary_key=True),
    Column("kind", String(20), primary_key=True),
    Column("body", Text, nullable=False),
    Column("updated", BigInteger, nullable=False, default=0),
)
usage = Table(
    "usage", meta,
    Column("user_id", Integer, primary_key=True),
    Column("day", Date, primary_key=True),
    Column("n", Integer, nullable=False, default=0),
)
meta.create_all(engine)


def upsert(table, values: dict, keys: list, update: dict):
    ins = (pg_insert if IS_PG else sqlite_insert)(table).values(**values)
    return ins.on_conflict_do_update(index_elements=keys, set_=update)


# ---------------------------------------------------------------- auth
app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
fails: Dict[str, List[float]] = defaultdict(list)  # in-memory login throttle


def hash_pw(pw: str) -> str:
    return bcrypt.hashpw(pw.encode()[:72], bcrypt.gensalt()).decode()


def check_pw(pw: str, h: str) -> bool:
    try:
        return bcrypt.checkpw(pw.encode()[:72], h.encode())
    except ValueError:
        return False


def set_session(resp: Response, uid: int):
    exp = datetime.now(timezone.utc) + timedelta(days=JWT_DAYS)
    token = jwt.encode({"sub": str(uid), "exp": exp}, JWT_SECRET, algorithm="HS256")
    resp.set_cookie("session", token, max_age=JWT_DAYS * 86400, httponly=True,
                    samesite="lax", secure=SECURE_COOKIE, path="/")


def current_user(request: Request) -> dict:
    token = request.cookies.get("session")
    if not token:
        raise HTTPException(401, "Not logged in")
    try:
        uid = int(jwt.decode(token, JWT_SECRET, algorithms=["HS256"])["sub"])
    except Exception:
        raise HTTPException(401, "Session expired")
    with engine.connect() as c:
        row = c.execute(select(users.c.id, users.c.email).where(users.c.id == uid)).first()
    if not row:
        raise HTTPException(401, "Account not found")
    return {"id": row.id, "email": row.email}


class Credentials(BaseModel):
    email: str = Field(max_length=255)
    password: str = Field(max_length=200)
    invite: str = Field(default="", max_length=100)


@app.post("/api/signup")
def signup(c: Credentials, response: Response):
    email = c.email.strip().lower()
    if INVITE_CODE and c.invite.strip() != INVITE_CODE:
        raise HTTPException(403, "Wrong invite code")
    if not EMAIL_RE.match(email):
        raise HTTPException(400, "Enter a valid email address")
    if len(c.password) < 8:
        raise HTTPException(400, "Password must be at least 8 characters")
    with engine.begin() as conn:
        if conn.execute(select(users.c.id).where(users.c.email == email)).first():
            raise HTTPException(409, "That email is already registered")
        uid = conn.execute(users.insert().values(
            email=email, pw_hash=hash_pw(c.password), created=int(time.time()))).inserted_primary_key[0]
    set_session(response, uid)
    return {"id": uid, "email": email}


@app.post("/api/login")
def login(c: Credentials, request: Request, response: Response):
    email = c.email.strip().lower()
    key = email + "|" + (request.client.host if request.client else "")
    now = time.time()
    fails[key] = [t for t in fails[key] if now - t < 900]
    if len(fails[key]) >= 8:
        raise HTTPException(429, "Too many attempts. Try again in a few minutes.")
    with engine.connect() as conn:
        row = conn.execute(select(users).where(users.c.email == email)).first()
    if not row or not check_pw(c.password, row.pw_hash):
        fails[key].append(now)
        raise HTTPException(401, "Wrong email or password")
    fails.pop(key, None)
    set_session(response, row.id)
    return {"id": row.id, "email": row.email}


@app.post("/api/logout")
def logout(response: Response):
    response.delete_cookie("session", path="/")
    return {"status": "ok"}


@app.get("/api/me")
def me(user: dict = Depends(current_user)):
    return user


# ---------------------------------------------------------------- user data
class TrackerData(BaseModel):
    log: Dict[str, Any]
    custom: List[Dict[str, Any]]
    target: float
    updated: int = 0


class WorkoutData(BaseModel):
    workouts: List[Dict[str, Any]]
    custom: List[Dict[str, Any]] = []
    updated: int = 0
    bw: float = 0


EMPTY = {
    "tracker": {"log": {}, "custom": [], "target": 2000, "updated": 0},
    "workouts": {"workouts": [], "custom": [], "updated": 0, "bw": 0},
}


def read_doc(uid: int, kind: str) -> dict:
    with engine.connect() as c:
        row = c.execute(select(user_data.c.body).where(
            (user_data.c.user_id == uid) & (user_data.c.kind == kind))).first()
    return json.loads(row.body) if row else EMPTY[kind]


def write_doc(uid: int, kind: str, doc: dict):
    body = json.dumps(doc)
    if len(body) > MAX_PAYLOAD:
        raise HTTPException(413, "Data too large")
    vals = {"user_id": uid, "kind": kind, "body": body, "updated": int(doc.get("updated", 0))}
    with engine.begin() as c:
        c.execute(upsert(user_data, vals, ["user_id", "kind"],
                         {"body": body, "updated": vals["updated"]}))


@app.get("/api/data")
def get_data(user: dict = Depends(current_user)):
    return read_doc(user["id"], "tracker")


@app.post("/api/data")
def update_data(data: TrackerData, user: dict = Depends(current_user)):
    write_doc(user["id"], "tracker", data.model_dump())
    return {"status": "success"}


@app.get("/api/workouts")
def get_workouts(user: dict = Depends(current_user)):
    return read_doc(user["id"], "workouts")


@app.post("/api/workouts")
def update_workouts(data: WorkoutData, user: dict = Depends(current_user)):
    write_doc(user["id"], "workouts", data.model_dump())
    return {"status": "success"}


# ---------------------------------------------------------------- Gemini
class EstimateRequest(BaseModel):
    prompt: str = Field(max_length=2000)


def take_quota(uid: int):
    today = date.today()
    with engine.begin() as c:
        row = c.execute(select(usage.c.n).where(
            (usage.c.user_id == uid) & (usage.c.day == today))).first()
        used = row.n if row else 0
        if used >= ESTIMATES_PER_DAY:
            raise HTTPException(429, f"Daily limit of {ESTIMATES_PER_DAY} estimates reached")
        c.execute(upsert(usage, {"user_id": uid, "day": today, "n": used + 1},
                         ["user_id", "day"], {"n": used + 1}))


@app.post("/api/estimate")
def estimate(req: EstimateRequest, user: dict = Depends(current_user)):
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        raise HTTPException(status_code=503, detail="GEMINI_API_KEY is not set on the server")
    take_quota(user["id"])
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"
    body = json.dumps({
        "contents": [{"parts": [{"text": req.prompt}]}],
        "generationConfig": {"responseMimeType": "application/json"},
    }).encode()
    request = urllib.request.Request(
        url, data=body, headers={"Content-Type": "application/json", "x-goog-api-key": key})
    try:
        with urllib.request.urlopen(request, timeout=30) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "ignore")
        try:
            msg = json.loads(raw)["error"]["message"]
        except Exception:
            msg = raw[:200]
        print(f"[estimate] Gemini returned {e.code} for model {GEMINI_MODEL}: {msg}")
        raise HTTPException(status_code=502, detail=f"Gemini error {e.code}: {msg[:160]}")
    except Exception as e:
        print(f"[estimate] Could not reach Gemini: {e!r}")
        raise HTTPException(status_code=502, detail=f"Could not reach Gemini ({type(e).__name__})")


@app.get("/healthz")
def healthz():
    with engine.connect() as c:
        c.execute(text("select 1"))
    return {"ok": True}


# ---------------------------------------------------------------- pages
STATIC = BASE_DIR / "static"


@app.get("/manifest.webmanifest")
def manifest():
    return FileResponse(STATIC / "manifest.webmanifest", media_type="application/manifest+json")


@app.get("/icon-192.png")
def icon192():
    return FileResponse(STATIC / "icon-192.png")


@app.get("/icon-512.png")
def icon512():
    return FileResponse(STATIC / "icon-512.png")


@app.get("/apple-touch-icon.png")
def apple_icon():
    return FileResponse(STATIC / "apple-touch-icon.png")


@app.get("/login")
def login_page():
    return FileResponse(BASE_DIR / "login.html")


@app.get("/workouts")
def workouts_page():
    return FileResponse(BASE_DIR / "workouts.html")


@app.get("/")
def index():
    return FileResponse(BASE_DIR / "index.html")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=int(os.environ.get("PORT", "8000")))
