import io
import json
import urllib.error

import pytest

from app.core.config import Settings
from app.core.errors import ServiceError
from app.services import estimates

REPLY = {"candidates": [{"content": {"parts": [{"text": json.dumps({"ok": 1})}]}}]}


class Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def http_error(code):
    return urllib.error.HTTPError("u", code, "x", {}, io.BytesIO(b"{}"))


def make(script, monkeypatch):
    """script: one item per call, either an exception to raise or a reply dict. Returns the models called."""
    calls = []

    def fake_urlopen(req, timeout=0):
        calls.append(req.full_url.split("models/")[1].split(":")[0])
        item = script[min(len(calls) - 1, len(script) - 1)]
        if isinstance(item, Exception):
            raise item
        return Resp(json.dumps(item).encode())

    monkeypatch.setattr(estimates.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(estimates.time, "sleep", lambda s: None)
    return calls


def cfg(fallback=""):
    return Settings(gemini_api_key="k", gemini_model="main", gemini_fallback_model=fallback)


def test_success_on_first_try(monkeypatch):
    calls = make([REPLY], monkeypatch)
    assert estimates.call_gemini(cfg(), "p") == {"ok": 1} and calls == ["main"]


def test_overload_is_retried_on_the_same_model(monkeypatch):
    calls = make([http_error(503), REPLY], monkeypatch)
    assert estimates.call_gemini(cfg(), "p") == {"ok": 1} and calls == ["main", "main"]


def test_falls_back_when_the_main_model_stays_overloaded(monkeypatch):
    calls = make([http_error(503), http_error(503), REPLY], monkeypatch)
    assert estimates.call_gemini(cfg("backup"), "p") == {"ok": 1} and calls == ["main", "main", "backup"]


def test_retired_model_goes_straight_to_the_fallback(monkeypatch):
    calls = make([http_error(404), REPLY], monkeypatch)
    assert estimates.call_gemini(cfg("backup"), "p") == {"ok": 1} and calls == ["main", "backup"]


def test_timeouts_are_retried_then_reported(monkeypatch):
    calls = make([TimeoutError()], monkeypatch)
    with pytest.raises(ServiceError) as e:
        estimates.call_gemini(cfg(), "p")
    assert e.value.status == 502 and "TimeoutError" in e.value.detail and len(calls) == 2


def test_error_names_the_last_failure(monkeypatch):
    make([http_error(503)], monkeypatch)
    with pytest.raises(ServiceError) as e:
        estimates.call_gemini(cfg("backup"), "p")
    assert "503" in e.value.detail and "backup" in e.value.detail


def test_unreadable_reply_returns_empty_for_the_caller_to_reject(monkeypatch):
    make([{"candidates": []}], monkeypatch)
    assert estimates.call_gemini(cfg(), "p") == {}
