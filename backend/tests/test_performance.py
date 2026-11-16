"""Guards against N+1 queries. Each query is a network round trip to a remote database, so the number of
statements per request must not grow with the amount of data."""
import pytest
from sqlalchemy import event

from app.core import db as database


@pytest.fixture()
def counter():
    n = [0]

    def hit(*_):
        n[0] += 1
    event.listen(database.engine, "before_cursor_execute", hit)
    yield n
    event.remove(database.engine, "before_cursor_execute", hit)


def big_workouts(n=60):
    return {"workouts": [{"id": f"w{i}", "date": f"2026-{1 + i % 11:02d}-{1 + i % 27:02d}", "name": "W", "dur": 60,
                          "kcal": 300, "bw": 70,
                          "ex": [{"id": f"e{j}", "sets": [{"w": 50, "r": 8} for _ in range(4)]} for j in range(5)]}
                         for i in range(n)], "custom": []}


def test_workouts_load_and_save_use_a_constant_number_of_queries(client, user, counter):
    counter[0] = 0
    client.post("/api/workouts", json=big_workouts(60))
    save_60 = counter[0]
    counter[0] = 0
    got = client.get("/api/workouts").json()
    load_60 = counter[0]
    assert len(got["workouts"]) == 60 and len(got["workouts"][0]["ex"]) == 5
    assert sum(len(e["sets"]) for e in got["workouts"][0]["ex"]) == 20
    counter[0] = 0
    client.post("/api/workouts", json=big_workouts(10))
    save_10 = counter[0]
    assert load_60 <= 8 and save_60 <= 20
    assert save_60 <= save_10 + 4           # 6x more data, about the same number of statements (batches)


def test_tracker_load_is_constant_too(client, user, counter):
    custom = [{"n": f"Food {i}", "k": 100, "p": 1, "c": 1, "f": 1, "units": [{"n": "piece", "g": 40}]}
              for i in range(40)]
    counter[0] = 0
    client.post("/api/data", json={"log": {}, "custom": custom, "target": 2000})
    save = counter[0]
    counter[0] = 0
    got = client.get("/api/data").json()
    assert len(got["custom"]) == 40 and got["custom"][0]["units"] == [{"n": "piece", "g": 40}]
    assert counter[0] <= 8 and save <= 20
