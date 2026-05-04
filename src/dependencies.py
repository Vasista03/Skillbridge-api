from typing import Iterable, Optional

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from .auth import decode_token
from .database import get_db
from .models import User


def _extract_bearer(request: Request) -> str:
    header = request.headers.get("Authorization")
    if not header or not header.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing or invalid Authorization header")
    return header.split(" ", 1)[1].strip()


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = _extract_bearer(request)
    payload = decode_token(token)
    if not payload or "user_id" not in payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

    if payload.get("scope") == "monitoring:read":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Monitoring token cannot be used here")

    user = db.query(User).filter(User.id == payload["user_id"]).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


def require_roles(*allowed: str):
    allowed_set = set(allowed)

    def checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed_set:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorised for this action")
        return user

    return checker


def get_monitoring_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = _extract_bearer(request)
    payload = decode_token(token)
    if not payload or payload.get("scope") != "monitoring:read":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Valid monitoring scoped token required")
    if payload.get("role") != "monitoring_officer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Monitoring role required")
    user = db.query(User).filter(User.id == payload["user_id"]).first()
    if not user or user.role != "monitoring_officer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Monitoring user not found")
    return user
