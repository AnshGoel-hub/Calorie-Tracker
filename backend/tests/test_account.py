from sqlalchemy import func, select

from app.core import db as database
from app.models import DayLog, Food, FoodEntry, FoodUnit, Profile, User, Workout, WorkoutSet
from tests.conftest import tracker_doc, workouts_doc


def test_export_contains_everything(client, user):
    client.post("/api/data", json=tracker_doc())
    client.post("/api/workouts", json=workouts_doc())
    r = client.get("/api/account/export")
    assert r.status_code == 200 and "attachment" in r.headers["content-disposition"]
    body = r.json()
    assert body["email"] == "a@example.com" and len(body["workouts"]["workouts"]) == 2
    assert body["tracker"]["log"]["2026-11-10"]["e"][0]["n"] == "Dal"


def test_delete_account_removes_all_rows(client, user):
    client.post("/api/data", json=tracker_doc())
    client.post("/api/workouts", json=workouts_doc())
    assert client.post("/api/account/delete", json={"password": "wrong-password"}).status_code == 403
    assert client.post("/api/account/delete", json={"password": "password123"}).status_code == 200
    with database.SessionLocal() as db:
        for model in (User, Profile, FoodEntry, DayLog, Food, FoodUnit, Workout, WorkoutSet):
            assert db.scalar(select(func.count()).select_from(model)) == 0, model.__name__
    assert client.get("/api/me").status_code == 401


def test_health_and_pages(client):
    assert client.get("/healthz").json() == {"ok": True}
    assert client.get("/login").status_code == 200
    assert client.get("/nope").status_code == 404
    assert client.get("/workouts").status_code == 404      # page missing from the temp frontend dir
    h = client.get("/healthz").headers
    assert h["x-content-type-options"] == "nosniff" and h["x-frame-options"] == "DENY" and "x-request-id" in h


def test_request_id_is_echoed_and_logged(client, caplog):
    import logging
    with caplog.at_level(logging.INFO, logger="access"):
        r = client.get("/api/me", headers={"X-Request-ID": "trace-123"})
    assert r.headers["x-request-id"] == "trace-123"
    assert any(rec.extra_fields["status"] == 401 for rec in caplog.records if rec.name == "access")
