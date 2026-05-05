# SkillBridge Attendance Monitoring API

Backend REST API for programme attendance monitoring. Five user roles, JWT
authentication, role-based access control, batch membership via invite tokens,
session creation, attendance marking, reporting endpoints per role, and a
separate scoped token for read-only monitoring access.

No frontend. No QR codes. No face recognition. Just the backend, done properly.

---

## 1. Live API Base URL

```
https://skillbridge-api-jevk.onrender.com
```

Interactive docs (Swagger UI):

```
https://skillbridge-api-jevk.onrender.com/docs
```

Postman documentation:

```
https://documenter.getpostman.com/view/54527094/2sBXqMGeJJ
```

### Deployment Notes

Deployed on Render (free tier) backed by Neon PostgreSQL.

**What broke during deployment and how it was fixed:**

- `psycopg2-binary==2.9.9` has no pre-built wheel for Python 3.14. The build
  failed silently with a compiler error. Fixed by switching to
  `psycopg[binary]>=3.2.3` (psycopg v3) and adding a `_normalize_url()` helper
  in `database.py` that rewrites `postgresql://` to `postgresql+psycopg://`
  automatically.

- `passlib[bcrypt]` version conflicts with `bcrypt>=4.0`. Passlib wraps bcrypt
  and started raising `ValueError: password cannot be longer than 72 bytes`
  even for short passwords. Fixed by removing passlib entirely and calling
  `bcrypt.hashpw` / `bcrypt.checkpw` directly.

- Render free tier has no shell access. Could not run `python -m scripts.seed`
  after deploy. Added `POST /seed` as an HTTP endpoint that drops all tables,
  recreates them, and inserts demo data. One HTTP call replaces the missing
  shell.

- After the first push, `/seed` returned 404. The app had not redeployed yet.
  Pushed a trivial commit to trigger Render's automatic redeploy. Endpoint
  worked after that.

---

## 2. Local Setup

Assumes Python 3.11+ and pip are installed. Nothing else required.

```bash
cd submission
python -m venv .venv
```

**Windows PowerShell:**

```powershell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

**macOS / Linux:**

```bash
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` and set these values for a local run:

```env
DATABASE_URL=sqlite:///./app.db
JWT_SECRET_KEY=any-long-random-string-here
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_HOURS=24
MONITORING_API_KEY=monitoring-secret-key
MONITORING_TOKEN_EXPIRE_MINUTES=60
```

Start the API:

```bash
python -m uvicorn src.main:app --reload
```

The app creates tables automatically on startup. No migrations to run.

Seed demo data locally:

```bash
python -m scripts.seed
```

Run tests:

```bash
python -m pytest
```

---

## 3. Test Accounts

After seeding, all accounts use this password:

```
password123
```

| Role               | Email                     |
|--------------------|---------------------------|
| student            | student@example.com       |
| trainer            | trainer@example.com       |
| institution        | institution@example.com   |
| programme_manager  | manager@example.com       |
| monitoring_officer | monitoring@example.com    |

To seed the live deployment:

```bash
curl -X POST https://skillbridge-api-jevk.onrender.com/seed
```

---

## 4. Curl Examples For Every Endpoint

Set the base URL once:

```bash
BASE=https://skillbridge-api-jevk.onrender.com
```

For local testing:

```bash
BASE=http://localhost:8000
```

### Health check

```bash
curl $BASE/health
```

Expected:

```json
{"status":"healthy"}
```

### POST /auth/signup

```bash
curl -X POST $BASE/auth/signup \
  -H "Content-Type: application/json" \
  -d '{"name":"New Student","email":"new@example.com","password":"password123","role":"student","institution_id":null}'
```

Returns a JWT and the new user's public details. The hashed password is never
returned.

### POST /auth/login

```bash
curl -X POST $BASE/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"student@example.com","password":"password123"}'
```

Returns:

```json
{"access_token":"<JWT>","token_type":"bearer","user":{"id":1,"name":"Student 1","email":"student@example.com","role":"student"}}
```

Save the token for subsequent requests:

```bash
STUDENT=$(curl -sX POST $BASE/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"student@example.com","password":"password123"}' | python -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
```

Repeat for each role:

```bash
TRAINER=$(curl -sX POST $BASE/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"trainer@example.com","password":"password123"}' | python -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

INSTITUTION=$(curl -sX POST $BASE/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"institution@example.com","password":"password123"}' | python -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

MANAGER=$(curl -sX POST $BASE/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"manager@example.com","password":"password123"}' | python -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

MONITOR=$(curl -sX POST $BASE/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"monitoring@example.com","password":"password123"}' | python -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
```

### POST /auth/monitoring-token (obtaining the scoped token)

The monitoring officer first logs in normally to get `$MONITOR`, then exchanges
it together with the server-side API key for a short-lived scoped token:

```bash
SCOPED=$(curl -sX POST $BASE/auth/monitoring-token \
  -H "Authorization: Bearer $MONITOR" \
  -H "Content-Type: application/json" \
  -d '{"key":"monitoring-secret-key"}' | python -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
```

The scoped token payload contains `"scope": "monitoring:read"`. The normal
`$MONITOR` token does not have this field and will be rejected by
`GET /monitoring/attendance`.

### POST /batches

Allowed roles: `trainer`, `institution`.

```bash
curl -X POST $BASE/batches \
  -H "Authorization: Bearer $TRAINER" \
  -H "Content-Type: application/json" \
  -d '{"name":"Demo Batch","institution_id":1}'
```

When a trainer creates a batch, the trainer is automatically added to
`batch_trainers` so they can generate invites and create sessions immediately.

### POST /batches/{id}/invite

Allowed role: trainer assigned to that batch.

```bash
curl -X POST $BASE/batches/1/invite \
  -H "Authorization: Bearer $TRAINER"
```

Returns a one-time invite token string valid for 24 hours.

### POST /batches/join

Allowed role: `student`.

```bash
curl -X POST $BASE/batches/join \
  -H "Authorization: Bearer $STUDENT" \
  -H "Content-Type: application/json" \
  -d '{"token":"<INVITE_TOKEN>"}'
```

Reusing the token returns `400 Bad Request`. This is enforced by the `used`
flag on the `batch_invites` row.

### POST /sessions

Allowed role: trainer assigned to the target batch.

```bash
curl -X POST $BASE/sessions \
  -H "Authorization: Bearer $TRAINER" \
  -H "Content-Type: application/json" \
  -d '{"batch_id":1,"title":"Python Basics","date":"2026-05-10","start_time":"10:00","end_time":"11:00"}'
```

`trainer_id` is taken from the JWT, not from the request body.

### POST /attendance/mark

Allowed role: `student`. Student must be enrolled in the session's batch.

```bash
curl -X POST $BASE/attendance/mark \
  -H "Authorization: Bearer $STUDENT" \
  -H "Content-Type: application/json" \
  -d '{"session_id":1,"status":"present"}'
```

Allowed statuses: `present`, `absent`, `late`.

If the student marks the same session twice, the existing record is updated
rather than rejected. This avoids a confusing error for the common case of
correcting a mistake.

A student who is not enrolled in the session's batch gets `403 Forbidden`.

### GET /sessions/{id}/attendance

Allowed role: trainer assigned to the session's batch.

```bash
curl $BASE/sessions/1/attendance \
  -H "Authorization: Bearer $TRAINER"
```

Returns every student enrolled in the batch. Students who have not marked
attendance yet appear with `"status": "not_marked"` so the trainer can see
exactly who is missing.

### GET /batches/{id}/summary

Allowed role: institution that owns the batch.

```bash
curl $BASE/batches/1/summary \
  -H "Authorization: Bearer $INSTITUTION"
```

Returns total sessions, present/absent/late counts, and attendance percentage.

### GET /institutions/{id}/summary

Allowed role: `programme_manager`.

```bash
curl $BASE/institutions/1/summary \
  -H "Authorization: Bearer $MANAGER"
```

Returns per-batch breakdown for every batch owned by that institution.

### GET /programme/summary

Allowed role: `programme_manager`.

```bash
curl $BASE/programme/summary \
  -H "Authorization: Bearer $MANAGER"
```

Returns global summary with per-institution breakdown.

### GET /monitoring/attendance (requires scoped token)

```bash
curl $BASE/monitoring/attendance \
  -H "Authorization: Bearer $SCOPED"
```

Using the normal `$MONITOR` login token here returns `401 Unauthorized` because
the payload lacks `"scope": "monitoring:read"`.

### POST /monitoring/attendance (must return 405)

```bash
curl -X POST $BASE/monitoring/attendance \
  -H "Authorization: Bearer $SCOPED"
```

Expected:

```json
{"detail":"Method not allowed"}
```

PUT, DELETE, and PATCH on this path also return 405.

---

## 5. Schema Decisions

### batch_trainers

This is a many-to-many join table between batches and trainers. One batch can
have multiple trainers. One trainer can be assigned to multiple batches. A
simple `trainer_id` column on batches would have forced a one-to-one
relationship, which did not fit the spec.

Every trainer-guarded endpoint (`POST /batches/{id}/invite`, `POST /sessions`,
`GET /sessions/{id}/attendance`) checks `batch_trainers` to confirm the calling
trainer is actually assigned to that batch before proceeding.

When a trainer creates a batch, the API automatically inserts a row into
`batch_trainers` so the trainer can use their own batch immediately without a
separate assignment step.

### batch_invites

Stores URL-safe tokens generated when a trainer calls `POST /batches/{id}/invite`.
Each row tracks:

- `token` — random URL-safe string
- `batch_id` — which batch the token grants access to
- `created_by` — trainer's user ID
- `expires_at` — 24 hours from creation
- `used` — boolean, flipped to true on first successful join

The `used` flag enforces one-time use. When a student submits a token, the API
checks that `used = false` and `expires_at > now`. On success it sets `used =
true` and adds the student to `batch_students`. A second attempt with the same
token returns `400`.

### Dual-token approach for Monitoring Officer

The monitoring endpoint has stricter access than any other protected route.

Step 1 — the monitoring officer logs in at `POST /auth/login` and gets a normal
24-hour JWT. This is how all other roles authenticate.

Step 2 — the officer calls `POST /auth/monitoring-token` with both that normal
JWT and the server-side `MONITORING_API_KEY`. The API checks the role is
`monitoring_officer` and the key matches, then issues a second short-lived JWT
(60 minutes) that carries `"scope": "monitoring:read"` in its payload.

Step 3 — `GET /monitoring/attendance` is protected by a dependency that decodes
the token and explicitly checks for the scope field. A normal login token, even
from a monitoring officer, has no scope field and is rejected with 401.

This means stealing a monitoring officer's login token is not enough to reach
the monitoring endpoint. The attacker also needs `MONITORING_API_KEY`, which
lives only in the server environment.

---

## 6. Working Status

### Fully working

- Signup, login, JWT issued and validated on every protected request
- Password hashing with bcrypt (removed passlib, calls bcrypt directly)
- Role checks enforced server-side on every protected endpoint
- Batch creation with automatic trainer assignment
- One-time invite token generation and join
- Trainer session creation
- Student attendance marking with duplicate-update behaviour
- Batch enrollment check before attendance marking (403 if not enrolled)
- Session attendance report including not-yet-marked students
- Batch summary (present/absent/late counts and percentage)
- Institution summary with per-batch breakdown
- Programme summary with per-institution breakdown
- Monitoring officer dual-token flow
- Read-only monitoring attendance endpoint
- 405 for write methods on `/monitoring/attendance`
- Automated seed via `POST /seed` (required because Render free tier has no
  shell access)
- 24 passing tests using real SQLite databases, not mocked repositories

### Partially done / kept intentionally simple

- `attendance_percentage` counts only `present` records as attended. Students
  marked `late` are reported separately and do not count toward the percentage.
  This is a policy choice that could go either way; the code makes one
  consistent choice.

- Reports aggregate in Python by loading all attendance rows for a batch into
  memory and summing them. Correct for assignment-sized data. Would need SQL
  `GROUP BY` for production scale.

- The `/seed` endpoint is unauthenticated and destructive. Safe for demo; not
  safe for production.

### Skipped

- Alembic migrations (tables are created by `Base.metadata.create_all` on startup)
- Refresh tokens and token revocation
- Rate limiting
- Email verification
- Pagination on `/monitoring/attendance`
- Frontend, mobile app, dashboard
- QR codes, face recognition, geolocation, analytics

---

## 7. One Thing I'd Do Differently With More Time

Move the attendance calculations from Python into SQL.

Right now, `GET /batches/{id}/summary` works like this: load every attendance
row for the batch into a Python list, then loop and count. For assignment data
(a few hundred rows) this is fine.

If a batch had thousands of students across hundreds of sessions, the API would
load all of it into memory on every request. A single SQL query using
`COUNT(*) FILTER (WHERE status = 'present')` with `GROUP BY session_id` would
do the same work in the database without transferring rows over the wire.

The schema already supports this. The fix is entirely in the report endpoint
logic, not in the models. I left it as Python loops because it was easier to
read and verify during development.

---

## Project Layout

```
submission/
  CONTACT.txt
  README.md
  requirements.txt
  .env.example
  .gitignore
  src/
    main.py          # app entry point, exception handlers, routers, /seed
    config.py        # pydantic settings from environment
    database.py      # engine factory, URL normalisation, get_db dependency
    models.py        # User, Batch, BatchTrainer, BatchStudent, BatchInvite, Session, Attendance
    schemas.py       # pydantic request/response models
    auth.py          # hash_password, verify_password, create_access_token, create_monitoring_token
    dependencies.py  # get_current_user, require_roles, get_monitoring_user
    routers/
      auth.py
      batches.py
      sessions.py
      attendance.py
      reports.py
      monitoring.py
  scripts/
    seed.py
  tests/
    conftest.py
    test_auth.py
    test_sessions.py
    test_attendance.py
    test_monitoring.py
    test_security.py
```
