"""Unit tests for app.auth using a mocked Cognito client."""
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError
from fastapi import HTTPException

from app import auth


def _client_error(code: str, message: str = "boom"):
    return ClientError({"Error": {"Code": code, "Message": message}}, "Op")


@patch("app.config.COGNITO_USER_POOL_ID", "pool-123")
@patch("app.config.COGNITO_CLIENT_ID", "client-123")
@patch("app.auth._cognito")
def test_sign_up_calls_cognito_with_attributes(mock_cognito):
    cog = MagicMock()
    mock_cognito.return_value = cog

    auth.sign_up("a@b.com", "Passw0rd!", "alice")

    cog.admin_create_user.assert_called_once()
    kwargs = cog.admin_create_user.call_args.kwargs
    assert kwargs["UserPoolId"] == "pool-123"
    assert kwargs["Username"] == "a@b.com"
    assert kwargs["MessageAction"] == "SUPPRESS"
    attrs = {a["Name"]: a["Value"] for a in kwargs["UserAttributes"]}
    assert attrs["email"] == "a@b.com"
    assert attrs["nickname"] == "alice"

    cog.admin_set_user_password.assert_called_once()
    pw_kwargs = cog.admin_set_user_password.call_args.kwargs
    assert pw_kwargs["UserPoolId"] == "pool-123"
    assert pw_kwargs["Username"] == "a@b.com"
    assert pw_kwargs["Password"] == "Passw0rd!"
    assert pw_kwargs["Permanent"] is True


@patch("app.auth._cognito")
def test_sign_up_duplicate_returns_409(mock_cognito):
    cog = MagicMock()
    cog.admin_create_user.side_effect = _client_error("UsernameExistsException")
    mock_cognito.return_value = cog

    with pytest.raises(HTTPException) as ei:
        auth.sign_up("a@b.com", "Passw0rd!", "alice")
    assert ei.value.status_code == 409


@patch("app.auth.verify_token", return_value={"nickname": "alice"})
@patch("app.auth._cognito")
def test_log_in_returns_tokens_and_nickname(mock_cognito, _verify):
    cog = MagicMock()
    cog.admin_initiate_auth.return_value = {"AuthenticationResult": {
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
    cog.admin_initiate_auth.side_effect = _client_error("NotAuthorizedException")
    mock_cognito.return_value = cog

    with pytest.raises(HTTPException) as ei:
        auth.log_in("a@b.com", "wrong")
    assert ei.value.status_code == 401
