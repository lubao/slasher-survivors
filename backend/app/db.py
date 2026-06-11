"""DynamoDB single-table data access.

Table layout (see README):

    PK                     SK                 attrs
    PLAYER#<nick>          PROFILE            nickname, best_score, games_played,
                                              total_kills, GSI1PK, GSI1SK(=best_score)
    PLAYER#<nick>          RUN#<ts>#<uuid>    score, kills, survival_seconds, region
    PLAYER#<nick>          ACH#<id>           id, name, unlocked_at

Global leaderboard is the GSI1 query: GSI1PK="LEADERBOARD" sorted by GSI1SK
(best_score) descending.

The same table is a DynamoDB Global Table in production; this code is
Region-agnostic and simply writes to its local replica ("就近寫入").
"""
from __future__ import annotations

import datetime as dt
import uuid
from decimal import Decimal

import boto3
from botocore.exceptions import ClientError

from . import config
from .achievements import AchievementContext, evaluate, get_definition

PROFILE_SK = "PROFILE"


def _now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def _int(value) -> int:
    if isinstance(value, Decimal):
        return int(value)
    return int(value or 0)


class Repository:
    def __init__(self, table_name: str | None = None, region: str | None = None,
                 endpoint_url: str | None = "__default__"):
        self.table_name = table_name or config.TABLE_NAME
        self.region = region or config.AWS_REGION
        endpoint = config.DDB_ENDPOINT if endpoint_url == "__default__" else endpoint_url
        self._resource = boto3.resource(
            "dynamodb", region_name=self.region, endpoint_url=endpoint)
        self.table = self._resource.Table(self.table_name)

    # ------------------------------------------------------------------ #
    # Schema (used by local dev + tests; prod schema is created by CDK)
    # ------------------------------------------------------------------ #
    def ensure_table(self) -> None:
        existing = [t.name for t in self._resource.tables.all()]
        if self.table_name in existing:
            return
        self._resource.create_table(
            TableName=self.table_name,
            BillingMode="PAY_PER_REQUEST",
            KeySchema=[
                {"AttributeName": "PK", "KeyType": "HASH"},
                {"AttributeName": "SK", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "PK", "AttributeType": "S"},
                {"AttributeName": "SK", "AttributeType": "S"},
                {"AttributeName": "GSI1PK", "AttributeType": "S"},
                {"AttributeName": "GSI1SK", "AttributeType": "N"},
            ],
            GlobalSecondaryIndexes=[{
                "IndexName": config.LEADERBOARD_INDEX,
                "KeySchema": [
                    {"AttributeName": "GSI1PK", "KeyType": "HASH"},
                    {"AttributeName": "GSI1SK", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
            }],
        )
        self.table.wait_until_exists()

    # ------------------------------------------------------------------ #
    # Writes
    # ------------------------------------------------------------------ #
    def submit_run(self, nickname: str, score: int, kills: int,
                   survival_seconds: int) -> dict:
        """Persist a run, update the player's profile/best, unlock achievements.

        Returns a dict with best_score, games_played, total_kills and the list
        of newly-unlocked achievement definitions.
        """
        pk = f"PLAYER#{nickname}"

        # 1) immutable run-history record
        self.table.put_item(Item={
            "PK": pk,
            "SK": f"RUN#{_now_iso()}#{uuid.uuid4().hex[:8]}",
            "type": "run",
            "nickname": nickname,
            "score": score,
            "kills": kills,
            "survival_seconds": survival_seconds,
            "region": self.region,
            "created_at": _now_iso(),
        })

        # 2) bump cumulative counters on the profile
        profile = self.table.update_item(
            Key={"PK": pk, "SK": PROFILE_SK},
            UpdateExpression=("SET #nick = :n, GSI1PK = :lb "
                              "ADD games_played :one, total_kills :k"),
            ExpressionAttributeNames={"#nick": "nickname"},
            ExpressionAttributeValues={
                ":n": nickname, ":lb": config.LEADERBOARD_PK_VALUE,
                ":one": 1, ":k": kills,
            },
            ReturnValues="ALL_NEW",
        )["Attributes"]

        # 3) raise best_score (and the leaderboard sort key) only if improved
        best_score = _int(profile.get("best_score", 0))
        try:
            updated = self.table.update_item(
                Key={"PK": pk, "SK": PROFILE_SK},
                UpdateExpression="SET best_score = :s, GSI1SK = :s",
                ConditionExpression="attribute_not_exists(best_score) OR best_score < :s",
                ExpressionAttributeValues={":s": score},
                ReturnValues="ALL_NEW",
            )["Attributes"]
            best_score = _int(updated.get("best_score", score))
        except ClientError as err:
            if err.response["Error"]["Code"] != "ConditionalCheckFailedException":
                raise
            # existing best is higher — keep it

        games_played = _int(profile.get("games_played", 1))
        total_kills = _int(profile.get("total_kills", kills))

        # 4) evaluate + unlock achievements
        context = AchievementContext(
            run_score=score, run_kills=kills, survival_seconds=survival_seconds,
            best_score=best_score, total_kills=total_kills, games_played=games_played,
        )
        newly = self._unlock(pk, [a.id for a in evaluate(context)])

        return {
            "best_score": best_score,
            "games_played": games_played,
            "total_kills": total_kills,
            "newly_unlocked": newly,
        }

    def _unlock(self, pk: str, qualified_ids: list[str]) -> list[dict]:
        newly: list[dict] = []
        for ach_id in qualified_ids:
            definition = get_definition(ach_id)
            if definition is None:
                continue
            unlocked_at = _now_iso()
            try:
                self.table.put_item(
                    Item={
                        "PK": pk, "SK": f"ACH#{ach_id}", "type": "achievement",
                        "id": ach_id, "name": definition.name,
                        "unlocked_at": unlocked_at,
                    },
                    ConditionExpression="attribute_not_exists(SK)",
                )
                newly.append({"id": ach_id, "name": definition.name,
                              "unlocked_at": unlocked_at})
            except ClientError as err:
                if err.response["Error"]["Code"] != "ConditionalCheckFailedException":
                    raise
                # already unlocked — skip
        return newly

    # ------------------------------------------------------------------ #
    # Reads
    # ------------------------------------------------------------------ #
    def get_leaderboard(self, limit: int = 10) -> list[dict]:
        resp = self.table.query(
            IndexName=config.LEADERBOARD_INDEX,
            KeyConditionExpression="GSI1PK = :lb",
            ExpressionAttributeValues={":lb": config.LEADERBOARD_PK_VALUE},
            ScanIndexForward=False,  # highest score first
            Limit=limit,
        )
        return [
            {"nickname": item.get("nickname", "?"), "score": _int(item.get("best_score", 0))}
            for item in resp.get("Items", [])
        ]

    def get_achievements(self, nickname: str) -> list[dict]:
        resp = self.table.query(
            KeyConditionExpression="PK = :pk AND begins_with(SK, :ach)",
            ExpressionAttributeValues={":pk": f"PLAYER#{nickname}", ":ach": "ACH#"},
        )
        return [
            {"id": item["id"], "name": item["name"],
             "unlocked_at": item.get("unlocked_at")}
            for item in resp.get("Items", [])
        ]
