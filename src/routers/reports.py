from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session as DBSession

from ..database import get_db
from ..dependencies import require_roles
from ..models import (
    ROLE_INSTITUTION,
    ROLE_PROGRAMME_MANAGER,
    Attendance,
    Batch,
    BatchStudent,
    Session,
    User,
)
from ..schemas import (
    BatchSummary,
    InstitutionBatchSummary,
    InstitutionSummary,
    ProgrammeInstitutionBreakdown,
    ProgrammeSummary,
)

router = APIRouter(tags=["reports"])


def _attendance_pct(present: int, total_records: int) -> float:
    if total_records == 0:
        return 0.0
    return round((present / total_records) * 100, 2)


def _summarize_batch(db: DBSession, batch: Batch) -> dict:
    total_students = (
        db.query(BatchStudent).filter(BatchStudent.batch_id == batch.id).count()
    )
    sessions_in_batch = db.query(Session).filter(Session.batch_id == batch.id).all()
    session_ids = [s.id for s in sessions_in_batch]
    total_sessions = len(session_ids)

    present_count = absent_count = late_count = 0
    if session_ids:
        records = db.query(Attendance).filter(Attendance.session_id.in_(session_ids)).all()
        for r in records:
            if r.status == "present":
                present_count += 1
            elif r.status == "absent":
                absent_count += 1
            elif r.status == "late":
                late_count += 1

    total_records = present_count + absent_count + late_count
    pct = _attendance_pct(present_count, total_records)

    return {
        "batch_id": batch.id,
        "batch_name": batch.name,
        "total_students": total_students,
        "total_sessions": total_sessions,
        "present_count": present_count,
        "absent_count": absent_count,
        "late_count": late_count,
        "attendance_percentage": pct,
    }


@router.get("/batches/{batch_id}/summary", response_model=BatchSummary)
def batch_summary(
    batch_id: int,
    db: DBSession = Depends(get_db),
    user: User = Depends(require_roles(ROLE_INSTITUTION)),
):
    batch = db.query(Batch).filter(Batch.id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    if batch.institution_id != user.id:
        raise HTTPException(status_code=403, detail="Not authorised for this batch")

    data = _summarize_batch(db, batch)
    return BatchSummary(
        batch_id=data["batch_id"],
        total_students=data["total_students"],
        total_sessions=data["total_sessions"],
        present_count=data["present_count"],
        absent_count=data["absent_count"],
        late_count=data["late_count"],
        attendance_percentage=data["attendance_percentage"],
    )


@router.get("/institutions/{institution_id}/summary", response_model=InstitutionSummary)
def institution_summary(
    institution_id: int,
    db: DBSession = Depends(get_db),
    user: User = Depends(require_roles(ROLE_PROGRAMME_MANAGER)),
):
    institution = db.query(User).filter(User.id == institution_id).first()
    if not institution or institution.role != ROLE_INSTITUTION:
        raise HTTPException(status_code=404, detail="Institution not found")

    batches = db.query(Batch).filter(Batch.institution_id == institution_id).all()
    batch_summaries = [_summarize_batch(db, b) for b in batches]

    total_students = sum(bs["total_students"] for bs in batch_summaries)
    total_sessions = sum(bs["total_sessions"] for bs in batch_summaries)
    total_present = sum(bs["present_count"] for bs in batch_summaries)
    total_records = sum(
        bs["present_count"] + bs["absent_count"] + bs["late_count"] for bs in batch_summaries
    )

    return InstitutionSummary(
        institution_id=institution_id,
        total_batches=len(batches),
        total_students=total_students,
        total_sessions=total_sessions,
        attendance_percentage=_attendance_pct(total_present, total_records),
        batches=[
            InstitutionBatchSummary(
                batch_id=bs["batch_id"],
                batch_name=bs["batch_name"],
                total_students=bs["total_students"],
                total_sessions=bs["total_sessions"],
                present_count=bs["present_count"],
                absent_count=bs["absent_count"],
                late_count=bs["late_count"],
                attendance_percentage=bs["attendance_percentage"],
            )
            for bs in batch_summaries
        ],
    )


@router.get("/programme/summary", response_model=ProgrammeSummary)
def programme_summary(
    db: DBSession = Depends(get_db),
    _: User = Depends(require_roles(ROLE_PROGRAMME_MANAGER)),
):
    institutions = db.query(User).filter(User.role == ROLE_INSTITUTION).all()
    breakdown = []
    grand_present = grand_records = 0
    grand_students = grand_sessions = grand_batches = 0

    for inst in institutions:
        batches = db.query(Batch).filter(Batch.institution_id == inst.id).all()
        summaries = [_summarize_batch(db, b) for b in batches]
        present = sum(s["present_count"] for s in summaries)
        records = sum(s["present_count"] + s["absent_count"] + s["late_count"] for s in summaries)
        students = sum(s["total_students"] for s in summaries)
        sessions = sum(s["total_sessions"] for s in summaries)

        breakdown.append(
            ProgrammeInstitutionBreakdown(
                institution_id=inst.id,
                institution_name=inst.name,
                total_batches=len(batches),
                total_students=students,
                total_sessions=sessions,
                attendance_percentage=_attendance_pct(present, records),
            )
        )
        grand_present += present
        grand_records += records
        grand_students += students
        grand_sessions += sessions
        grand_batches += len(batches)

    return ProgrammeSummary(
        total_institutions=len(institutions),
        total_batches=grand_batches,
        total_students=grand_students,
        total_sessions=grand_sessions,
        total_attendance_records=grand_records,
        attendance_percentage=_attendance_pct(grand_present, grand_records),
        institutions=breakdown,
    )
