from app.services import catalog


def test_catalogue_is_valid():
    foods = catalog.load()["foods"]
    names = [f["n"].lower() for f in foods]
    assert len(names) == len(set(names)) and len(foods) >= 60
    assert sum(1 for f in foods if f.get("raw")) >= 20
    for f in foods:
        k, p, c, fat = f["k"], f["p"], f["c"], f["f"]
        assert 0 < k <= 900 and min(p, c, fat) >= 0 and p + c + fat <= 105, f["n"]
        assert abs(4 * p + 4 * c + 9 * fat - k) <= max(40, .25 * k), f["n"]
        assert 1 <= len(f["units"]) <= 4, f["n"]
        for u in f["units"]:
            assert 0.5 <= u["g"] <= 1500 or u["n"] == "almond", f["n"]
            assert k * u["g"] / 100 <= 1500, f["n"]


def test_raw_ingredients_have_the_units_recipes_need():
    by = {f["n"]: f for f in catalog.load()["foods"]}
    assert {"small tomato", "medium tomato", "large tomato"} == {u["n"] for u in by["Tomato (raw)"]["units"]}
    assert by["Soya chunks (dry)"]["raw"] and by["Cooking oil"]["units"][0]["n"] == "tsp"


def test_foods_endpoint(client, user):
    r = client.get("/api/v1/foods")
    assert r.status_code == 200 and "private" in r.headers["cache-control"]
    j = r.json()
    assert j["version"] and any(f.get("raw") for f in j["foods"]) and j == catalog.load()


def test_foods_requires_login(client):
    assert client.get("/api/v1/foods").status_code == 401