"""Pygame rendering layer.

Reads from the headless :class:`~src.world.World` and draws it. Keeping all
pygame drawing here means the simulation stays testable.
"""
from __future__ import annotations

import pygame

from . import config as C
from .world import World


class Renderer:
    def __init__(self, screen: pygame.Surface):
        self.screen = screen
        self.font = pygame.font.SysFont("consolas,menlo,monospace", 20)
        self.big = pygame.font.SysFont("consolas,menlo,monospace", 44, bold=True)
        self.small = pygame.font.SysFont("consolas,menlo,monospace", 16)

    # ------------------------------------------------------------------ #
    def _text(self, surface_font, text, color, pos, center=False):
        surf = surface_font.render(text, True, color)
        rect = surf.get_rect()
        if center:
            rect.center = pos
        else:
            rect.topleft = pos
        self.screen.blit(surf, rect)

    # ------------------------------------------------------------------ #
    def draw_world(self, world: World) -> None:
        self.screen.fill(C.COLOR_BG)

        for bullet in world.bullets:
            pygame.draw.circle(self.screen, C.COLOR_BULLET,
                               (int(bullet.pos.x), int(bullet.pos.y)), bullet.radius)
        for enemy in world.enemies:
            pygame.draw.circle(self.screen, C.COLOR_ENEMY,
                               (int(enemy.pos.x), int(enemy.pos.y)), enemy.radius)

        player = world.player
        # blink while invulnerable
        if not (player.invuln > 0 and int(player.invuln * 20) % 2 == 0):
            pygame.draw.circle(self.screen, C.COLOR_PLAYER,
                               (int(player.pos.x), int(player.pos.y)), int(player.radius))

        self._draw_hud(world)

    def _draw_hud(self, world: World) -> None:
        p = world.player
        # HP bar
        bar_w, bar_h = 220, 16
        pygame.draw.rect(self.screen, C.COLOR_HP_BACK, (16, 16, bar_w, bar_h))
        frac = max(0.0, p.hp / p.max_hp)
        pygame.draw.rect(self.screen, C.COLOR_HP_FRONT, (16, 16, int(bar_w * frac), bar_h))
        self._text(self.small, f"HP {p.hp}/{p.max_hp}", C.COLOR_TEXT, (20, 17))

        self._text(self.font, f"Score {world.score}", C.COLOR_TEXT, (16, 40))
        self._text(self.font, f"Kills {world.kills}", C.COLOR_TEXT, (16, 64))
        self._text(self.font, f"Time  {world.survival_seconds}s", C.COLOR_TEXT, (16, 88))

    # ------------------------------------------------------------------ #
    def draw_menu(self, nickname: str, leaderboard: list[dict],
                  achievements: list[dict]) -> None:
        self.screen.fill(C.COLOR_BG)
        cx = C.SCREEN_WIDTH // 2
        self._text(self.big, C.TITLE, C.COLOR_PLAYER, (cx, 70), center=True)
        self._text(self.font, "Enter your nickname, then press ENTER to play",
                   C.COLOR_TEXT, (cx, 130), center=True)

        # nickname box
        box = pygame.Rect(cx - 160, 160, 320, 40)
        pygame.draw.rect(self.screen, (40, 40, 55), box, border_radius=6)
        pygame.draw.rect(self.screen, C.COLOR_PLAYER, box, width=2, border_radius=6)
        caret = "_" if (pygame.time.get_ticks() // 500) % 2 == 0 else " "
        self._text(self.font, f"{nickname}{caret}", C.COLOR_TEXT,
                   (box.centerx, box.centery), center=True)

        # leaderboard
        self._text(self.font, "— Global Leaderboard —", C.COLOR_BULLET, (120, 250))
        if not leaderboard:
            self._text(self.small, "(no scores yet / backend offline)",
                       (160, 160, 160), (120, 280))
        for i, entry in enumerate(leaderboard[:10]):
            line = f"{i + 1:2d}. {entry.get('nickname', '?'):<14} {entry.get('score', 0):>6}"
            self._text(self.small, line, C.COLOR_TEXT, (120, 280 + i * 22))

        # achievements for current player
        self._text(self.font, "— Your Achievements —", C.COLOR_BULLET, (560, 250))
        if not achievements:
            self._text(self.small, "(none yet)", (160, 160, 160), (600, 280))
        for i, ach in enumerate(achievements[:10]):
            self._text(self.small, f"\u2605 {ach.get('name', ach.get('id', '?'))}",
                       C.COLOR_HP_FRONT, (560, 280 + i * 22))

        self._text(self.small, "WASD / Arrows to move · auto-attack · ESC to quit",
                   (170, 170, 170), (cx, C.SCREEN_HEIGHT - 30), center=True)

    # ------------------------------------------------------------------ #
    def draw_gameover(self, world: World, submitted: bool) -> None:
        self.draw_world(world)
        overlay = pygame.Surface((C.SCREEN_WIDTH, C.SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 170))
        self.screen.blit(overlay, (0, 0))

        cx, cy = C.SCREEN_WIDTH // 2, C.SCREEN_HEIGHT // 2
        self._text(self.big, "GAME OVER", C.COLOR_ENEMY, (cx, cy - 90), center=True)
        self._text(self.font, f"Score: {world.score}", C.COLOR_TEXT, (cx, cy - 30), center=True)
        self._text(self.font, f"Kills: {world.kills}", C.COLOR_TEXT, (cx, cy), center=True)
        self._text(self.font, f"Survived: {world.survival_seconds}s",
                   C.COLOR_TEXT, (cx, cy + 30), center=True)
        status = "uploaded \u2713" if submitted else "uploading…"
        self._text(self.small, f"score {status}", (170, 170, 170), (cx, cy + 70), center=True)
        self._text(self.font, "Press ENTER to return to menu",
                   C.COLOR_BULLET, (cx, cy + 110), center=True)
