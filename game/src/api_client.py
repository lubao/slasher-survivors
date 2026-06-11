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
from typing import Callable, Optional

import requests

DEFAULT_TIMEOUT = 3.0


class ApiClient:
    def __init__(self, base_url: Optional[str] = None, timeout: float = DEFAULT_TIMEOUT):
        self.base_url = (base_url or os.environ.get("BACKEND_URL", "http://localhost:8000")).rstrip("/")
        self.timeout = timeout

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
        payload = {"nickname": nickname, **result}
        try:
            resp = requests.post(f"{self.base_url}/scores", json=payload, timeout=self.timeout)
            return resp.status_code < 400
        except requests.RequestException:
            return False

    # ------------------------------------------------------------------ #
    # Reads
    # ------------------------------------------------------------------ #
    def get_leaderboard(self, limit: int = 10) -> list[dict]:
        try:
            resp = requests.get(f"{self.base_url}/leaderboard",
                                params={"limit": limit}, timeout=self.timeout)
            resp.raise_for_status()
            return resp.json().get("entries", [])
        except (requests.RequestException, ValueError):
            return []

    def get_achievements(self, nickname: str) -> list[dict]:
        try:
            resp = requests.get(f"{self.base_url}/achievements/{nickname}",
                                timeout=self.timeout)
            resp.raise_for_status()
            return resp.json().get("achievements", [])
        except (requests.RequestException, ValueError):
            return []
