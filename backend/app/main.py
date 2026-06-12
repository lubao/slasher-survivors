"""FastAPI application: scores, leaderboard, achievements, health.

Game-over events are emitted as structured JSON log lines so that, in
production, the Fargate container's stdout is shipped to CloudWatch Logs and is
queryable with Logs Insights.
"""
from __future__ import annotations

import json
import logging
import os
from functools import lru_cache

from fastapi import Depends, FastAPI, Query

from . import config
from .auth import get_current_user, log_in, sign_up
from .db import Repository
from .models import (AchievementsResponse, AuthTokens, LeaderboardResponse,
                     LoginRequest, ScoreResponse, ScoreSubmission,
                     SignupRequest, SignupResponse)

logger = logging.getLogger("slasher.events")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

app = FastAPI(title="Slasher Survivors API", version="0.1.0")


@lru_cache
def get_repository() -> Repository:
    repo = Repository()
    # Auto-create the table when pointing at DynamoDB Local for development.
    if config.DDB_ENDPOINT:
        try:
            repo.ensure_table()
        except Exception as exc:  # pragma: no cover - best effort for local dev
            logger.warning(json.dumps({"event": "ensure_table_failed", "error": str(exc)}))
    return repo


def log_game_over(nickname: str, submission: ScoreSubmission, result: dict) -> None:
    logger.info(json.dumps({
        "event": "game_over",
        "nickname": nickname,
        "score": submission.score,
        "kills": submission.kills,
        "survival_seconds": submission.survival_seconds,
        "best_score": result["best_score"],
        "games_played": result["games_played"],
        "newly_unlocked": [a["id"] for a in result["newly_unlocked"]],
        "region": os.environ.get("AWS_REGION", config.AWS_REGION),
    }))


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/auth/signup", response_model=SignupResponse)
def auth_signup(req: SignupRequest) -> SignupResponse:
    sign_up(req.email, req.password, req.nickname)
    return SignupResponse(
        message="Account created — you can now log in.", nickname=req.nickname)


@app.post("/auth/login", response_model=AuthTokens)
def auth_login(req: LoginRequest) -> AuthTokens:
    return AuthTokens(**log_in(req.email, req.password))


@app.post("/scores", response_model=ScoreResponse)
def submit_score(submission: ScoreSubmission,
                 user: dict = Depends(get_current_user),
                 repo: Repository = Depends(get_repository)) -> ScoreResponse:
    nickname = user["nickname"]
    result = repo.submit_run(
        nickname=nickname,
        score=submission.score,
        kills=submission.kills,
        survival_seconds=submission.survival_seconds,
    )
    log_game_over(nickname, submission, result)
    return ScoreResponse(
        nickname=nickname,
        score=submission.score,
        best_score=result["best_score"],
        games_played=result["games_played"],
        newly_unlocked=result["newly_unlocked"],
    )


@app.get("/leaderboard", response_model=LeaderboardResponse)
def leaderboard(limit: int = Query(10, ge=1, le=100),
                repo: Repository = Depends(get_repository)) -> LeaderboardResponse:
    return LeaderboardResponse(entries=repo.get_leaderboard(limit=limit))


@app.get("/achievements/{nickname}", response_model=AchievementsResponse)
def achievements(nickname: str,
                 repo: Repository = Depends(get_repository)) -> AchievementsResponse:
    return AchievementsResponse(nickname=nickname,
                                achievements=repo.get_achievements(nickname))
