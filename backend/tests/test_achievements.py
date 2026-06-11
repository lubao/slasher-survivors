"""Unit tests for achievement evaluation (pure logic)."""
from app.achievements import AchievementContext, evaluate, get_definition


def ctx(**kw):
    base = dict(run_score=0, run_kills=0, survival_seconds=0,
                best_score=0, total_kills=0, games_played=0)
    base.update(kw)
    return AchievementContext(**base)


def ids(defs):
    return {d.id for d in defs}


def test_nothing_unlocked_at_zero():
    assert evaluate(ctx()) == []


def test_first_blood_on_one_kill():
    assert "first_blood" in ids(evaluate(ctx(run_kills=1)))


def test_centurion_needs_100_total_kills():
    assert "centurion" not in ids(evaluate(ctx(total_kills=99)))
    assert "centurion" in ids(evaluate(ctx(total_kills=100)))


def test_survivor_needs_5_minutes():
    assert "survivor_5min" not in ids(evaluate(ctx(survival_seconds=299)))
    assert "survivor_5min" in ids(evaluate(ctx(survival_seconds=300)))


def test_high_scorer_threshold():
    assert "high_scorer" in ids(evaluate(ctx(run_score=500)))


def test_veteran_threshold():
    assert "veteran" in ids(evaluate(ctx(games_played=10)))


def test_multiple_unlock_together():
    result = ids(evaluate(ctx(run_kills=5, run_score=500, survival_seconds=300,
                              total_kills=120, games_played=11)))
    assert result == {"first_blood", "centurion", "survivor_5min",
                      "high_scorer", "veteran"}


def test_get_definition_roundtrip():
    assert get_definition("first_blood").name == "First Blood"
    assert get_definition("nope") is None
