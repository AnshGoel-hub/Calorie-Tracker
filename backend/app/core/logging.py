"""JSON logs with a request id, so one request can be followed across log lines."""
import contextvars
import json
import logging
import time
import uuid

request_id: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        out = {"ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"), "level": record.levelname,
               "logger": record.name, "msg": record.getMessage(), "request_id": request_id.get()}
        out.update(getattr(record, "extra_fields", {}))
        if record.exc_info:
            out["exc"] = self.formatException(record.exc_info)
        return json.dumps(out)


def setup_logging(level: str = "INFO") -> None:
    h = logging.StreamHandler()
    h.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [h]
    root.setLevel(level)


access = logging.getLogger("access")


async def request_context(request, call_next):
    rid = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
    token = request_id.set(rid)
    start = time.perf_counter()
    try:
        response = await call_next(request)
        response.headers["X-Request-ID"] = rid
        if request.url.path != "/healthz":
            access.info("request", extra={"extra_fields": {
                "method": request.method, "path": request.url.path, "status": response.status_code,
                "ms": round((time.perf_counter() - start) * 1000, 1)}})
        return response
    finally:
        request_id.reset(token)
