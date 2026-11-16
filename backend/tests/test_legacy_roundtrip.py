from tests.conftest import tracker_doc, workouts_doc


def test_tracker_roundtrip(client, user):
    doc = tracker_doc()
    assert client.post("/api/data", json=doc).status_code == 200
    got = client.get("/api/data").json()
    assert got["target"] == 2100 and got["setup"] is True and got["updated"] == doc["updated"]
    assert got["goals"] == {"weekly": 4}
    assert got["profile"]["age"] == 21 and got["profile"]["sex"] == "male"
    assert set(got["log"]) == {"2026-11-10", "2026-11-11"}
    day = got["log"]["2026-11-10"]
    assert [x["n"] for x in day["e"]] == ["Dal", "Roti"] and day["w"] == 3 and day["wt"] == 70.5
    assert day["e"][0]["m"] == "Lunch" and day["e"][0]["k"] == 157.5
    assert got["marks"]["2026-11-12"] == {"t": "sick", "n": "fever"}     # marker-only day is not a log day
    assert "2026-11-12" not in got["log"]
    names = {c["n"]: c for c in got["custom"]}
    assert names["Homemade laddoo"]["units"] == [{"n": "piece", "g": 40}] and "est" not in names["Homemade laddoo"]
    assert names["Egg bhurji"]["est"] is True and names["Egg bhurji"]["kind"] == "cooked"


def test_saving_again_replaces_instead_of_duplicating(client, user):
    client.post("/api/data", json=tracker_doc())
    client.post("/api/data", json=tracker_doc())
    got = client.get("/api/data").json()
    assert len(got["log"]["2026-11-10"]["e"]) == 2 and len(got["custom"]) == 2


def test_deleting_everything_clears_rows(client, user):
    client.post("/api/data", json=tracker_doc())
    client.post("/api/data", json={"log": {}, "custom": [], "target": 1800})
    got = client.get("/api/data").json()
    assert got["log"] == {} and got["custom"] == [] and got["marks"] == {} and got["target"] == 1800


def test_bad_rows_are_skipped_not_fatal(client, user):
    doc = tracker_doc(log={"not-a-date": {"e": []}, "2026-11-10": {"t": "x", "e": [{"n": "A", "k": "oops"}]}})
    assert client.post("/api/data", json=doc).status_code == 200
    day = client.get("/api/data").json()["log"]["2026-11-10"]
    assert day["e"][0]["k"] == 0 and day["t"] == 2100


def test_empty_account_returns_defaults(client, user):
    got = client.get("/api/data").json()
    assert got["target"] == 2000 and got["log"] == {} and got["setup"] is False
    w = client.get("/api/workouts").json()
    assert w["workouts"] == [] and w["bw"] == 0


def test_workouts_roundtrip(client, user):
    doc = workouts_doc()
    assert client.post("/api/workouts", json=doc).status_code == 200
    got = client.get("/api/workouts").json()
    assert got["bw"] == 70 and got["updated"] == doc["updated"]
    assert [w["id"] for w in got["workouts"]] == ["abc2", "abc1"]       # newest first
    push = got["workouts"][1]
    assert push["name"] == "Push" and push["dur"] == 60 and push["kcal"] == 310
    assert push["ex"][0] == doc["workouts"][0]["ex"][0]                   # sets, kinds and order survive
    assert push["ex"][1]["sets"] == [{"d": 10, "k": 1.2}]
    assert got["custom"] == doc["custom"]


def test_users_never_see_each_others_data(app, client, user):
    from fastapi.testclient import TestClient
    client.post("/api/data", json=tracker_doc())
    client.post("/api/workouts", json=workouts_doc())
    other = TestClient(app)
    other.post("/api/signup", json={"email": "b@example.com", "password": "password123"})
    assert other.get("/api/data").json()["log"] == {}
    assert other.get("/api/workouts").json()["workouts"] == []
    # same client-side ids in two accounts must not collide
    assert other.post("/api/workouts", json=workouts_doc()).status_code == 200
    assert len(client.get("/api/workouts").json()["workouts"]) == 2
