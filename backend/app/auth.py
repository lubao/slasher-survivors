"""Cognito-backed authentication.

Sign-up / login are proxied to a Cognito User Pool (the game talks only to this
backend, never to Cognito directly). Protected endpoints verify the Cognito
**ID token** against the pool's JWKS and derive the player's nickname from the
token, so a score can only be submitted for the authenticated user.
"""
from __future__ import annotations

import functools

import boto3
import jwt
from botocore.exceptions import ClientError
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient

from . import config

_bearer = HTTPBearer(auto_error=True)


@functools.lru_cache(maxsize=1)
def _cognito():
    return boto3.client("cognito-idp", region_name=config.COGNITO_REGION)


@functools.lru_cache(maxsize=1)
def _jwk_client() -> PyJWKClient:
    url = (f"https://cognito-idp.{config.COGNITO_REGION}.amazonaws.com/"
           f"{config.COGNITO_USER_POOL_ID}/.well-known/jwks.json")
    return PyJWKClient(url)


def _issuer() -> str:
    return (f"https://cognito-idp.{config.COGNITO_REGION}.amazonaws.com/"
            f"{config.COGNITO_USER_POOL_ID}")


# ---------------------------------------------------------------------- #
# Cognito operations
# ---------------------------------------------------------------------- #
def sign_up(email: str, password: str, nickname: str) -> None:
    """Register a new user. With the pre-signup trigger the user is
    auto-confirmed, so login works immediately afterwards."""
    try:
        _cognito().sign_up(
            ClientId=config.COGNITO_CLIENT_ID,
            Username=email,
            Password=password,
            UserAttributes=[
                {"Name": "email", "Value": email},
                {"Name": "nickname", "Value": nickname},
            ],
        )
    except ClientError as err:
        code = err.response["Error"]["Code"]
        message = err.response["Error"]["Message"]
        if code == "UsernameExistsException":
            raise HTTPException(status.HTTP_409_CONFLICT,
                                "An account with this email already exists")
        if code in ("InvalidPasswordException", "InvalidParameterException"):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, message)
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Sign up failed")


def log_in(email: str, password: str) -> dict:
    """Authenticate and return tokens + the player's nickname."""
    try:
        resp = _cognito().initiate_auth(
            ClientId=config.COGNITO_CLIENT_ID,
            AuthFlow="USER_PASSWORD_AUTH",
            AuthParameters={"USERNAME": email, "PASSWORD": password},
        )
    except ClientError as err:
        code = err.response["Error"]["Code"]
        if code in ("NotAuthorizedException", "UserNotFoundException"):
            raise HTTPException(status.HTTP_401_UNAUTHORIZED,
                                "Invalid email or password")
        if code == "UserNotConfirmedException":
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Account not confirmed")
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Login failed")

    result = resp["AuthenticationResult"]
    claims = verify_token(result["IdToken"])
    return {
        "id_token": result["IdToken"],
        "access_token": result["AccessToken"],
        "refresh_token": result.get("RefreshToken"),
        "expires_in": result.get("ExpiresIn", 3600),
        "nickname": claims.get("nickname") or claims.get("cognito:username") or email,
    }


# ---------------------------------------------------------------------- #
# Token verification
# ---------------------------------------------------------------------- #
def verify_token(token: str) -> dict:
    """Verify a Cognito ID token's signature, audience and issuer."""
    try:
        signing_key = _jwk_client().get_signing_key_from_jwt(token)
        return jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=config.COGNITO_CLIENT_ID,
            issuer=_issuer(),
        )
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token")


def get_current_user(
    creds: HTTPAuthorizationCredentials = Depends(_bearer),
) -> dict:
    """FastAPI dependency: resolve the authenticated player from a Bearer token."""
    claims = verify_token(creds.credentials)
    nickname = claims.get("nickname") or claims.get("cognito:username")
    if not nickname:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token missing nickname")
    return {"sub": claims.get("sub"), "nickname": nickname,
            "email": claims.get("email")}
