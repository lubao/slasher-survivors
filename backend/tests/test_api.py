"""API-level tests using FastAPI TestClient (repo backed by moto)."""


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_post_score_requires_auth(unauth_client):
    # No Authorization header -> rejected by the Bearer dependency.
    resp = unauth_client.post("/scores", json={
        "score": 600, "kills": 3, "survival_seconds": 42,
    })
    assert resp.status_code in (401, 403)


def test_post_score_uses_nickname_from_token(client):
    resp = client.post("/scores",
                       headers={"X-Test-Nickname": "alice"},
                       json={"score": 600, "kills": 3, "survival_seconds": 42})
    assert resp.status_code == 200
    body = resp.json()
    assert body["nickname"] == "alice"  # derived from token, not the body
    assert body["best_score"] == 600
    assert body["games_played"] == 1
    ids = {a["id"] for a in body["newly_unlocked"]}
    assert {"first_blood", "high_scorer"} <= ids


def test_post_score_validates_input(client):
    # negative score rejected by pydantic
    bad = client.post("/scores", headers={"X-Test-Nickname": "x"}, json={
        "score": -1, "kills": 0, "survival_seconds": 0,
    })
    assert bad.status_code == 422


def test_leaderboard_endpoint(client):
    client.post("/scores", headers={"X-Test-Nickname": "a"},
                json={"score": 100, "kills": 1, "survival_seconds": 1})
    client.post("/scores", headers={"X-Test-Nickname": "b"},
                json={"score": 300, "kills": 1, "survival_seconds": 1})
    resp = client.get("/leaderboard?limit=10")
    assert resp.status_code == 200
    entries = resp.json()["entries"]
    assert [e["nickname"] for e in entries] == ["b", "a"]


def test_achievements_endpoint(client):
    client.post("/scores", headers={"X-Test-Nickname": "zed"},
                json={"score": 10, "kills": 1, "survival_seconds": 1})
    resp = client.get("/achievements/zed")
    assert resp.status_code == 200
    body = resp.json()
    assert body["nickname"] == "zed"
    assert "first_blood" in {a["id"] for a in body["achievements"]}


def test_achievements_empty_for_unknown_player(client):
    resp = client.get("/achievements/nobody")
    assert resp.status_code == 200
    assert resp.json()["achievements"] == []
