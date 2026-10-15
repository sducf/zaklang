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

from api.schemas.auth import LoginRequest, TokenResponse, UserResponse
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


def _create_access_token(user: User) -> str:
    expires_in = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=expires_in)
    payload = {
        "sub": str(user.id),
        "role": user.role,
        "exp": expires_at,
    }
    return jwt.encode(
        payload,
        _jwt_secret(),
        algorithm=os.getenv("JWT_ALGORITHM", "HS256"),
    )


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

    return TokenResponse(access_token=_create_access_token(user))


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

    try:
        algorithm = os.getenv("JWT_ALGORITHM", "HS256")
        payload = jwt.decode(
            credentials.credentials,
            _jwt_secret(),
            algorithms=[algorithm],
        )
        user_id = UUID(payload["sub"])
    except (jwt.PyJWTError, KeyError, TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user
