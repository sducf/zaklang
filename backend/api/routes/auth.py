"""Authentication route surface.

Handlers remain intentionally unimplemented until the database-backed auth
service, password hashing, and token strategy are agreed upon.
"""

from typing import NoReturn

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/auth", tags=["auth"])


def not_implemented() -> NoReturn:
    raise HTTPException(
        status_code=501,
        detail="Authentication is not implemented yet",
    )


@router.post("/register", status_code=501, response_model=None)
def register() -> NoReturn:
    not_implemented()


@router.post("/login", status_code=501, response_model=None)
def login() -> NoReturn:
    not_implemented()


@router.get("/me", status_code=501, response_model=None)
def get_current_user() -> NoReturn:
    not_implemented()