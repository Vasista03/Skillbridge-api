"""Seed script: populates a fresh database with realistic demo data.

Run from the submission folder:
    python -m scripts.seed

Creates:
    - 2 institutions
    - 1 programme manager
    - 1 monitoring officer
    - 4 trainers
    - 15 students
    - 3 batches (with trainer + student assignments)
    - 8 sessions
    - attendance records across present/absent/late
"""

from __future__ import annotations

import os
import random
import sys
from datetime import date, time, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.auth import hash_password  # noqa: E402
from src.database import Base, SessionLocal, engine  # noqa: E402
from src.models import (  # noqa: E402
    Attendance,
    Batch,
    BatchStudent,
    BatchTrainer,
    Session,
    User,
)

PASSWORD = "password123"


def reset_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def seed():
    reset_database()
    db = SessionLocal()
    try:
        institutions = [
            User(name="Acme Institute", email="institution@example.com", hashed_password=hash_password(PASSWORD), role="institution"),
            User(name="Beta College", email="institution2@example.com", hashed_password=hash_password(PASSWORD), role="institution"),
        ]
        db.add_all(institutions)
        db.commit()
        for inst in institutions:
            db.refresh(inst)

        manager = User(name="Programme Manager", email="manager@example.com", hashed_password=hash_password(PASSWORD), role="programme_manager")
        monitor = User(name="Monitoring Officer", email="monitoring@example.com", hashed_password=hash_password(PASSWORD), role="monitoring_officer")
        db.add_all([manager, monitor])
        db.commit()

        trainers = [
            User(name=f"Trainer {i}", email=f"trainer{i}@example.com", hashed_password=hash_password(PASSWORD), role="trainer", institution_id=institutions[(i - 1) % 2].id)
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
                    hashed_password=hash_password(PASSWORD),
                    role="student",
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

        db.add_all([
            BatchTrainer(batch_id=batches[0].id, trainer_id=trainers[0].id),
            BatchTrainer(batch_id=batches[0].id, trainer_id=trainers[1].id),
            BatchTrainer(batch_id=batches[1].id, trainer_id=trainers[1].id),
            BatchTrainer(batch_id=batches[2].id, trainer_id=trainers[2].id),
            BatchTrainer(batch_id=batches[2].id, trainer_id=trainers[3].id),
        ])

        for s in students[:6]:
            db.add(BatchStudent(batch_id=batches[0].id, student_id=s.id))
        for s in students[5:11]:
            db.add(BatchStudent(batch_id=batches[1].id, student_id=s.id))
        for s in students[10:]:
            db.add(BatchStudent(batch_id=batches[2].id, student_id=s.id))

        db.commit()

        sessions: list[Session] = []
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

        print("Seed complete.")
        print("Test accounts (password: password123):")
        print("  student@example.com")
        print("  trainer@example.com")
        print("  institution@example.com")
        print("  manager@example.com")
        print("  monitoring@example.com")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
