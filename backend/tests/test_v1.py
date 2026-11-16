ENTRY = {"date": "2026-11-13", "meal": "Lunch", "name": "Dal", "label": "1 bowl", "grams": 150, "kcal": 157,
         "protein": 9.7, "carbs": 21, "fat": 3.7}
DAY = {"water": 3, "weight_kg": 70.5, "marker_type": "rest", "marker_note": "", "target_kcal": 2000}


def make(client, **over):
    r = client.post("/api/v1/entries", json={**ENTRY, **over})
    assert r.status_code == 201, r.text
    return r.json()


def test_create_list_update(client, user):
    e = make(client)
    assert e["version"] == 1 and e["id"]
    assert [x["name"] for x in client.get("/api/v1/entries?date=2026-11-13").json()] == ["Dal"]
    up = client.put(f"/api/v1/entries/{e['id']}", json={**ENTRY, "kcal": 200, "version": 1})
    assert up.status_code == 200 and up.json()["version"] == 2 and up.json()["kcal"] == 200


def test_stale_update_is_rejected_with_current_copy(client, user):
    e = make(client)
    client.put(f"/api/v1/entries/{e['id']}", json={**ENTRY, "kcal": 200, "version": 1})   # device A wins
    lost = client.put(f"/api/v1/entries/{e['id']}", json={**ENTRY, "kcal": 999, "version": 1})  # device B is stale
    assert lost.status_code == 409
    cur = lost.json()["detail"]["current"]
    assert cur["kcal"] == 200 and cur["version"] == 2


def test_delete_leaves_tombstone_visible_in_sync(client, user):
    e = make(client)
    assert client.delete(f"/api/v1/entries/{e['id']}?version=1").status_code == 204
    assert client.get("/api/v1/entries?date=2026-11-13").json() == []
    feed = client.get("/api/v1/sync?since=0").json()
    assert [x["deleted"] for x in feed["entries"]] == [True]
    assert client.delete(f"/api/v1/entries/{e['id']}?version=2").status_code == 404


def test_sync_returns_only_changes_since_cursor(client, user):
    make(client, name="First")
    cursor = client.get("/api/v1/sync?since=0").json()["server_time"]
    import time
    time.sleep(0.01)
    make(client, name="Second")
    feed = client.get(f"/api/v1/sync?since={cursor}").json()
    assert [x["name"] for x in feed["entries"]] == ["Second"]


def test_entries_belong_to_their_owner(app, client, user):
    from fastapi.testclient import TestClient
    e = make(client)
    other = TestClient(app)
    other.post("/api/signup", json={"email": "b@example.com", "password": "password123"})
    assert other.put(f"/api/v1/entries/{e['id']}", json={**ENTRY, "version": 1}).status_code == 404
    assert other.delete(f"/api/v1/entries/{e['id']}?version=1").status_code == 404
    assert other.get("/api/v1/entries?date=2026-11-13").json() == []


def test_v1_entries_appear_in_legacy_document(client, user):
    make(client)
    day = client.get("/api/data").json()["log"]["2026-11-13"]
    assert day["e"][0]["n"] == "Dal" and day["e"][0]["m"] == "Lunch"


def test_input_validation(client, user):
    assert client.post("/api/v1/entries", json={**ENTRY, "kcal": -5}).status_code == 422
    assert client.post("/api/v1/entries", json={**ENTRY, "date": "13-11-2026"}).status_code == 422
    assert client.post("/api/v1/entries", json={**ENTRY, "date": "2026-13-45"}).status_code == 422


# --- the snapshot endpoint can leave v1-managed rows alone
def test_snapshot_save_with_entries_skip_keeps_ids_and_versions(client, user):
    e = make(client)
    doc = client.get("/api/data").json()
    assert doc["log"]["2026-11-13"]["e"][0]["id"] == e["id"]
    doc["log"]["2026-11-13"]["e"][0]["k"] = 999          # a stale value in the snapshot must be ignored
    assert client.post("/api/data?entries=skip", json=doc).status_code == 200
    after = client.get("/api/data").json()["log"]["2026-11-13"]["e"][0]
    assert after["id"] == e["id"] and after["v"] == 1 and after["k"] == 157
    assert client.put(f"/api/v1/entries/{e['id']}", json={**ENTRY, "kcal": 200, "version": 1}).status_code == 200


def test_default_snapshot_save_still_replaces_entries(client, user):
    make(client)
    doc = client.get("/api/data").json()
    doc["log"]["2026-11-13"]["e"][0]["k"] = 999
    client.post("/api/data", json=doc)
    assert client.get("/api/data").json()["log"]["2026-11-13"]["e"][0]["k"] == 999


# --- per-day facts
def test_day_create_update_and_stale_write(client, user):
    first = client.put("/api/v1/days/2026-11-13", json={**DAY, "version": 0})
    assert first.status_code == 200 and first.json()["version"] == 1
    second = client.put("/api/v1/days/2026-11-13", json={**DAY, "water": 4, "version": 1})
    assert second.json()["version"] == 2 and second.json()["water"] == 4
    stale = client.put("/api/v1/days/2026-11-13", json={**DAY, "water": 9, "version": 1})
    assert stale.status_code == 409 and stale.json()["detail"]["current"]["water"] == 4
    got = client.get("/api/data").json()
    assert got["log"]["2026-11-13"]["w"] == 4 and got["dv"]["2026-11-13"] == 2
    assert got["marks"]["2026-11-13"]["t"] == "rest"


def test_missing_day_with_nonzero_version_conflicts(client, user):
    r = client.put("/api/v1/days/2026-11-13", json={**DAY, "version": 3})
    assert r.status_code == 409 and r.json()["detail"]["current"] is None


def test_day_validation(client, user):
    assert client.put("/api/v1/days/not-a-date", json={**DAY, "version": 0}).status_code == 422
    assert client.put("/api/v1/days/2026-11-13", json={**DAY, "weight_kg": 5, "version": 0}).status_code == 422
    assert client.put("/api/v1/days/2026-11-13", json={**DAY, "marker_type": "party", "version": 0}).status_code == 422


def test_clearing_the_marker_removes_it(client, user):
    client.put("/api/v1/days/2026-11-13", json={**DAY, "version": 0})
    client.put("/api/v1/days/2026-11-13", json={**DAY, "marker_type": None, "version": 1})
    assert "2026-11-13" not in client.get("/api/data").json()["marks"]


def test_snapshot_with_days_skip_keeps_day_versions(client, user):
    client.put("/api/v1/days/2026-11-13", json={**DAY, "version": 0})
    doc = client.get("/api/data").json()
    assert client.post("/api/data?entries=skip&days=skip", json=doc).status_code == 200
    assert client.get("/api/data").json()["dv"]["2026-11-13"] == 1


def test_days_belong_to_their_owner(app, client, user):
    from fastapi.testclient import TestClient
    client.put("/api/v1/days/2026-11-13", json={**DAY, "version": 0})
    other = TestClient(app)
    other.post("/api/signup", json={"email": "b@example.com", "password": "password123"})
    assert other.get("/api/data").json()["dv"] == {}
    assert other.put("/api/v1/days/2026-11-13", json={**DAY, "version": 1}).status_code == 409
