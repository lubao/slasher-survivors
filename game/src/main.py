"""Game entry point: state machine wiring input -> World -> Renderer.

States:
    LOGIN     email/password -> Cognito login via backend
    SIGNUP    nickname/email/password -> account creation (auto-confirmed)
    MENU      shows global leaderboard + your achievements; ENTER to play
    PLAYING   the horde-survival run
    GAMEOVER  result screen; submits the score once (non-blocking)

Score submission requires login: the nickname comes from the account, and the
backend derives it from the auth token.

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

LOGIN, SIGNUP, MENU, PLAYING, GAMEOVER = "login", "signup", "menu", "playing", "gameover"

LOGIN_FIELDS = ["email", "password"]
SIGNUP_FIELDS = ["nickname", "email", "password"]


class GameApp:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption(C.TITLE)
        self.screen = pygame.display.set_mode((C.SCREEN_WIDTH, C.SCREEN_HEIGHT))
        self.clock = pygame.time.Clock()
        self.renderer = Renderer(self.screen)
        self.api = ApiClient()

        self.state = LOGIN
        self.nickname = ""
        self.world: World | None = None
        self.submitted = False

        # auth form state
        self.login = {"email": "", "password": ""}
        self.signup = {"nickname": "", "email": "", "password": ""}
        self.active = 0
        self.auth_message = ""

        # cached menu data (refreshed in background so the UI never blocks)
        self._leaderboard: list[dict] = []
        self._achievements: list[dict] = []

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
                if self.state == LOGIN:
                    self._login_key(event)
                elif self.state == SIGNUP:
                    self._signup_key(event)
                elif self.state == MENU:
                    self._menu_key(event)
                elif self.state == GAMEOVER and event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    self.state = MENU
                    self.refresh_menu_data()
        return True

    # ------------------------------------------------------------------ #
    # Text-field editing helpers
    # ------------------------------------------------------------------ #
    @staticmethod
    def _edit(fields: dict, name: str, event, *, nickname: bool = False) -> None:
        if event.key == pygame.K_BACKSPACE:
            fields[name] = fields[name][:-1]
        elif event.unicode and event.unicode.isprintable():
            ch = event.unicode
            if nickname and not (ch.isalnum() or ch in "_-"):
                return
            limit = 16 if nickname else 64
            if len(fields[name]) < limit:
                fields[name] += ch

    def _login_key(self, event) -> None:
        if event.key == pygame.K_F2:
            self.state = SIGNUP
            self.active = 0
            self.auth_message = ""
            return
        if event.key == pygame.K_TAB:
            self.active = (self.active + 1) % len(LOGIN_FIELDS)
            return
        if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            self._do_login()
            return
        self._edit(self.login, LOGIN_FIELDS[self.active], event)

    def _signup_key(self, event) -> None:
        if event.key == pygame.K_F2:
            self.state = LOGIN
            self.active = 0
            self.auth_message = ""
            return
        if event.key == pygame.K_TAB:
            self.active = (self.active + 1) % len(SIGNUP_FIELDS)
            return
        if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            self._do_signup()
            return
        name = SIGNUP_FIELDS[self.active]
        self._edit(self.signup, name, event, nickname=(name == "nickname"))

    def _menu_key(self, event) -> None:
        if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            self._start_run()
        elif event.key == pygame.K_F3:  # log out
            self.api.log_out()
            self.nickname = ""
            self._achievements = []
            self.state = LOGIN
            self.active = 0
            self.auth_message = "Logged out."

    # ------------------------------------------------------------------ #
    def _do_login(self) -> None:
        email, password = self.login["email"].strip(), self.login["password"]
        if not email or not password:
            self.auth_message = "Enter email and password."
            return
        self.auth_message = "Logging in…"
        self._draw(); pygame.display.flip()
        ok, msg = self.api.log_in(email, password)
        self.auth_message = msg
        if ok:
            self.nickname = self.api.nickname or ""
            self.login["password"] = ""
            self.state = MENU
            self.refresh_menu_data()

    def _do_signup(self) -> None:
        nickname = self.signup["nickname"].strip()
        email = self.signup["email"].strip()
        password = self.signup["password"]
        if not (nickname and email and password):
            self.auth_message = "Fill in nickname, email and password."
            return
        self.auth_message = "Creating account…"
        self._draw(); pygame.display.flip()
        ok, msg = self.api.sign_up(email, password, nickname)
        self.auth_message = msg
        if ok:
            # prefill login with the new email and switch to the login screen
            self.login["email"] = email
            self.login["password"] = ""
            self.state = LOGIN
            self.active = 1  # focus the password field

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
        if self.state == LOGIN:
            self.renderer.draw_login(self.login, LOGIN_FIELDS[self.active],
                                     self.auth_message, self.api.backend_info())
        elif self.state == SIGNUP:
            self.renderer.draw_signup(self.signup, SIGNUP_FIELDS[self.active],
                                      self.auth_message, self.api.backend_info())
        elif self.state == MENU:
            self.renderer.draw_menu(self.nickname, self._leaderboard,
                                    self._achievements, self.api.backend_info())
        elif self.state == PLAYING:
            self.renderer.draw_world(self.world)
        elif self.state == GAMEOVER:
            self.renderer.draw_gameover(self.world, self.submitted)


def main() -> int:
    GameApp().run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
