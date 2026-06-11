"""Shared test fixtures.

Uses moto to mock DynamoDB in-process, so tests need neither real AWS nor a
running DynamoDB Local container.
"""
import os

import pytest

# Ensure boto3 has (fake) credentials and no real endpoint before importing app.
os.environ.setdefault("AWS_ACCESS_KEY_ID", "testing")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "testing")
os.environ.setdefault("AWS_DEFAULT_REGION", "us-west-1")
os.environ["AWS_REGION"] = "us-west-1"
os.environ.pop("DDB_ENDPOINT", None)

from moto import mock_aws  # noqa: E402


@pytest.fixture
def repo():
    from app import config
    from app.db import Repository
    with mock_aws():
        r = Repository(table_name=config.TABLE_NAME, region="us-west-1",
                       endpoint_url=None)
        r.ensure_table()
        yield r


@pytest.fixture
def client(repo):
    from fastapi.testclient import TestClient

    from app.main import app, get_repository
    app.dependency_overrides[get_repository] = lambda: repo
    yield TestClient(app)
    app.dependency_overrides.clear()
