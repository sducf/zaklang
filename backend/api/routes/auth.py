"""Authentication HTTP routes."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from api.controllers.auth import (
    get_current_user_controller,
    login_controller,
    refresh_controller,
    register_controller,
)
from api.schemas.auth import (
    LoginRequest,
    RefreshRequest,
    TokenResponse,
    UserResponse,
)
from database.db import get_db
from database.models import User

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
def register(
    payload: LoginRequest,
    db: Session = Depends(get_db),
) -> UserResponse:
    return register_controller(payload, db)


@router.post("/login", response_model=TokenResponse)
def login(
    payload: LoginRequest,
    db: Session = Depends(get_db),
) -> TokenResponse:
    return login_controller(payload, db)


@router.post("/refresh", response_model=TokenResponse)
def refresh(
    payload: RefreshRequest,
    db: Session = Depends(get_db),
) -> TokenResponse:
    return refresh_controller(payload, db)


@router.get("/me", response_model=UserResponse)
def get_current_user(
    user: User = Depends(get_current_user_controller),
) -> UserResponse:
    return user