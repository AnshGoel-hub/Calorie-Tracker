import json
import os
import urllib.request
import urllib.error
from pathlib import Path
from typing import Any, Dict, List

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:8000", "http://localhost:8000"],  # same-origin only: the API holds your Gemini key
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = Path(__file__).parent
DATA_FILE = str(BASE_DIR / "tracker_data.json")


def _load_env():
    """Tiny .env loader so the key can live in a git-ignored file."""
    f = BASE_DIR / ".env"
    if f.exists():
        for line in f.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip("\"'"))


_load_env()

# Set GEMINI_API_KEY in your environment to keep the key out of the browser.
# Override GEMINI_MODEL if you want a different model.
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash")


class TrackerData(BaseModel):
    log: Dict[str, Any]
    custom: List[Dict[str, Any]]
    target: int
    updated: int = 0  # ms timestamp, lets the frontend pick the newest copy


class EstimateRequest(BaseModel):
    prompt: str = Field(max_length=2000)


def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return {"log": {}, "custom": [], "target": 2000, "updated": 0}


def save_data(data: dict):
    # Atomic write: a crash mid-write can't corrupt the real file.
    tmp = DATA_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f)
    os.replace(tmp, DATA_FILE)


@app.get("/api/data")
def get_data():
    return load_data()


@app.post("/api/data")
def update_data(data: TrackerData):
    save_data(data.model_dump() if hasattr(data, "model_dump") else data.dict())
    return {"status": "success"}


@app.post("/api/estimate")
def estimate(req: EstimateRequest):
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        raise HTTPException(status_code=503, detail="GEMINI_API_KEY is not set on the server")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"
    body = json.dumps({
        "contents": [{"parts": [{"text": req.prompt}]}],
        "generationConfig": {"responseMimeType": "application/json"},
    }).encode()
    request = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json", "x-goog-api-key": key},
    )
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


@app.get("/")
def index():
    return FileResponse(BASE_DIR / "index.html")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
