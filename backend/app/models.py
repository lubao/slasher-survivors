"""Pydantic request/response models."""
from __future__ import annotations

from pydantic import BaseModel, Field


class ScoreSubmission(BaseModel):
    nickname: str = Field(min_length=1, max_length=16, pattern=r"^[A-Za-z0-9_-]+$")
    score: int = Field(ge=0)
    kills: int = Field(ge=0)
    survival_seconds: int = Field(ge=0)


class Achievement(BaseModel):
    id: str
    name: str
    unlocked_at: str | None = None


class ScoreResponse(BaseModel):
    nickname: str
    score: int
    best_score: int
    games_played: int
    newly_unlocked: list[Achievement] = []


class LeaderboardEntry(BaseModel):
    nickname: str
    score: int


class LeaderboardResponse(BaseModel):
    entries: list[LeaderboardEntry] = []


class AchievementsResponse(BaseModel):
    nickname: str
    achievements: list[Achievement] = []
