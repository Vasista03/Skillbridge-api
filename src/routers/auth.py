from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..auth import create_access_token, create_monitoring_token, hash_password, verify_password
from ..config import settings
from ..database import get_db
from ..dependencies import require_roles
from ..models import ROLE_INSTITUTION, ROLE_MONITORING_OFFICER, User
from ..schemas import (
    LoginRequest,
    MonitoringTokenRequest,
    MonitoringTokenResponse,
    SignupRequest,
    TokenResponse,
    UserOut,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def signup(payload: SignupRequest, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(status_code=409, detail="Email already registered")

    if payload.institution_id is not None:
        institution = db.query(User).filter(User.id == payload.institution_id).first()
        if not institution or institution.role != ROLE_INSTITUTION:
            raise HTTPException(status_code=404, detail="Institution not found")

    user = User(
        name=payload.name,
        email=payload.email,
        hashed_password=hash_password(payload.password),
        role=payload.role,
        institution_id=payload.institution_id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(user_id=user.id, role=user.role)
    return TokenResponse(access_token=token, user=UserOut.model_validate(user))


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = create_access_token(user_id=user.id, role=user.role)
    return TokenResponse(access_token=token, user=UserOut.model_validate(user))


@router.post("/monitoring-token", response_model=MonitoringTokenResponse)
def monitoring_token(
    payload: MonitoringTokenRequest,
    user: User = Depends(require_roles(ROLE_MONITORING_OFFICER)),
):
    if payload.key != settings.MONITORING_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid monitoring API key")

    token = create_monitoring_token(user_id=user.id)
    return MonitoringTokenResponse(
        access_token=token, expires_in_minutes=settings.MONITORING_TOKEN_EXPIRE_MINUTES
    )
