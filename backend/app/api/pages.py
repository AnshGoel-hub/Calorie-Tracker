"""Serves the static frontend. Page routes are explicit so unknown paths 404 cleanly."""
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse
from sqlalchemy import text

from app.core import db as database

router = APIRouter()

PAGES = {"/": "index.html", "/login": "login.html", "/account": "account.html", "/calendar": "calendar.html",
         "/progress": "progress.html", "/achievements": "achievements.html", "/workouts": "workouts.html"}
ASSETS = {"/nav.js": ("nav.js", "application/javascript"), "/ui.css": ("ui.css", "text/css"),
          "/anatomy.js": ("anatomy.js", "application/javascript"), "/goals.js": ("goals.js", "application/javascript"),
          "/manifest.webmanifest": ("static/manifest.webmanifest", "application/manifest+json"),
          "/icon-192.png": ("static/icon-192.png", None), "/icon-512.png": ("static/icon-512.png", None),
          "/apple-touch-icon.png": ("static/apple-touch-icon.png", None)}


def _serve(request: Request, rel: str, media_type=None):
    f = request.app.state.settings.frontend_dir / rel
    if not f.is_file():
        raise HTTPException(404, "Not found")
    return FileResponse(f, media_type=media_type)


def _page(rel):
    def handler(request: Request):  # the annotation is what makes FastAPI inject the request
        return _serve(request, rel)
    return handler


def _asset(rel, mt):
    def handler(request: Request):
        return _serve(request, rel, mt)
    return handler


for path, rel in PAGES.items():
    router.add_api_route(path, _page(rel), methods=["GET"], include_in_schema=False)
for path, (rel, mt) in ASSETS.items():
    router.add_api_route(path, _asset(rel, mt), methods=["GET"], include_in_schema=False)


@router.get("/healthz", include_in_schema=False)
def healthz():
    with database.engine.connect() as c:
        c.execute(text("select 1"))
    return {"ok": True}
