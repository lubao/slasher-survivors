"""Unit tests for pure entity logic (no pygame, no display needed)."""
import math

from src.entities import (Bullet, Enemy, Player, Vec2, circles_collide,
                          distance)


def test_vec2_arithmetic():
    a = Vec2(3, 4)
    b = Vec2(1, 2)
    assert (a + b) == Vec2(4, 6)
    assert (a - b) == Vec2(2, 2)
    assert (a * 2) == Vec2(6, 8)
    assert a.length() == 5.0


def test_vec2_normalized_unit_length():
    n = Vec2(0, 5).normalized()
    assert math.isclose(n.length(), 1.0)
    assert n == Vec2(0, 1)


def test_vec2_normalized_zero_is_safe():
    assert Vec2(0, 0).normalized() == Vec2(0, 0)


def test_distance():
    assert distance(Vec2(0, 0), Vec2(3, 4)) == 5.0


def test_circles_collide():
    assert circles_collide(Vec2(0, 0), 5, Vec2(8, 0), 5) is True   # overlap
    assert circles_collide(Vec2(0, 0), 5, Vec2(11, 0), 5) is False  # gap


def test_player_takes_damage_then_is_invulnerable():
    p = Player(pos=Vec2(0, 0), hp=100, max_hp=100, radius=10)

    assert p.take_damage(20, cooldown=0.5) is True
    assert p.hp == 80
    # immediate second hit is blocked by i-frames
    assert p.take_damage(20, cooldown=0.5) is False
    assert p.hp == 80


def test_player_hp_floors_at_zero_and_marks_dead():
    p = Player(pos=Vec2(0, 0), hp=10, max_hp=100, radius=10)
    p.take_damage(999, cooldown=0.0)
    assert p.hp == 0
    assert p.alive is False


def test_enemy_and_bullet_alive_flags():
    e = Enemy(pos=Vec2(0, 0), hp=50, radius=10, speed=10)
    assert e.alive
    e.hp = 0
    assert not e.alive

    b = Bullet(pos=Vec2(0, 0), vel=Vec2(1, 0), radius=4, damage=10, life=1.0)
    assert b.spent is False
