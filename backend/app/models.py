"""Pydantic request/response models."""
from __future__ import annotations

from pydantic import BaseModel, Field


class ScoreSubmission(BaseModel):
    # nickname is derived from the authenticated token, not the client.
    score: int = Field(ge=0)
    kills: int = Field(ge=0)
    survival_seconds: int = Field(ge=0)


class SignupRequest(BaseModel):
    email: str = Field(min_length=3, max_length=128)
    password: str = Field(min_length=8, max_length=256)
    nickname: str = Field(min_length=1, max_length=16, pattern=r"^[A-Za-z0-9_-]+$")


class SignupResponse(BaseModel):
    message: str
    nickname: str


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=128)
    password: str = Field(min_length=1, max_length=256)


class AuthTokens(BaseModel):
    id_token: str
    access_token: str
    refresh_token: str | None = None
    expires_in: int
    nickname: str


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
