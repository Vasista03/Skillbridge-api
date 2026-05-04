from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException

from .database import Base, engine
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
