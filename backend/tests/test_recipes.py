from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.core import db as database
from app.models import Recipe

RECIPE = {"name": "Egg bhurji toast", "portions": 2, "ingredients": [
    {"name": "Egg (whole, raw)", "label": "4 × egg", "grams": 200, "kcal": 286, "protein": 25.2, "carbs": 1.4,
     "fat": 19},
    {"name": "Cooking oil", "label": "2 × tsp", "grams": 9, "kcal": 81, "protein": 0, "carbs": 0, "fat": 9}]}
ENTRY = {"date": "2026-11-13", "meal": "Lunch", "name": "Egg bhurji toast", "label": "1 portion", "grams": 0,
         "kcal": 183.5, "protein": 12.6, "carbs": 0.7, "fat": 14}
SNAP = [{"name": "Egg (whole, raw)", "label": "", "grams": 100, "kcal": 143, "protein": 12.6, "carbs": 0.7,
         "fat": 9.5}]


def make(client, **over):
    r = client.post("/api/v1/recipes", json={**RECIPE, **over})
    assert r.status_code == 201, r.text
    return r.json()


def test_per_portion_comes_from_raw_totals_divided_by_portions(client, user):
    r = make(client)
    assert (r["kcal"], r["protein"], r["carbs"], r["fat"]) == (183.5, 12.6, 0.7, 14.0)
    assert r["version"] == 1 and len(r["ingredients"]) == 2 and r["portions"] == 2


def test_list_update_delete(client, user):
    r = make(client)
    assert [x["name"] for x in client.get("/api/v1/recipes").json()] == ["Egg bhurji toast"]
    up = client.put(f"/api/v1/recipes/{r['id']}", json={**RECIPE, "portions": 5, "version": 1})
    assert up.status_code == 200 and up.json()["version"] == 2 and up.json()["kcal"] == 73.4
    stale = client.put(f"/api/v1/recipes/{r['id']}", json={**RECIPE, "version": 1})
    assert stale.status_code == 409 and stale.json()["detail"]["current"]["version"] == 2
    assert client.delete(f"/api/v1/recipes/{r['id']}").status_code == 204
    assert client.get("/api/v1/recipes").json() == []
    assert client.delete(f"/api/v1/recipes/{r['id']}").status_code == 404


def test_names_are_unique_per_user_ignoring_case_and_spacing(client, user):
    a = make(client)
    dup = client.post("/api/v1/recipes", json={**RECIPE, "name": "  EGG bhurji   toast "})
    assert dup.status_code == 409 and "already have" in dup.json()["detail"]
    other = make(client, name="Plain omelette")
    clash = client.put(f"/api/v1/recipes/{other['id']}", json={**RECIPE, "version": 1})
    assert clash.status_code == 409
    same = client.put(f"/api/v1/recipes/{a['id']}", json={**RECIPE, "version": 1})   # keeping its own name is fine
    assert same.status_code == 200


def test_recipe_validation(client, user):
    post = lambda **o: client.post("/api/v1/recipes", json={**RECIPE, **o}).status_code  # noqa: E731
    assert post(ingredients=[]) == 422
    assert post(portions=0) == 422
    assert post(name="   ") == 422
    huge = [{"name": "Oil", "label": "", "grams": 1000, "kcal": 9000, "protein": 0, "carbs": 0, "fat": 1000}]
    assert post(ingredients=huge, portions=1) == 422          # over 5000 kcal per portion
    assert post(ingredients=huge, portions=4) == 201
    zero = [{"name": "Water", "label": "", "grams": 500, "kcal": 0}]
    assert post(name="Water", ingredients=zero) == 422


def test_recipes_belong_to_their_owner(app, client, user):
    r = make(client)
    other = TestClient(app)
    other.post("/api/signup", json={"email": "b@example.com", "password": "password123"})
    assert other.get("/api/v1/recipes").json() == []
    assert other.put(f"/api/v1/recipes/{r['id']}", json={**RECIPE, "version": 1}).status_code == 404
    assert other.delete(f"/api/v1/recipes/{r['id']}").status_code == 404
    assert other.post("/api/v1/recipes", json=RECIPE).status_code == 201     # same name in another account is fine


def test_recipes_require_login(client):
    assert client.get("/api/v1/recipes").status_code == 401


def test_entry_keeps_its_own_ingredient_snapshot(client, user):
    r = make(client)
    e = client.post("/api/v1/entries", json={**ENTRY, "ingredients": SNAP}).json()
    assert e["ingredients"] == SNAP
    client.put(f"/api/v1/recipes/{r['id']}", json={**RECIPE, "portions": 10, "version": 1})   # edit the recipe later
    got = client.get("/api/v1/entries?date=2026-11-13").json()[0]
    assert got["ingredients"] == SNAP and got["kcal"] == 183.5          # the old day is unchanged


def test_snapshot_reaches_the_legacy_document_and_survives_a_snapshot_save(client, user):
    client.post("/api/v1/entries", json={**ENTRY, "ingredients": SNAP})
    client.post("/api/v1/entries", json={**ENTRY, "name": "Plain toast", "ingredients": None})
    doc = client.get("/api/data").json()
    first, second = doc["log"]["2026-11-13"]["e"]
    assert first["i"] == SNAP and "i" not in second
    assert client.post("/api/data", json=doc).status_code == 200          # a full replace keeps the snapshot
    again = client.get("/api/data").json()["log"]["2026-11-13"]["e"]
    assert again[0]["i"] == SNAP and "i" not in again[1]


def test_legacy_snapshot_drops_malformed_lines(client, user):
    doc = {"log": {"2026-11-13": {"t": 2000, "e": [{"n": "X", "k": 100, "i": [{"name": "A", "grams": 5, "kcal": 1},
                                                                          "junk", {"grams": 3}]},
                                                   {"n": "Y", "k": 50, "i": "nope"}]}}, "custom": [], "target": 2000}
    assert client.post("/api/data", json=doc).status_code == 200
    x, y = client.get("/api/data").json()["log"]["2026-11-13"]["e"]
    assert [i["name"] for i in x["i"]] == ["A"] and "i" not in y


def test_updating_an_entry_replaces_the_snapshot(client, user):
    e = client.post("/api/v1/entries", json={**ENTRY, "ingredients": SNAP}).json()
    up = client.put(f"/api/v1/entries/{e['id']}", json={**ENTRY, "version": 1})
    assert up.status_code == 200 and up.json()["ingredients"] is None


def test_snapshot_size_is_limited(client, user):
    many = [SNAP[0]] * 41
    assert client.post("/api/v1/entries", json={**ENTRY, "ingredients": many}).status_code == 422


def test_export_includes_recipes_and_delete_removes_them(client, user):
    make(client)
    body = client.get("/api/account/export").json()
    assert body["recipes"][0]["name"] == "Egg bhurji toast" and body["recipes"][0]["kcal"] == 183.5
    assert client.post("/api/account/delete", json={"password": "password123"}).status_code == 200
    with database.SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(Recipe)) == 0