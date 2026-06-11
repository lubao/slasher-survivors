"""World simulation for the horde-survival game.

This module holds ALL gameplay logic and is intentionally free of any pygame
import so it can be unit-tested headlessly. Rendering and input live elsewhere
(`renderer.py` / `main.py`) and only read from / feed into this simulation.

The update loop is time-step based (``dt`` in seconds) so behaviour is
frame-rate independent and deterministic when given a seeded RNG.
"""
from __future__ import annotations

import random
from typing import Optional

from . import config as C
from .entities import Bullet, Enemy, Player, Vec2, circles_collide, distance


class World:
    """Owns the live game state for a single run."""

    def __init__(self, width: int = C.SCREEN_WIDTH, height: int = C.SCREEN_HEIGHT,
                 rng: Optional[random.Random] = None):
        self.width = width
        self.height = height
        self.rng = rng or random.Random()

        self.player = Player(
            pos=Vec2(width / 2, height / 2),
            hp=C.PLAYER_MAX_HP,
            max_hp=C.PLAYER_MAX_HP,
            radius=C.PLAYER_RADIUS,
        )
        self.enemies: list[Enemy] = []
        self.bullets: list[Bullet] = []

        self.kills = 0
        self.score = 0
        self.elapsed = 0.0          # seconds survived
        self._spawn_timer = 0.0
        self._attack_timer = 0.0
        self.game_over = False

    # ------------------------------------------------------------------ #
    # Queries
    # ------------------------------------------------------------------ #
    @property
    def survival_seconds(self) -> int:
        return int(self.elapsed)

    def current_spawn_interval(self) -> float:
        """Spawn interval shrinks as the run goes on (difficulty ramp)."""
        interval = C.SPAWN_INTERVAL_START - C.SPAWN_RAMP * self.elapsed
        return max(C.SPAWN_INTERVAL_MIN, interval)

    def nearest_enemy(self, point: Vec2) -> Optional[Enemy]:
        nearest: Optional[Enemy] = None
        best = float("inf")
        for enemy in self.enemies:
            d = distance(point, enemy.pos)
            if d < best:
                best = d
                nearest = enemy
        return nearest

    def result(self) -> dict:
        """Summary payload for score submission."""
        return {
            "score": self.score,
            "kills": self.kills,
            "survival_seconds": self.survival_seconds,
        }

    # ------------------------------------------------------------------ #
    # Simulation
    # ------------------------------------------------------------------ #
    def update(self, dt: float, move: Vec2) -> None:
        """Advance the simulation by ``dt`` seconds given a movement vector."""
        if self.game_over:
            return

        self.elapsed += dt
        if self.player.invuln > 0:
            self.player.invuln = max(0.0, self.player.invuln - dt)

        self._move_player(dt, move)
        self._spawn(dt)
        self._move_enemies(dt)
        self._auto_attack(dt)
        self._move_bullets(dt)
        self._resolve_collisions()
        self._cleanup()

        if not self.player.alive:
            self.game_over = True

    def _move_player(self, dt: float, move: Vec2) -> None:
        step = move.normalized() * (C.PLAYER_SPEED * dt)
        p = self.player.pos + step
        # clamp inside the arena
        p.x = min(max(self.player.radius, p.x), self.width - self.player.radius)
        p.y = min(max(self.player.radius, p.y), self.height - self.player.radius)
        self.player.pos = p

    def _spawn(self, dt: float) -> None:
        self._spawn_timer += dt
        interval = self.current_spawn_interval()
        while self._spawn_timer >= interval:
            self._spawn_timer -= interval
            self.enemies.append(self._make_enemy())

    def _make_enemy(self) -> Enemy:
        """Spawn an enemy just outside a random edge of the arena."""
        edge = self.rng.randint(0, 3)
        if edge == 0:      # top
            pos = Vec2(self.rng.uniform(0, self.width), -C.ENEMY_RADIUS)
        elif edge == 1:    # bottom
            pos = Vec2(self.rng.uniform(0, self.width), self.height + C.ENEMY_RADIUS)
        elif edge == 2:    # left
            pos = Vec2(-C.ENEMY_RADIUS, self.rng.uniform(0, self.height))
        else:              # right
            pos = Vec2(self.width + C.ENEMY_RADIUS, self.rng.uniform(0, self.height))
        return Enemy(pos=pos, hp=C.ENEMY_HP, radius=C.ENEMY_RADIUS, speed=C.ENEMY_SPEED)

    def _move_enemies(self, dt: float) -> None:
        for enemy in self.enemies:
            direction = (self.player.pos - enemy.pos).normalized()
            enemy.pos = enemy.pos + direction * (enemy.speed * dt)

    def _auto_attack(self, dt: float) -> None:
        self._attack_timer += dt
        if self._attack_timer < C.ATTACK_INTERVAL:
            return
        target = self.nearest_enemy(self.player.pos)
        if target is None:
            return
        if distance(self.player.pos, target.pos) > C.ATTACK_RANGE:
            return
        self._attack_timer = 0.0
        direction = (target.pos - self.player.pos).normalized()
        self.bullets.append(Bullet(
            pos=Vec2(self.player.pos.x, self.player.pos.y),
            vel=direction * C.BULLET_SPEED,
            radius=C.BULLET_RADIUS,
            damage=C.BULLET_DAMAGE,
            life=C.BULLET_LIFETIME,
        ))

    def _move_bullets(self, dt: float) -> None:
        for bullet in self.bullets:
            bullet.pos = bullet.pos + bullet.vel * dt
            bullet.life -= dt

    def _resolve_collisions(self) -> None:
        # bullet -> enemy
        for bullet in self.bullets:
            if bullet.spent:
                continue
            for enemy in self.enemies:
                if not enemy.alive:
                    continue
                if circles_collide(bullet.pos, bullet.radius, enemy.pos, enemy.radius):
                    enemy.hp -= bullet.damage
                    bullet.spent = True
                    if not enemy.alive:
                        self.kills += 1
                        self.score += C.SCORE_PER_KILL
                    break

        # enemy -> player (contact damage, respects i-frames)
        for enemy in self.enemies:
            if not enemy.alive:
                continue
            if circles_collide(self.player.pos, self.player.radius,
                               enemy.pos, enemy.radius):
                self.player.take_damage(C.ENEMY_CONTACT_DAMAGE,
                                        C.PLAYER_CONTACT_COOLDOWN)

    def _cleanup(self) -> None:
        self.enemies = [e for e in self.enemies if e.alive]
        self.bullets = [
            b for b in self.bullets
            if not b.spent and b.life > 0 and self._in_bounds(b.pos, b.radius)
        ]

    def _in_bounds(self, pos: Vec2, radius: float) -> bool:
        return (-radius <= pos.x <= self.width + radius
                and -radius <= pos.y <= self.height + radius)
