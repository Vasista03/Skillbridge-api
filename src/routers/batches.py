import secrets
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..dependencies import require_roles
from ..models import (
    ROLE_INSTITUTION,
    ROLE_STUDENT,
    ROLE_TRAINER,
    Batch,
    BatchInvite,
    BatchStudent,
    BatchTrainer,
    User,
)
from ..schemas import BatchCreate, BatchOut, InviteResponse, JoinRequest, JoinResponse

router = APIRouter(prefix="/batches", tags=["batches"])

INVITE_EXPIRY_HOURS = 24


@router.post("", response_model=BatchOut, status_code=201)
def create_batch(
    payload: BatchCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(ROLE_TRAINER, ROLE_INSTITUTION)),
):
    institution = db.query(User).filter(User.id == payload.institution_id).first()
    if not institution or institution.role != ROLE_INSTITUTION:
        raise HTTPException(status_code=404, detail="Institution not found")

    if user.role == ROLE_INSTITUTION and user.id != payload.institution_id:
        raise HTTPException(status_code=403, detail="Not authorised for this action")

    batch = Batch(name=payload.name, institution_id=payload.institution_id)
    db.add(batch)
    db.commit()
    db.refresh(batch)

    if user.role == ROLE_TRAINER:
        db.add(BatchTrainer(batch_id=batch.id, trainer_id=user.id))
        db.commit()

    return batch


@router.post("/{batch_id}/invite", response_model=InviteResponse, status_code=201)
def create_invite(
    batch_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(ROLE_TRAINER)),
):
    batch = db.query(Batch).filter(Batch.id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")

    is_assigned = (
        db.query(BatchTrainer)
        .filter(BatchTrainer.batch_id == batch_id, BatchTrainer.trainer_id == user.id)
        .first()
    )
    if not is_assigned:
        raise HTTPException(status_code=403, detail="Not authorised for this action")

    token = secrets.token_urlsafe(24)
    expires_at = datetime.utcnow() + timedelta(hours=INVITE_EXPIRY_HOURS)
    invite = BatchInvite(
        batch_id=batch_id,
        token=token,
        created_by=user.id,
        expires_at=expires_at,
        used=False,
    )
    db.add(invite)
    db.commit()
    db.refresh(invite)

    return InviteResponse(batch_id=batch_id, invite_token=token, expires_at=expires_at)


@router.post("/join", response_model=JoinResponse)
def join_batch(
    payload: JoinRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(ROLE_STUDENT)),
):
    invite = db.query(BatchInvite).filter(BatchInvite.token == payload.token).first()
    if not invite:
        raise HTTPException(status_code=404, detail="Invite token not found")

    if invite.used:
        raise HTTPException(status_code=400, detail="Invite token already used")

    if invite.expires_at < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Invite token expired")

    batch = db.query(Batch).filter(Batch.id == invite.batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")

    existing = (
        db.query(BatchStudent)
        .filter(BatchStudent.batch_id == batch.id, BatchStudent.student_id == user.id)
        .first()
    )
    if not existing:
        db.add(BatchStudent(batch_id=batch.id, student_id=user.id))

    invite.used = True
    db.commit()

    return JoinResponse(batch_id=batch.id, batch_name=batch.name, student_id=user.id)
