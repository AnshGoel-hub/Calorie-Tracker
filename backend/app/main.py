"""App factory. `uvicorn app.main:app` serves the API and the static frontend."""
import logging
from urllib.parse import urlparse

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api import account, auth, data, pages, v1
from app.core import db as database
from app.core.config import Settings, load_settings
from app.core.errors import ServiceError
from app.core.logging import request_context, setup_logging
from app.core.ratelimit import build_counter
from app.services.estimates import call_gemini

log = logging.getLogger("app")
UNSAFE = {"POST", "PUT", "PATCH", "DELETE"}


async def origin_guard(request: Request, call_next):
    """CSRF defence for cookie auth: a state-changing request from a browser must come from our own origin.
    (Requests with no Origin header are non-browser clients, which cannot ride on a victim's cookie.)"""
    if request.method in UNSAFE:
        origin = request.headers.get("origin")
        if origin:
            s = request.app.state.settings
            host = request.headers.get("host", "")
            if urlparse(origin).netloc != host and origin not in s.allowed_origins:
                return JSONResponse({"detail": "Cross-origin request blocked"}, status_code=403)
    return await call_next(request)


async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "same-origin")
    return response


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or load_settings()
    setup_logging()
    database.configure(settings.database_url)
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    app.state.settings = settings
    app.state.limiter = build_counter(settings.redis_url)
    app.state.fetcher = call_gemini  # swapped for a fake in tests

    # last added runs first: request id/logging wraps everything
    app.middleware("http")(security_headers)
    app.middleware("http")(origin_guard)
    app.middleware("http")(request_context)

    @app.exception_handler(ServiceError)
    async def service_error(_: Request, e: ServiceError):
        return JSONResponse({"detail": e.detail}, status_code=e.status)

    for r in (auth.router, data.router, account.router, v1.router, pages.router):
        app.include_router(r)
    return app


app = create_app()

if __name__ == "__main__":
    import os

    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=int(os.environ.get("PORT", "8000")))
