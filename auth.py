"""Authentication helpers for Google Sign-In and JWT handling."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from pydantic import BaseModel


class AuthenticatedUser(BaseModel):
    """Minimal user profile stored in access tokens."""

    sub: str
    email: str
    name: Optional[str] = None
    picture: Optional[str] = None


CLIENT_ID = (
    os.getenv("GOOGLE_CLIENT_ID")
    or os.getenv("client_id")
    or os.getenv("CLIENT_ID")
)

JWT_SECRET = os.getenv("JWT_SECRET", "change-me")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_EXP_MINUTES = int(os.getenv("JWT_EXP_MINUTES", "1440"))

_google_request = google_requests.Request()
_bearer_scheme = HTTPBearer(auto_error=False)


def verify_google_credential(credential: str) -> AuthenticatedUser:
    """Validate a Google ID token and return the associated user profile."""

    try:
        if not CLIENT_ID:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="GOOGLE_CLIENT_ID is not configured",
            )

        payload = id_token.verify_oauth2_token(
            credential, _google_request, CLIENT_ID
        )
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001 - surface auth specific error
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Google credential",
        ) from exc

    return AuthenticatedUser(
        sub=payload["sub"],
        email=payload["email"],
        name=payload.get("name"),
        picture=payload.get("picture"),
    )


def _now_utc() -> datetime:
    return datetime.now(tz=timezone.utc)


def create_access_token(user: AuthenticatedUser) -> str:
    """Generate an application JWT for the authenticated user."""

    issued_at = _now_utc()
    expires_at = issued_at + timedelta(minutes=JWT_EXP_MINUTES)
    payload = {
        "sub": user.sub,
        "email": user.email,
        "name": user.name,
        "picture": user.picture,
        "iat": int(issued_at.timestamp()),
        "exp": int(expires_at.timestamp()),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> AuthenticatedUser:
    """Decode and validate a previously issued access token."""

    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError as exc:  # type: ignore[attr-defined]
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired",
        ) from exc
    except jwt.InvalidTokenError as exc:  # type: ignore[attr-defined]
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        ) from exc

    user_data = {
        key: payload.get(key)
        for key in ("sub", "email", "name", "picture")
    }
    if not user_data["sub"] or not user_data["email"]:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Malformed token payload",
        )
    return AuthenticatedUser(**user_data)


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
) -> AuthenticatedUser:
    """FastAPI dependency to retrieve the authenticated user from Authorization header."""

    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header missing",
        )
    token = credentials.credentials
    return decode_access_token(token)


__all__ = [
    "AuthenticatedUser",
    "create_access_token",
    "decode_access_token",
    "get_current_user",
    "verify_google_credential",
]

