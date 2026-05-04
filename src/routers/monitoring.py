from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session as DBSession

from ..database import get_db
from ..dependencies import get_monitoring_user
from ..models import Attendance, Batch, Session, User
from ..schemas import MonitoringAttendanceItem, MonitoringAttendanceResponse

router = APIRouter(prefix="/monitoring", tags=["monitoring"])


@router.api_route("/attendance", methods=["POST", "PUT", "DELETE", "PATCH"], include_in_schema=False)
async def monitoring_attendance_method_not_allowed(_: Request):
    raise HTTPException(status_code=status.HTTP_405_METHOD_NOT_ALLOWED, detail="Method not allowed")


@router.get("/attendance", response_model=MonitoringAttendanceResponse)
def monitoring_attendance(
    db: DBSession = Depends(get_db),
    _: User = Depends(get_monitoring_user),
):
    rows = (
        db.query(Attendance, Session, Batch, User)
        .join(Session, Session.id == Attendance.session_id)
        .join(Batch, Batch.id == Session.batch_id)
        .join(User, User.id == Attendance.student_id)
        .all()
    )

    institution_cache: dict[int, str] = {}

    def institution_name(institution_id: int) -> str:
        if institution_id not in institution_cache:
            inst = db.query(User).filter(User.id == institution_id).first()
            institution_cache[institution_id] = inst.name if inst else "Unknown"
        return institution_cache[institution_id]

    items = [
        MonitoringAttendanceItem(
            institution_id=batch.institution_id,
            institution_name=institution_name(batch.institution_id),
            batch_id=batch.id,
            batch_name=batch.name,
            session_id=session_obj.id,
            session_title=session_obj.title,
            student_id=student.id,
            student_name=student.name,
            status=attendance.status,
            marked_at=attendance.marked_at,
        )
        for attendance, session_obj, batch, student in rows
    ]

    return MonitoringAttendanceResponse(total_records=len(items), records=items)
