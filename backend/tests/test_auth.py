from fastapi.testclient import TestClient

from tests.conftest import signup


def test_signup_login_me_logout(client):
    signup(client)
    assert client.get("/api/me").json()["email"] == "a@example.com"
    client.post("/api/logout")
    assert client.get("/api/me").status_code == 401
    r = client.post("/api/login", json={"email": "A@Example.com ", "password": "password123"})
    assert r.status_code == 200 and client.get("/api/me").status_code == 200


def test_signup_validation(client):
    assert client.post("/api/signup", json={"email": "nope", "password": "password123"}).status_code == 400
    assert client.post("/api/signup", json={"email": "b@example.com", "password": "short"}).status_code == 400
    signup(client)
    dup = client.post("/api/signup", json={"email": "a@example.com", "password": "password123"})
    assert dup.status_code == 409


def test_invite_code_required_when_configured(app):
    from dataclasses import replace
    app.state.settings = replace(app.state.settings, invite_code="secret")
    c = TestClient(app)
    assert c.post("/api/signup", json={"email": "a@example.com", "password": "password123"}).status_code == 403
    ok = c.post("/api/signup", json={"email": "a@example.com", "password": "password123", "invite": "secret"})
    assert ok.status_code == 200


def test_login_is_throttled_after_repeated_failures(client, user):
    bad = {"email": "a@example.com", "password": "wrong-password"}
    codes = [client.post("/api/login", json=bad).status_code for _ in range(10)]
    assert codes[:8] == [401] * 8 and codes[8:] == [429, 429]
    good = client.post("/api/login", json={"email": "a@example.com", "password": "password123"})
    assert good.status_code == 429  # locked out even with the right password until the window passes


def test_password_change_signs_out_other_devices(app, client, user):
    other = TestClient(app)
    other.post("/api/login", json={"email": "a@example.com", "password": "password123"})
    r = client.post("/api/account/password", json={"current": "password123", "new": "newpassword456"})
    assert r.status_code == 200
    assert client.get("/api/me").status_code == 200       # the device that changed it stays in
    assert other.get("/api/me").status_code == 401        # the other session is invalidated


def test_password_change_requires_current_password(client, user):
    r = client.post("/api/account/password", json={"current": "wrong-password", "new": "newpassword456"})
    assert r.status_code == 403


def test_cross_origin_post_is_blocked_but_same_origin_passes(client, user):
    doc = {"log": {}, "custom": [], "target": 2000}
    evil = client.post("/api/data", json=doc, headers={"Origin": "https://evil.example"})
    assert evil.status_code == 403
    same = client.post("/api/data", json=doc, headers={"Origin": "http://testserver"})
    assert same.status_code == 200


def test_data_requires_login(client):
    assert client.get("/api/data").status_code == 401
    assert client.get("/api/workouts").status_code == 401
    assert client.get("/api/v1/sync").status_code == 401
