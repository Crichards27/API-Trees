import hashlib
import secrets

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Team
from app.config import settings


def generate_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(
        token.encode("utf-8")
    ).hexdigest()


def get_authenticated_team(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> Team:

    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header required.",
        )

    scheme, separator, token = authorization.partition(" ")

    if (
        separator != " "
        or scheme.lower() != "bearer"
        or not token
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Use Authorization: Bearer <token>",
        )

    token_hash = hash_token(token)

    team = db.scalar(
        select(Team).where(
            Team.token == token_hash
        )
    )

    if team is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid team token.",
        )

    return team


def require_admin(
    authorization: str | None = Header(default=None),
) -> None:

    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin authorization required.",
        )

    scheme, separator, token = authorization.partition(" ")

    if (
        separator != " "
        or scheme.lower() != "bearer"
        or not token
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Use Authorization: Bearer <admin-token>",
        )

    if not secrets.compare_digest(
        token,
        settings.admin_token,
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid admin token.",
        )