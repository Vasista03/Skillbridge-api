from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session as DBSession

from ..database import get_db
from ..dependencies import require_roles
from ..models import (
    ROLE_TRAINER,
    Attendance,
    Batch,
    BatchStudent,
    BatchTrainer,
    Session,
    User,
)
from ..schemas import (
    SessionAttendanceItem,
    SessionAttendanceReport,
    SessionCreate,
    SessionOut,
)

router = APIRouter(tags=["sessions"])


@router.post("/sessions", response_model=SessionOut, status_code=201)
def create_session(
    payload: SessionCreate,
    db: DBSession = Depends(get_db),
    user: User = Depends(require_roles(ROLE_TRAINER)),
):
    batch = db.query(Batch).filter(Batch.id == payload.batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")

    if payload.end_time <= payload.start_time:
        raise HTTPException(status_code=422, detail="end_time must be after start_time")

    is_assigned = (
        db.query(BatchTrainer)
        .filter(BatchTrainer.batch_id == payload.batch_id, BatchTrainer.trainer_id == user.id)
        .first()
    )
    if not is_assigned:
        raise HTTPException(status_code=403, detail="Trainer not assigned to this batch")

    session_obj = Session(
        batch_id=payload.batch_id,
        trainer_id=user.id,
        title=payload.title,
        date=payload.date,
        start_time=payload.start_time,
        end_time=payload.end_time,
    )
    db.add(session_obj)
    db.commit()
    db.refresh(session_obj)
    return session_obj


@router.get("/sessions/{session_id}/attendance", response_model=SessionAttendanceReport)
def session_attendance(
    session_id: int,
    db: DBSession = Depends(get_db),
    user: User = Depends(require_roles(ROLE_TRAINER)),
):
    session_obj = db.query(Session).filter(Session.id == session_id).first()
    if not session_obj:
        raise HTTPException(status_code=404, detail="Session not found")

    is_assigned = (
        db.query(BatchTrainer)
        .filter(BatchTrainer.batch_id == session_obj.batch_id, BatchTrainer.trainer_id == user.id)
        .first()
    )
    if not is_assigned and session_obj.trainer_id != user.id:
        raise HTTPException(status_code=403, detail="Not authorised for this session")

    students = (
        db.query(User)
        .join(BatchStudent, BatchStudent.student_id == User.id)
        .filter(BatchStudent.batch_id == session_obj.batch_id)
        .all()
    )

    attendance_rows = {
        a.student_id: a
        for a in db.query(Attendance).filter(Attendance.session_id == session_id).all()
    }

    items: list[SessionAttendanceItem] = []
    for student in students:
        record = attendance_rows.get(student.id)
        items.append(
            SessionAttendanceItem(
                student_id=student.id,
                student_name=student.name,
                status=record.status if record else "not_marked",
                marked_at=record.marked_at if record else None,
            )
        )

    return SessionAttendanceReport(
        session_id=session_obj.id,
        session_title=session_obj.title,
        batch_id=session_obj.batch_id,
        attendance=items,
    )
