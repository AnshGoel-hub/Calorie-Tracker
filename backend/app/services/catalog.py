"""The built-in food catalogue, loaded once from app/data/foods.json. Values are per 100 g; `raw: true` marks
uncooked ingredients meant for the recipe builder."""
import hashlib
import json
from functools import lru_cache
from pathlib import Path

FILE = Path(__file__).resolve().parents[1] / "data" / "foods.json"


@lru_cache(maxsize=1)
def load() -> dict:
    raw = FILE.read_bytes()
    return {"version": hashlib.sha256(raw).hexdigest()[:12], "foods": json.loads(raw)}