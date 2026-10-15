"""Authentication controllers and bearer-token dependencies."""

import os
from datetime import datetime, timedelta, timezone
from typing import Annotated
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pwdlib import PasswordHash
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from api.schemas.auth import (
    LoginRequest,
    RefreshRequest,
    TokenResponse,
    UserResponse,
)
from database.db import get_db
from database.models import User

password_hash = PasswordHash.recommended()
bearer_scheme = HTTPBearer(auto_error=False)


def _jwt_secret() -> str:
    secret = os.getenv("JWT_SECRET_KEY", "")
    if not secret:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="JWT_SECRET_KEY is not configured",
        )
    return secret


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _create_token(user: User, token_type: str, lifetime: timedelta) -> str:
    payload = {
        "sub": str(user.id),
        "role": user.role,
        "type": token_type,
        "exp": datetime.now(timezone.utc) + lifetime,
    }
    return jwt.encode(
        payload,
        _jwt_secret(),
        algorithm=os.getenv("JWT_ALGORITHM", "HS256"),
    )


def _issue_tokens(user: User) -> TokenResponse:
    access_minutes = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
    refresh_days = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))
    return TokenResponse(
        access_token=_create_token(
            user, "access", timedelta(minutes=access_minutes)
        ),
        refresh_token=_create_token(
            user, "refresh", timedelta(days=refresh_days)
        ),
    )


def _user_from_token(token: str, token_type: str, db: Session) -> User:
    """Decode a token of the expected type and load its user, or raise 401."""
    invalid = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        algorithm = os.getenv("JWT_ALGORITHM", "HS256")
        payload = jwt.decode(token, _jwt_secret(), algorithms=[algorithm])
        user_id = UUID(payload["sub"])
    except (jwt.PyJWTError, KeyError, TypeError, ValueError) as exc:
        raise invalid from exc

    # An access token must not work as a refresh token, and vice versa.
    if payload.get("type") != token_type:
        raise invalid

    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise invalid
    return user


def register_controller(payload: LoginRequest, db: Session) -> UserResponse:
    email = _normalize_email(payload.email)
    existing_user = db.query(User).filter(User.email == email).first()
    if existing_user is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        )

    user = User(
        email=email,
        password_hash=password_hash.hash(payload.password),
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        ) from exc

    db.refresh(user)
    return UserResponse.model_validate(user)


def login_controller(payload: LoginRequest, db: Session) -> TokenResponse:
    email = _normalize_email(payload.email)
    user = db.query(User).filter(User.email == email).first()
    if user is None or not password_hash.verify(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return _issue_tokens(user)


def refresh_controller(payload: RefreshRequest, db: Session) -> TokenResponse:
    """Exchange a valid refresh token for a new access and refresh token."""
    user = _user_from_token(payload.refresh_token, "refresh", db)
    return _issue_tokens(user)


def get_current_user_controller(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(bearer_scheme),
    ],
    db: Session = Depends(get_db),
) -> User:
    """Resolve the bearer token to a database user."""
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return _user_from_token(credentials.credentials, "access", db)
