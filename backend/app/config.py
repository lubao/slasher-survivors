"""Backend configuration, driven by environment variables.

These map directly onto what the CDK stacks (Task 5–6) will inject into the
Fargate task definition.
"""
import os

# DynamoDB single-table name (Global Table in production).
TABLE_NAME = os.environ.get("GAME_TABLE", "slasher-survivors")

# AWS region the task runs in. In multi-Region prod this is the local Region,
# used purely to tag where a score was written from ("就近寫入").
AWS_REGION = os.environ.get("AWS_REGION", "us-west-1")

# Optional custom endpoint for DynamoDB Local during development.
# e.g. http://dynamodb-local:8000 (docker compose) or http://localhost:8000
DDB_ENDPOINT = os.environ.get("DDB_ENDPOINT") or None

# GSI used for the global leaderboard query.
LEADERBOARD_INDEX = "GSI1"
LEADERBOARD_PK_VALUE = "LEADERBOARD"
