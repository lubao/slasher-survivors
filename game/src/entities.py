"""Game entities and a tiny 2D vector helper.

Pure logic only — no pygame import — so this module is fully unit-testable
without a display.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field


@dataclass
class Vec2:
    x: float = 0.0
    y: float = 0.0

    def __add__(self, other: "Vec2") -> "Vec2":
        return Vec2(self.x + other.x, self.y + other.y)

    def __sub__(self, other: "Vec2") -> "Vec2":
        return Vec2(self.x - other.x, self.y - other.y)

    def __mul__(self, scalar: float) -> "Vec2":
        return Vec2(self.x * scalar, self.y * scalar)

    def length(self) -> float:
        return math.hypot(self.x, self.y)

    def normalized(self) -> "Vec2":
        length = self.length()
        if length == 0:
            return Vec2(0.0, 0.0)
        return Vec2(self.x / length, self.y / length)


def distance(a: Vec2, b: Vec2) -> float:
    """Euclidean distance between two points."""
    return math.hypot(a.x - b.x, a.y - b.y)


def circles_collide(a: Vec2, ra: float, b: Vec2, rb: float) -> bool:
    """True if two circles overlap."""
    return distance(a, b) <= (ra + rb)


@dataclass
class Player:
    pos: Vec2
    hp: int
    max_hp: int
    radius: float
    invuln: float = 0.0  # remaining invulnerability seconds

    @property
    def alive(self) -> bool:
        return self.hp > 0

    def take_damage(self, amount: int, cooldown: float) -> bool:
        """Apply damage if not invulnerable. Returns True if damage landed."""
        if self.invuln > 0:
            return False
        self.hp = max(0, self.hp - amount)
        self.invuln = cooldown
        return True


@dataclass
class Enemy:
    pos: Vec2
    hp: int
    radius: float
    speed: float

    @property
    def alive(self) -> bool:
        return self.hp > 0


@dataclass
class Bullet:
    pos: Vec2
    vel: Vec2
    radius: float
    damage: int
    life: float = 0.0  # remaining lifetime seconds
    spent: bool = False
