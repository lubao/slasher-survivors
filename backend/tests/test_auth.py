"""Unit tests for app.auth using a mocked Cognito client."""
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError
from fastapi import HTTPException

from app import auth


def _client_error(code: str, message: str = "boom"):
    return ClientError({"Error": {"Code": code, "Message": message}}, "Op")


@patch("app.config.COGNITO_CLIENT_ID", "client-123")
@patch("app.auth._cognito")
def test_sign_up_calls_cognito_with_attributes(mock_cognito):
    cog = MagicMock()
    mock_cognito.return_value = cog

    auth.sign_up("a@b.com", "Passw0rd!", "alice")

    cog.sign_up.assert_called_once()
    kwargs = cog.sign_up.call_args.kwargs
    assert kwargs["ClientId"] == "client-123"
    assert kwargs["Username"] == "a@b.com"
    attrs = {a["Name"]: a["Value"] for a in kwargs["UserAttributes"]}
    assert attrs == {"email": "a@b.com", "nickname": "alice"}


@patch("app.auth._cognito")
def test_sign_up_duplicate_returns_409(mock_cognito):
    cog = MagicMock()
    cog.sign_up.side_effect = _client_error("UsernameExistsException")
    mock_cognito.return_value = cog

    with pytest.raises(HTTPException) as ei:
        auth.sign_up("a@b.com", "Passw0rd!", "alice")
    assert ei.value.status_code == 409


@patch("app.auth.verify_token", return_value={"nickname": "alice"})
@patch("app.auth._cognito")
def test_log_in_returns_tokens_and_nickname(mock_cognito, _verify):
    cog = MagicMock()
    cog.initiate_auth.return_value = {"AuthenticationResult": {
        "IdToken": "id.tok", "AccessToken": "acc.tok",
        "RefreshToken": "ref.tok", "ExpiresIn": 3600,
    }}
    mock_cognito.return_value = cog

    out = auth.log_in("a@b.com", "Passw0rd!")
    assert out["id_token"] == "id.tok"
    assert out["access_token"] == "acc.tok"
    assert out["nickname"] == "alice"


@patch("app.auth._cognito")
def test_log_in_bad_credentials_returns_401(mock_cognito):
    cog = MagicMock()
    cog.initiate_auth.side_effect = _client_error("NotAuthorizedException")
    mock_cognito.return_value = cog

    with pytest.raises(HTTPException) as ei:
        auth.log_in("a@b.com", "wrong")
    assert ei.value.status_code == 401
