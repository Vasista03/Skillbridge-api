from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session
from starlette.exceptions import HTTPException as StarletteHTTPException

from .database import Base, SessionLocal, engine, get_db
from .routers import attendance, auth, batches, monitoring, reports, sessions

Base.metadata.create_all(bind=engine)

app = FastAPI(title="SkillBridge Attendance Monitoring API", version="1.0.0")


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(_: Request, exc: StarletteHTTPException):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_: Request, exc: RequestValidationError):
    return JSONResponse(status_code=422, content={"detail": exc.errors()})


@app.exception_handler(IntegrityError)
async def integrity_exception_handler(_: Request, __: IntegrityError):
    return JSONResponse(status_code=409, content={"detail": "Conflict with existing record"})


@app.exception_handler(SQLAlchemyError)
async def sqlalchemy_exception_handler(_: Request, __: SQLAlchemyError):
    return JSONResponse(status_code=500, content={"detail": "Database error"})


app.include_router(auth.router)
app.include_router(batches.router)
app.include_router(sessions.router)
app.include_router(attendance.router)
app.include_router(reports.router)
app.include_router(monitoring.router)


@app.get("/")
def root():
    return {"service": "SkillBridge Attendance Monitoring API", "status": "ok"}


@app.get("/health")
def health():
    return {"status": "healthy"}


@app.post("/seed")
def seed_database(db: Session = Depends(get_db)):
    """One-time seed endpoint for fresh deployments (no auth required).

    Drops all tables, recreates them, and populates with test data.
    Call this once after deploying to Render.
    """
    from .models import (
        ROLE_INSTITUTION,
        ROLE_MONITORING_OFFICER,
        ROLE_STUDENT,
        ROLE_TRAINER,
        Attendance,
        Batch,
        BatchStudent,
        BatchTrainer,
        Session,
        User,
    )
    from .auth import hash_password
    import random
    from datetime import date, time, timedelta

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        institutions = [
            User(
                name="Acme Institute",
                email="institution@example.com",
                hashed_password=hash_password("password123"),
                role=ROLE_INSTITUTION,
            ),
            User(
                name="Beta College",
                email="institution2@example.com",
                hashed_password=hash_password("password123"),
                role=ROLE_INSTITUTION,
            ),
        ]
        db.add_all(institutions)
        db.commit()
        for inst in institutions:
            db.refresh(inst)

        manager = User(
            name="Programme Manager",
            email="manager@example.com",
            hashed_password=hash_password("password123"),
            role="programme_manager",
        )
        monitor = User(
            name="Monitoring Officer",
            email="monitoring@example.com",
            hashed_password=hash_password("password123"),
            role=ROLE_MONITORING_OFFICER,
        )
        db.add_all([manager, monitor])
        db.commit()

        trainers = [
            User(
                name=f"Trainer {i}",
                email=f"trainer{i}@example.com",
                hashed_password=hash_password("password123"),
                role=ROLE_TRAINER,
                institution_id=institutions[(i - 1) % 2].id,
            )
            for i in range(1, 5)
        ]
        trainers[0].email = "trainer@example.com"
        db.add_all(trainers)
        db.commit()
        for t in trainers:
            db.refresh(t)

        students = []
        for i in range(1, 16):
            email = "student@example.com" if i == 1 else f"student{i}@example.com"
            students.append(
                User(
                    name=f"Student {i}",
                    email=email,
                    hashed_password=hash_password("password123"),
                    role=ROLE_STUDENT,
                    institution_id=institutions[(i - 1) % 2].id,
                )
            )
        db.add_all(students)
        db.commit()
        for s in students:
            db.refresh(s)

        batches = [
            Batch(name="Batch A - Python Basics", institution_id=institutions[0].id),
            Batch(name="Batch B - Data Science", institution_id=institutions[0].id),
            Batch(name="Batch C - Web Dev", institution_id=institutions[1].id),
        ]
        db.add_all(batches)
        db.commit()
        for b in batches:
            db.refresh(b)

        db.add_all(
            [
                BatchTrainer(batch_id=batches[0].id, trainer_id=trainers[0].id),
                BatchTrainer(batch_id=batches[0].id, trainer_id=trainers[1].id),
                BatchTrainer(batch_id=batches[1].id, trainer_id=trainers[1].id),
                BatchTrainer(batch_id=batches[2].id, trainer_id=trainers[2].id),
                BatchTrainer(batch_id=batches[2].id, trainer_id=trainers[3].id),
            ]
        )

        for s in students[:6]:
            db.add(BatchStudent(batch_id=batches[0].id, student_id=s.id))
        for s in students[5:11]:
            db.add(BatchStudent(batch_id=batches[1].id, student_id=s.id))
        for s in students[10:]:
            db.add(BatchStudent(batch_id=batches[2].id, student_id=s.id))

        db.commit()

        sessions = []
        base_date = date(2026, 5, 1)
        session_specs = [
            (batches[0], trainers[0], "Intro to Python", 0),
            (batches[0], trainers[0], "Data Types", 1),
            (batches[0], trainers[1], "Functions", 2),
            (batches[1], trainers[1], "NumPy Basics", 0),
            (batches[1], trainers[1], "Pandas Intro", 1),
            (batches[1], trainers[1], "Plotting", 2),
            (batches[2], trainers[2], "HTML & CSS", 0),
            (batches[2], trainers[3], "JavaScript", 1),
        ]
        for batch, trainer, title, day_offset in session_specs:
            sess = Session(
                batch_id=batch.id,
                trainer_id=trainer.id,
                title=title,
                date=base_date + timedelta(days=day_offset),
                start_time=time(10, 0),
                end_time=time(11, 0),
            )
            db.add(sess)
            sessions.append(sess)
        db.commit()
        for sess in sessions:
            db.refresh(sess)

        random.seed(42)
        statuses = ["present", "present", "present", "absent", "late"]
        for sess in sessions:
            enrolled = (
                db.query(User)
                .join(BatchStudent, BatchStudent.student_id == User.id)
                .filter(BatchStudent.batch_id == sess.batch_id)
                .all()
            )
            for student in enrolled:
                db.add(
                    Attendance(
                        session_id=sess.id,
                        student_id=student.id,
                        status=random.choice(statuses),
                    )
                )
        db.commit()

        return {
            "status": "seeded",
            "message": "Database reset and populated with test data",
            "test_accounts": [
                {"email": "student@example.com", "role": "student", "password": "password123"},
                {"email": "trainer@example.com", "role": "trainer", "password": "password123"},
                {"email": "institution@example.com", "role": "institution", "password": "password123"},
                {"email": "manager@example.com", "role": "programme_manager", "password": "password123"},
                {"email": "monitoring@example.com", "role": "monitoring_officer", "password": "password123"},
            ],
        }
    finally:
        db.close()
