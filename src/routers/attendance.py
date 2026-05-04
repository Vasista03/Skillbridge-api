from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session as DBSession

from ..database import get_db
from ..dependencies import require_roles
from ..models import ROLE_STUDENT, Attendance, BatchStudent, Session, User
from ..schemas import AttendanceMarkRequest, AttendanceOut

router = APIRouter(prefix="/attendance", tags=["attendance"])


@router.post("/mark", response_model=AttendanceOut, status_code=201)
def mark_attendance(
    payload: AttendanceMarkRequest,
    db: DBSession = Depends(get_db),
    user: User = Depends(require_roles(ROLE_STUDENT)),
):
    session_obj = db.query(Session).filter(Session.id == payload.session_id).first()
    if not session_obj:
        raise HTTPException(status_code=404, detail="Session not found")

    enrolled = (
        db.query(BatchStudent)
        .filter(
            BatchStudent.batch_id == session_obj.batch_id,
            BatchStudent.student_id == user.id,
        )
        .first()
    )
    if not enrolled:
        raise HTTPException(status_code=403, detail="Student not enrolled in this batch")

    existing = (
        db.query(Attendance)
        .filter(Attendance.session_id == payload.session_id, Attendance.student_id == user.id)
        .first()
    )

    if existing:
        existing.status = payload.status
        existing.marked_at = datetime.utcnow()
        db.commit()
        db.refresh(existing)
        record = existing
    else:
        record = Attendance(
            session_id=payload.session_id,
            student_id=user.id,
            status=payload.status,
        )
        db.add(record)
        db.commit()
        db.refresh(record)

    return AttendanceOut(
        session_id=record.session_id,
        student_id=record.student_id,
        status=record.status,
        marked_at=record.marked_at,
    )
