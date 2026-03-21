"""
FastAPI dependency for JWT authentication.

Replaces Flask-JWT-Extended's @jwt_required() + get_jwt_identity() with
a single Depends(get_current_user) that returns the authenticated user_id.

Error codes match the originals so the Android app needs no changes:
  TOKEN_EXPIRED        — access token has expired (trigger refresh)
  TOKEN_INVALID        — malformed / wrong signature
  UNAUTHORIZED         — Authorization header missing
  REFRESH_TOKEN_REUSED — token has been revoked (force logout)
"""

import logging
from fastapi import Header, HTTPException
from jose import jwt, JWTError, ExpiredSignatureError

from app.config import settings

logger = logging.getLogger(__name__)


def _decode_token(token: str) -> dict:
    """Decode and validate a JWT. Raises HTTPException on any failure."""
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=["HS256"],
        )
        return payload
    except ExpiredSignatureError:
        raise HTTPException(
            status_code=401,
            detail={"code": "TOKEN_EXPIRED",
                    "message": "Your session has expired. Please refresh your token."},
        )
    except JWTError:
        raise HTTPException(
            status_code=401,
            detail={"code": "TOKEN_INVALID",
                    "message": "Invalid or malformed token. Please log in again."},
        )


def decode_token_lenient(token: str) -> dict:
    """
    Decode a token WITHOUT enforcing expiry — used by the /refresh endpoint
    so it can extract the JTI/sub even from an already-expired refresh token
    and check whether it has been revoked before issuing a new pair.
    """
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=["HS256"],
            options={"verify_exp": False},
        )
        return payload
    except JWTError:
        raise HTTPException(
            status_code=401,
            detail={"code": "REFRESH_TOKEN_INVALID",
                    "message": "Invalid refresh token."},
        )


def get_current_user(authorization: str = Header(...)) -> str:
    """
    FastAPI dependency — extracts and validates the Bearer access token.

    Usage:
        @router.get("/me")
        def get_me(user_id: str = Depends(get_current_user)):
            ...

    Returns the authenticated user's UUID string.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail={"code": "UNAUTHORIZED",
                    "message": "Authentication token is required."},
        )

    token = authorization.replace("Bearer ", "", 1)
    payload = _decode_token(token)

    # Check revocation (only refresh tokens are stored — access tokens are
    # short-lived so we skip the DB lookup on every request).
    token_type = payload.get("type", "access")
    if token_type == "refresh":
        jti = payload.get("jti")
        if jti:
            from sqlalchemy import select
            from app.models.revoked_token import RevokedToken
            from app.database import ScopedSession
            if ScopedSession.scalar(select(RevokedToken).where(RevokedToken.jti == jti)):
                raise HTTPException(
                    status_code=401,
                    detail={"code": "REFRESH_TOKEN_REUSED",
                            "message": "Token has been revoked. Please log in again."},
                )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=401,
            detail={"code": "TOKEN_INVALID",
                    "message": "Invalid or malformed token."},
        )

    return user_id
