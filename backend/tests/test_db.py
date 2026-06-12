"""Integration tests for the DynamoDB Repository against moto."""


def test_submit_run_creates_profile_and_unlocks_first_blood(repo):
    result = repo.submit_run("alice", score=120, kills=5, survival_seconds=30)
    assert result["best_score"] == 120
    assert result["games_played"] == 1
    assert result["total_kills"] == 5
    unlocked = {a["id"] for a in result["newly_unlocked"]}
    assert "first_blood" in unlocked


def test_best_score_only_increases(repo):
    repo.submit_run("bob", score=200, kills=1, survival_seconds=10)
    second = repo.submit_run("bob", score=50, kills=1, survival_seconds=10)
    assert second["best_score"] == 200          # not lowered
    third = repo.submit_run("bob", score=300, kills=1, survival_seconds=10)
    assert third["best_score"] == 300           # raised
    assert third["games_played"] == 3


def test_total_kills_accumulate(repo):
    repo.submit_run("carol", score=10, kills=40, survival_seconds=5)
    r = repo.submit_run("carol", score=10, kills=60, survival_seconds=5)
    assert r["total_kills"] == 100
    assert "centurion" in {a["id"] for a in r["newly_unlocked"]}


def test_achievement_only_unlocked_once(repo):
    first = repo.submit_run("dave", score=10, kills=1, survival_seconds=1)
    second = repo.submit_run("dave", score=10, kills=1, survival_seconds=1)
    assert "first_blood" in {a["id"] for a in first["newly_unlocked"]}
    assert "first_blood" not in {a["id"] for a in second["newly_unlocked"]}


def test_get_achievements_lists_unlocked(repo):
    repo.submit_run("erin", score=600, kills=1, survival_seconds=1)
    achs = {a["id"] for a in repo.get_achievements("erin")}
    assert {"first_blood", "high_scorer"} <= achs


def test_leaderboard_sorted_desc_and_best_per_player(repo):
    repo.submit_run("low", score=100, kills=1, survival_seconds=1)
    repo.submit_run("high", score=900, kills=1, survival_seconds=1)
    repo.submit_run("mid", score=500, kills=1, survival_seconds=1)
    repo.submit_run("high", score=50, kills=1, survival_seconds=1)  # no effect

    board = repo.get_leaderboard(limit=10)
    names = [e["nickname"] for e in board]
    scores = [e["score"] for e in board]
    assert names[:3] == ["high", "mid", "low"]
    assert scores == sorted(scores, reverse=True)
    assert scores[0] == 900


def test_leaderboard_respects_limit(repo):
    for i in range(5):
        repo.submit_run(f"p{i}", score=i * 10, kills=1, survival_seconds=1)
    assert len(repo.get_leaderboard(limit=3)) == 3
