"""Game entry point: state machine wiring input -> World -> Renderer.

States:
    MENU      nickname input, shows global leaderboard + your achievements
    PLAYING   the horde-survival run
    GAMEOVER  result screen; submits the score once (non-blocking)

Run with:  python -m src.main
"""
from __future__ import annotations

import sys
import threading

import pygame

from . import config as C
from .api_client import ApiClient
from .entities import Vec2
from .renderer import Renderer
from .world import World

MENU, PLAYING, GAMEOVER = "menu", "playing", "gameover"


class GameApp:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption(C.TITLE)
        self.screen = pygame.display.set_mode((C.SCREEN_WIDTH, C.SCREEN_HEIGHT))
        self.clock = pygame.time.Clock()
        self.renderer = Renderer(self.screen)
        self.api = ApiClient()

        self.state = MENU
        self.nickname = ""
        self.world: World | None = None
        self.submitted = False

        # cached menu data (refreshed in background so the UI never blocks)
        self._leaderboard: list[dict] = []
        self._achievements: list[dict] = []
        self.refresh_menu_data()

    # ------------------------------------------------------------------ #
    def refresh_menu_data(self) -> None:
        def _worker():
            self._leaderboard = self.api.get_leaderboard(limit=10)
            if self.nickname:
                self._achievements = self.api.get_achievements(self.nickname)
        threading.Thread(target=_worker, daemon=True).start()

    # ------------------------------------------------------------------ #
    def run(self) -> None:
        running = True
        while running:
            dt = self.clock.tick(C.FPS) / 1000.0
            running = self._handle_events()
            if self.state == PLAYING:
                self._update_playing(dt)
            self._draw()
            pygame.display.flip()
        pygame.quit()

    # ------------------------------------------------------------------ #
    def _handle_events(self) -> bool:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    return False
                if self.state == MENU:
                    self._menu_key(event)
                elif self.state == GAMEOVER and event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    self.state = MENU
                    self.refresh_menu_data()
        return True

    def _menu_key(self, event) -> None:
        if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            if self.nickname.strip():
                self._start_run()
        elif event.key == pygame.K_BACKSPACE:
            self.nickname = self.nickname[:-1]
        elif event.unicode and event.unicode.isprintable() and len(self.nickname) < 16:
            ch = event.unicode
            if ch.isalnum() or ch in "_-":
                self.nickname += ch

    # ------------------------------------------------------------------ #
    def _start_run(self) -> None:
        self.world = World()
        self.submitted = False
        self.state = PLAYING

    def _update_playing(self, dt: float) -> None:
        keys = pygame.key.get_pressed()
        move = Vec2(
            (keys[pygame.K_d] or keys[pygame.K_RIGHT]) - (keys[pygame.K_a] or keys[pygame.K_LEFT]),
            (keys[pygame.K_s] or keys[pygame.K_DOWN]) - (keys[pygame.K_w] or keys[pygame.K_UP]),
        )
        self.world.update(dt, move)
        if self.world.game_over:
            self.state = GAMEOVER
            self._submit_result()

    def _submit_result(self) -> None:
        if self.submitted or self.world is None:
            return

        def _done(ok: bool) -> None:
            self.submitted = True
            self.refresh_menu_data()

        self.api.submit_score(self.nickname, self.world.result(), on_done=_done)

    # ------------------------------------------------------------------ #
    def _draw(self) -> None:
        if self.state == MENU:
            self.renderer.draw_menu(self.nickname, self._leaderboard, self._achievements)
        elif self.state == PLAYING:
            self.renderer.draw_world(self.world)
        elif self.state == GAMEOVER:
            self.renderer.draw_gameover(self.world, self.submitted)


def main() -> int:
    GameApp().run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
