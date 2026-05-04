from datetime import date, datetime, time
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field

Role = Literal["student", "trainer", "institution", "programme_manager", "monitoring_officer"]
AttendanceStatus = Literal["present", "absent", "late"]


class SignupRequest(BaseModel):
    name: str = Field(min_length=1)
    email: EmailStr
    password: str = Field(min_length=6)
    role: Role
    institution_id: Optional[int] = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class MonitoringTokenRequest(BaseModel):
    key: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: EmailStr
    role: Role


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class MonitoringTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in_minutes: int


class BatchCreate(BaseModel):
    name: str = Field(min_length=1)
    institution_id: int


class BatchOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    institution_id: int
    created_at: datetime


class InviteResponse(BaseModel):
    batch_id: int
    invite_token: str
    expires_at: datetime


class JoinRequest(BaseModel):
    token: str


class JoinResponse(BaseModel):
    batch_id: int
    batch_name: str
    student_id: int


class SessionCreate(BaseModel):
    batch_id: int
    title: str = Field(min_length=1)
    date: date
    start_time: time
    end_time: time


class SessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    batch_id: int
    trainer_id: int
    title: str
    date: date
    start_time: time
    end_time: time
    created_at: datetime


class AttendanceMarkRequest(BaseModel):
    session_id: int
    status: AttendanceStatus


class AttendanceOut(BaseModel):
    session_id: int
    student_id: int
    status: str
    marked_at: datetime


class SessionAttendanceItem(BaseModel):
    student_id: int
    student_name: str
    status: str
    marked_at: Optional[datetime] = None


class SessionAttendanceReport(BaseModel):
    session_id: int
    session_title: str
    batch_id: int
    attendance: list[SessionAttendanceItem]


class BatchSummary(BaseModel):
    batch_id: int
    total_students: int
    total_sessions: int
    present_count: int
    absent_count: int
    late_count: int
    attendance_percentage: float


class InstitutionBatchSummary(BaseModel):
    batch_id: int
    batch_name: str
    total_students: int
    total_sessions: int
    present_count: int
    absent_count: int
    late_count: int
    attendance_percentage: float


class InstitutionSummary(BaseModel):
    institution_id: int
    total_batches: int
    total_students: int
    total_sessions: int
    attendance_percentage: float
    batches: list[InstitutionBatchSummary]


class ProgrammeInstitutionBreakdown(BaseModel):
    institution_id: int
    institution_name: str
    total_batches: int
    total_students: int
    total_sessions: int
    attendance_percentage: float


class ProgrammeSummary(BaseModel):
    total_institutions: int
    total_batches: int
    total_students: int
    total_sessions: int
    total_attendance_records: int
    attendance_percentage: float
    institutions: list[ProgrammeInstitutionBreakdown]


class MonitoringAttendanceItem(BaseModel):
    institution_id: int
    institution_name: str
    batch_id: int
    batch_name: str
    session_id: int
    session_title: str
    student_id: int
    student_name: str
    status: str
    marked_at: datetime


class MonitoringAttendanceResponse(BaseModel):
    total_records: int
    records: list[MonitoringAttendanceItem]
