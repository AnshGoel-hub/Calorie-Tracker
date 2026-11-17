import json

import pytest
from fastapi.testclient import TestClient

from app.core import db as database
from app.core.config import Settings
from app.main import create_app
from app.models import Base

GOOD = {"kcal": 120, "protein": 4, "carbs": 20, "fat": 2.5,
        "units": [{"name": "small bowl", "grams": 100}, {"name": "large bowl", "grams": 220}]}


class FakeGemini:
    """Stands in for the Gemini call; records how many times it was used."""

    def __init__(self, replies=None):
        self.replies, self.calls, self.prompts = list(replies or [GOOD]), 0, []

    def __call__(self, settings, prompt):
        self.calls += 1
        self.prompts.append(prompt)
        r = self.replies[min(self.calls - 1, len(self.replies) - 1)]
        return json.loads(json.dumps(r))


@pytest.fixture()
def settings(tmp_path):
    (tmp_path / "frontend").mkdir()
    (tmp_path / "frontend" / "login.html").write_text("<html>login</html>")
    return Settings(database_url=f"sqlite:///{tmp_path / 'test.db'}", jwt_secret="test-secret",
                    estimates_per_day=3, frontend_dir=tmp_path / "frontend")


@pytest.fixture()
def app(settings):
    a = create_app(settings)
    Base.metadata.create_all(database.engine)
    a.state.fetcher = FakeGemini()
    yield a
    database.engine.dispose()


@pytest.fixture()
def client(app):
    return TestClient(app)


def signup(client, email="a@example.com", pw="password123"):
    r = client.post("/api/signup", json={"email": email, "password": pw})
    assert r.status_code == 200, r.text
    return r.json()


@pytest.fixture()
def user(client):
    return signup(client)


def tracker_doc(**over):
    doc = {
        "log": {"2026-11-10": {"t": 2000, "w": 3, "wt": 70.5, "e": [
            {"n": "Dal", "l": "1 × medium bowl", "g": 150, "k": 157.5, "p": 9.7, "c": 21, "f": 3.7, "m": "Lunch"},
            {"n": "Roti", "l": "2 × piece", "g": 60, "k": 178, "p": 5.9, "c": 27.6, "f": 4.5, "m": "Dinner"}]},
                "2026-11-11": {"t": 2000, "w": 0, "wt": None, "e": [
                    {"n": "Banana", "l": "1 × piece", "g": 110, "k": 98, "p": 1.2, "c": 25, "f": .3, "m": "Snacks"}]}},
        "custom": [{"n": "Homemade laddoo", "k": 420, "p": 8, "c": 55, "f": 18, "units": [{"n": "piece", "g": 40}]},
                   {"n": "Egg bhurji", "k": 180, "p": 12, "c": 3, "f": 13, "est": True, "kind": "cooked",
                    "units": [{"n": "small bowl", "g": 80}, {"n": "medium bowl", "g": 130}]}],
        "target": 2100, "updated": 1760000000000, "setup": True,
        "profile": {"age": 21, "sex": "male", "height": 175, "weight": 70.5, "activity": "light", "goal": "maintain"},
        "marks": {"2026-11-12": {"t": "sick", "n": "fever"}, "2026-11-10": {"t": "rest", "n": ""}},
        "goals": {"weekly": 4}}
    doc.update(over)
    return doc


def workouts_doc():
    return {"workouts": [
        {"id": "abc1", "date": "2026-11-10", "name": "Push", "dur": 60, "kcal": 310, "bw": 70, "ex": [
            {"id": "bp", "sets": [{"w": 40, "r": 10, "t": "w"}, {"w": 60, "r": 8}, {"w": 60, "r": 7, "t": "f"}]},
            {"id": "tm", "sets": [{"d": 10, "k": 1.2}]}]},
        {"id": "abc2", "date": "2026-11-12", "name": "", "dur": 0, "kcal": 90, "bw": 70, "ex": [
            {"id": "c1x", "sets": [{"r": 12}]}]}],
        "custom": [{"id": "c1x", "n": "Cable woodchop", "t": "br", "met": 6, "P": ["ab"], "S": ["sh", "gl"],
                    "sub": ["ab_up", "obl"]}],
        "updated": 1760000001000, "bw": 70}
