"""Unit tests for the World simulation. Deterministic via a seeded RNG."""
import random

from src import config as C
from src.entities import Enemy, Vec2
from src.world import World


def make_world(seed=1234):
    return World(width=800, height=600, rng=random.Random(seed))


def test_starts_with_player_centered_and_no_entities():
    w = make_world()
    assert w.player.pos == Vec2(400, 300)
    assert w.enemies == []
    assert w.bullets == []
    assert w.game_over is False


def test_player_moves_with_input():
    w = make_world()
    start_x = w.player.pos.x
    w.update(0.1, Vec2(1, 0))  # move right
    assert w.player.pos.x > start_x


def test_player_clamped_to_arena_bounds():
    w = make_world()
    for _ in range(200):
        w.update(0.1, Vec2(-1, 0))  # push left forever
    assert w.player.pos.x >= w.player.radius


def test_survival_timer_accumulates():
    w = make_world()
    for _ in range(10):
        w.update(0.5, Vec2(0, 0))
    assert w.survival_seconds == 5


def test_enemies_spawn_over_time():
    w = make_world()
    # no enemies should appear before the first interval elapses
    w.update(0.05, Vec2(0, 0))
    assert len(w.enemies) == 0
    # advance well past several spawn intervals
    for _ in range(20):
        w.update(0.2, Vec2(0, 0))
    assert len(w.enemies) > 0


def test_spawn_interval_ramps_down_with_time():
    w = make_world()
    start = w.current_spawn_interval()
    w.elapsed = 30.0
    later = w.current_spawn_interval()
    assert later < start
    assert later >= C.SPAWN_INTERVAL_MIN


def test_bullet_kills_enemy_and_scores():
    w = make_world()
    # place a weak enemy right next to the player and force a fresh attack
    w.enemies.append(Enemy(pos=Vec2(w.player.pos.x + 20, w.player.pos.y),
                           hp=C.BULLET_DAMAGE, radius=C.ENEMY_RADIUS, speed=0.0))
    w._attack_timer = C.ATTACK_INTERVAL  # ready to fire
    for _ in range(30):
        w.update(1 / 60, Vec2(0, 0))
        if w.kills:
            break
    assert w.kills == 1
    assert w.score == C.SCORE_PER_KILL


def test_enemy_contact_damages_player_with_cooldown():
    w = make_world()
    # overlap an enemy with the player
    w.enemies.append(Enemy(pos=Vec2(w.player.pos.x, w.player.pos.y),
                           hp=9999, radius=C.ENEMY_RADIUS, speed=0.0))
    w.update(1 / 60, Vec2(0, 0))
    hp_after_first = w.player.hp
    assert hp_after_first < C.PLAYER_MAX_HP
    # next immediate frame should NOT damage again (i-frames)
    w.update(1 / 60, Vec2(0, 0))
    assert w.player.hp == hp_after_first


def test_game_over_when_player_dies():
    w = make_world()
    w.enemies.append(Enemy(pos=Vec2(w.player.pos.x, w.player.pos.y),
                           hp=9999, radius=C.ENEMY_RADIUS, speed=0.0))
    # keep an enemy overlapping; let i-frames lapse repeatedly until death
    for _ in range(2000):
        w.enemies.append(Enemy(pos=Vec2(w.player.pos.x, w.player.pos.y),
                               hp=9999, radius=C.ENEMY_RADIUS, speed=0.0))
        w.update(1.0, Vec2(0, 0))  # large dt clears i-frames each step
        if w.game_over:
            break
    assert w.game_over is True
    assert w.player.hp == 0


def test_result_payload_shape():
    w = make_world()
    w.score, w.kills, w.elapsed = 120, 12, 45.7
    assert w.result() == {"score": 120, "kills": 12, "survival_seconds": 45}


def test_update_is_noop_after_game_over():
    w = make_world()
    w.game_over = True
    w.update(1.0, Vec2(1, 1))
    assert w.elapsed == 0.0  # nothing advanced
