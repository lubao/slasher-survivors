"""Achievement definitions and evaluation.

Pure logic: given a player's stats (this run + cumulative profile), decide which
achievements are *qualified*. Whether each is *newly* unlocked is decided by the
data layer (conditional writes), so this module stays free of I/O and easy to
unit-test.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class AchievementDef:
    id: str
    name: str
    description: str
    predicate: Callable[["AchievementContext"], bool]


@dataclass
class AchievementContext:
    run_score: int
    run_kills: int
    survival_seconds: int
    best_score: int
    total_kills: int
    games_played: int


# Ordered list of all achievements in the game.
ACHIEVEMENTS: list[AchievementDef] = [
    AchievementDef("first_blood", "First Blood",
                   "Defeat your first enemy",
                   lambda c: c.run_kills >= 1),
    AchievementDef("centurion", "Centurion",
                   "Defeat 100 enemies in total",
                   lambda c: c.total_kills >= 100),
    AchievementDef("survivor_5min", "Survivor",
                   "Survive 5 minutes in a single run",
                   lambda c: c.survival_seconds >= 300),
    AchievementDef("high_scorer", "High Scorer",
                   "Reach a score of 500 in a single run",
                   lambda c: c.run_score >= 500),
    AchievementDef("veteran", "Veteran",
                   "Play 10 games",
                   lambda c: c.games_played >= 10),
]

_BY_ID = {a.id: a for a in ACHIEVEMENTS}


def get_definition(achievement_id: str) -> AchievementDef | None:
    return _BY_ID.get(achievement_id)


def evaluate(context: AchievementContext) -> list[AchievementDef]:
    """Return all achievement definitions the context currently qualifies for."""
    return [a for a in ACHIEVEMENTS if a.predicate(context)]
