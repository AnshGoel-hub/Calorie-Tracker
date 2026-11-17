"""Settings, read once from the environment (and an optional git-ignored .env file)."""
import os
from dataclasses import dataclass, field
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[2]
REPO_DIR = BACKEND_DIR.parent


def _load_dotenv() -> None:
    f = BACKEND_DIR / ".env"
    if not f.exists():
        return
    for line in f.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip("\"'"))


def normalize_db_url(url: str) -> str:
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://"):]
    return url or f"sqlite:///{BACKEND_DIR / 'local.db'}"


@dataclass(frozen=True)
class Settings:
    database_url: str = ""
    jwt_secret: str = ""
    invite_code: str = ""
    cookie_secure: bool = False
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.8-flash"
    gemini_fallback_model: str = ""  # tried when the main model is overloaded or retired
    estimates_per_day: int = 30
    redis_url: str = ""
    jwt_days: int = 30
    max_payload: int = 2_000_000
    login_attempts: int = 8
    login_window_s: int = 900
    frontend_dir: Path = field(default_factory=lambda: REPO_DIR / "frontend")
    allowed_origins: tuple = ()  # extra origins besides the request's own host


def load_settings() -> Settings:
    _load_dotenv()
    env = os.environ.get
    secret = env("JWT_SECRET")
    if not secret:
        secret = os.urandom(32).hex()  # dev only: sessions reset on restart
    return Settings(
        database_url=normalize_db_url(env("DATABASE_URL", "")),
        jwt_secret=secret,
        invite_code=env("INVITE_CODE", ""),
        cookie_secure=env("COOKIE_SECURE", "0") == "1",
        gemini_api_key=env("GEMINI_API_KEY", ""),
        gemini_model=env("GEMINI_MODEL", "gemini-3.8-flash"),
        gemini_fallback_model=env("GEMINI_FALLBACK_MODEL", ""),
        estimates_per_day=int(env("ESTIMATES_PER_DAY", "30")),
        redis_url=env("REDIS_URL", ""),
        frontend_dir=Path(env("FRONTEND_DIR", str(REPO_DIR / "frontend"))),
        allowed_origins=tuple(o for o in env("ALLOWED_ORIGINS", "").split(",") if o),
    )
