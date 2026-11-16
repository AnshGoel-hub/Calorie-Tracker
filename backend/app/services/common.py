import re
import time
from datetime import date

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def now_ms() -> int:
    return int(time.time() * 1000)


def norm_name(s: str) -> str:
    return re.sub(r"\s+", " ", str(s or "").strip().lower())[:200]


def num(x, default=0.0):
    try:
        v = float(x)
        return v if v == v and abs(v) < 1e15 else default
    except (TypeError, ValueError):
        return default


def opt_num(x):
    return None if x is None or x == "" else num(x, None)


def parse_date(s):
    if not isinstance(s, str) or not DATE_RE.match(s):
        return None
    try:
        return date.fromisoformat(s)
    except ValueError:
        return None


def clip(s, n):
    return str(s if s is not None else "")[:n]
