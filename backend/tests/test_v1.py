ENTRY = {"date": "2026-11-13", "meal": "Lunch", "name": "Dal", "label": "1 bowl", "grams": 150, "kcal": 157,
         "protein": 9.7, "carbs": 21, "fat": 3.7}


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
