import json
import subprocess
import sys
from pathlib import Path

from sqlalchemy import select

from app.core import db as database
from app.models import FoodEntry, LegacyDoc, User
from app.services.legacy_import import migrate_legacy
from tests.conftest import signup, tracker_doc, workouts_doc

BACKEND = Path(__file__).resolve().parents[1]


def _seed_legacy(uid, tracker=None, workouts=None):
    with database.SessionLocal() as db:
        db.add(LegacyDoc(user_id=uid, kind="tracker", body=json.dumps(tracker or tracker_doc()), updated=1))
        db.add(LegacyDoc(user_id=uid, kind="workouts", body=json.dumps(workouts or workouts_doc()), updated=1))
        db.commit()


def test_import_moves_blobs_into_tables_and_is_idempotent(client, user):
    _seed_legacy(user["id"])
    with database.SessionLocal() as db:
        rep = migrate_legacy(db)
        assert rep.migrated == ["a@example.com"] and not rep.failed
        assert migrate_legacy(db).skipped == [("a@example.com", "already migrated")]
        assert len(db.scalars(select(FoodEntry)).all()) == 3
    assert len(client.get("/api/workouts").json()["workouts"]) == 2


def test_dry_run_changes_nothing(client, user):
    _seed_legacy(user["id"])
    with database.SessionLocal() as db:
        assert migrate_legacy(db, dry_run=True).migrated
        assert db.scalars(select(FoodEntry)).all() == []


def test_one_bad_blob_does_not_block_other_users(app, client, user):
    from fastapi.testclient import TestClient
    other = TestClient(app)
    b = signup(other, "b@example.com")
    with database.SessionLocal() as db:
        db.add(LegacyDoc(user_id=user["id"], kind="tracker", body="{not json", updated=1))
        db.commit()
    _seed_legacy(b["id"])
    with database.SessionLocal() as db:
        rep = migrate_legacy(db)
        assert [e for e, _ in rep.failed] == ["a@example.com"] and rep.migrated == ["b@example.com"]


def test_users_without_legacy_data_are_skipped(client, user):
    with database.SessionLocal() as db:
        assert migrate_legacy(db).skipped == [("a@example.com", "no legacy data")]
        assert db.scalar(select(User.id)) == user["id"]


def test_admin_cli_lists_and_exports(settings, client, user, tmp_path):
    client.post("/api/data", json=tracker_doc())
    env = {"DATABASE_URL": settings.database_url, "ADMIN_DATABASE_URL": settings.database_url,
           "PATH": "/usr/bin:/bin", "NO_COLOR": "1"}
    run = lambda *a: subprocess.run([sys.executable, "scripts/admin.py", *a], cwd=BACKEND, env=env,  # noqa: E731
                                    capture_output=True, text=True)
    assert "a@example.com" in run("list").stdout
    assert "food entries  3" in run("show", "a@example.com").stdout
    out = tmp_path / "e.json"
    assert run("export", "a@example.com", "-o", str(out)).returncode == 0
    assert json.loads(out.read_text())["tracker"]["target"] == 2100
    assert run("show", "nobody@example.com").returncode == 1
