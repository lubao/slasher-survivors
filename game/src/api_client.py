"""Thin HTTP client to the leaderboard backend.

Design goals:
* **Non-blocking**: score submission runs on a daemon thread so the game loop
  never stalls on the network.
* **Offline-safe**: every network call is wrapped; failures return empty /
  ``False`` instead of raising, so the game keeps running without a backend.

The base URL comes from the ``BACKEND_URL`` environment variable (falls back to
localhost for local development).
"""
from __future__ import annotations

import os
import threading
import time
from typing import Callable, Optional

import requests

DEFAULT_TIMEOUT = 3.0


class ApiClient:
    def __init__(self, base_url: Optional[str] = None, timeout: float = DEFAULT_TIMEOUT):
        self.base_url = (base_url or os.environ.get("BACKEND_URL", "http://localhost:8000")).rstrip("/")
        self.timeout = timeout
        # Backend connectivity telemetry, updated by get_leaderboard().
        self.last_rtt_ms: Optional[float] = None  # round-trip time, ms
        self.online: bool = False
        # Auth state (set by log_in). nickname comes from the account.
        self.id_token: Optional[str] = None
        self.nickname: Optional[str] = None

    @property
    def logged_in(self) -> bool:
        return self.id_token is not None

    def _auth_headers(self) -> dict:
        return {"Authorization": f"Bearer {self.id_token}"} if self.id_token else {}

    def backend_info(self) -> dict:
        """Snapshot of backend connectivity for the UI."""
        return {"url": self.base_url, "online": self.online, "rtt_ms": self.last_rtt_ms}

    # ------------------------------------------------------------------ #
    # Auth (synchronous — called from the login/signup screens)
    # ------------------------------------------------------------------ #
    def sign_up(self, email: str, password: str, nickname: str) -> tuple[bool, str]:
        """Register an account. Returns (ok, message)."""
        try:
            resp = requests.post(f"{self.base_url}/auth/signup", timeout=self.timeout,
                                 json={"email": email, "password": password,
                                       "nickname": nickname})
            if resp.status_code < 400:
                return True, "Account created — please log in."
            return False, self._error_detail(resp, "Sign up failed")
        except requests.RequestException:
            return False, "Cannot reach server."

    def log_in(self, email: str, password: str) -> tuple[bool, str]:
        """Authenticate and store the ID token + nickname. Returns (ok, message)."""
        try:
            resp = requests.post(f"{self.base_url}/auth/login", timeout=self.timeout,
                                 json={"email": email, "password": password})
            if resp.status_code < 400:
                data = resp.json()
                self.id_token = data.get("id_token")
                self.nickname = data.get("nickname")
                return True, f"Welcome, {self.nickname}!"
            return False, self._error_detail(resp, "Login failed")
        except (requests.RequestException, ValueError):
            return False, "Cannot reach server."

    def log_out(self) -> None:
        self.id_token = None
        self.nickname = None

    @staticmethod
    def _error_detail(resp, default: str) -> str:
        try:
            return str(resp.json().get("detail", default))
        except ValueError:
            return default

    # ------------------------------------------------------------------ #
    # Writes
    # ------------------------------------------------------------------ #
    def submit_score(self, nickname: str, result: dict,
                     on_done: Optional[Callable[[bool], None]] = None) -> threading.Thread:
        """Submit a run result without blocking the caller.

        Returns the spawned thread (handy for tests / joining).
        """
        def _worker() -> None:
            ok = self._post_score(nickname, result)
            if on_done is not None:
                on_done(ok)

        thread = threading.Thread(target=_worker, name="submit-score", daemon=True)
        thread.start()
        return thread

    def _post_score(self, nickname: str, result: dict) -> bool:
        # The nickname is derived from the auth token server-side; we send only
        # the run result plus the Bearer token.
        try:
            resp = requests.post(f"{self.base_url}/scores", json=dict(result),
                                 headers=self._auth_headers(), timeout=self.timeout)
            return resp.status_code < 400
        except requests.RequestException:
            return False

    # ------------------------------------------------------------------ #
    # Reads
    # ------------------------------------------------------------------ #
    def get_leaderboard(self, limit: int = 10) -> list[dict]:
        start = time.perf_counter()
        try:
            resp = requests.get(f"{self.base_url}/leaderboard",
                                params={"limit": limit}, timeout=self.timeout)
            resp.raise_for_status()
            entries = resp.json().get("entries", [])
            self.last_rtt_ms = (time.perf_counter() - start) * 1000.0
            self.online = True
            return entries
        except (requests.RequestException, ValueError):
            self.last_rtt_ms = None
            self.online = False
            return []

    def get_achievements(self, nickname: str) -> list[dict]:
        try:
            resp = requests.get(f"{self.base_url}/achievements/{nickname}",
                                timeout=self.timeout)
            resp.raise_for_status()
            return resp.json().get("achievements", [])
        except (requests.RequestException, ValueError):
            return []
