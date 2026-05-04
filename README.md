# SkillBridge Attendance Monitoring API

A FastAPI backend for tracking attendance across institutions, batches,
trainers, and students. Implements role-based access control, JWT auth,
and a separate scoped token for the Monitoring Officer role.

---

## 1. Live API base URL

`<FILL IN AFTER DEPLOYMENT — see "Deployment notes" below>`

If you are reviewing this before deployment is finished, run it locally
following section 2.

---

## 2. Local setup from scratch

Requires Python 3.11+ (developed and tested on Python 3.14).

```bash
# 1. Get into the project
cd submission

# 2. Create and activate a virtualenv
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Copy env template
cp .env.example .env
# (Windows PowerShell)
Copy-Item .env.example .env

# 5. Edit .env and fill in DATABASE_URL, JWT_SECRET_KEY, MONITORING_API_KEY
```

---

## 3. Environment variables

See `.env.example`. Required:

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | PostgreSQL connection string. SQLite also works. |
| `TEST_DATABASE_URL` | DB used by pytest (defaults to local SQLite file). |
| `JWT_SECRET_KEY` | HMAC secret for signing JWTs. |
| `JWT_ALGORITHM` | Defaults to `HS256`. |
| `ACCESS_TOKEN_EXPIRE_HOURS` | Normal login token lifetime (default 24). |
| `MONITORING_API_KEY` | Pre-shared key required to mint a monitoring token. |
| `MONITORING_TOKEN_EXPIRE_MINUTES` | Lifetime of the scoped monitoring token (default 60). |

`postgres://` and `postgresql://` URLs are auto-rewritten to use
`psycopg` (v3), so a Neon or Render-style URL works as-is.

---

## 4. Create tables

Tables are created automatically the first time the app starts (via
`Base.metadata.create_all`). No Alembic migrations were used to keep the
project small. To force a clean slate, drop the database/file and start the
app again, or run the seed script (which drops + recreates).

---

## 5. Seed the database

```bash
python -m scripts.seed
```

This drops all tables, recreates them, and inserts:

- 2 institutions
- 1 programme manager
- 1 monitoring officer
- 4 trainers
- 15 students
- 3 batches (with trainer assignments + student enrollments)
- 8 sessions
- attendance records (mix of present/absent/late)

---

## 6. Run tests

```bash
pytest
```

There are 24 tests across 5 files. They use a fresh SQLite database per
test (created via `tmp_path`), so they hit a real database — no mocks.

---

## 7. Test accounts (password for all: `password123`)

| Role | Email |
|---|---|
| student | `student@example.com` |
| trainer | `trainer@example.com` |
| institution | `institution@example.com` |
| programme_manager | `manager@example.com` |
| monitoring_officer | `monitoring@example.com` |

---

## 8. Curl examples for every endpoint

Replace `$BASE` with `http://localhost:8000` locally or your live URL.

### Run the API locally

```bash
uvicorn src.main:app --reload
```

### Setup

**Seed the database (first deployment only)**
```bash
curl -X POST $BASE/seed
```

Returns the 5 test account credentials. Call this once after deploying to Render.

### Auth

**Signup**
```bash
curl -X POST $BASE/auth/signup \
  -H "Content-Type: application/json" \
  -d '{"name":"Student One","email":"s1@example.com","password":"password123","role":"student","institution_id":null}'
```

**Login** (use this on a seeded DB to get tokens)
```bash
curl -X POST $BASE/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"student@example.com","password":"password123"}'
```

The response contains `access_token`. Use it with
`-H "Authorization: Bearer <token>"` in the calls below. Save tokens to
shell vars: `STUDENT=...`, `TRAINER=...`, `INSTITUTION=...`,
`MANAGER=...`, `MONITOR=...`.

**Monitoring scoped token** (Monitoring Officer JWT + pre-shared key)
```bash
curl -X POST $BASE/auth/monitoring-token \
  -H "Authorization: Bearer $MONITOR" \
  -H "Content-Type: application/json" \
  -d '{"key":"monitoring-secret-key"}'
```

### Batches

**Create a batch** (trainer or institution)
```bash
curl -X POST $BASE/batches \
  -H "Authorization: Bearer $TRAINER" \
  -H "Content-Type: application/json" \
  -d '{"name":"Batch A","institution_id":1}'
```

**Generate an invite** (trainer assigned to batch)
```bash
curl -X POST $BASE/batches/1/invite \
  -H "Authorization: Bearer $TRAINER"
```

**Student joins via invite**
```bash
curl -X POST $BASE/batches/join \
  -H "Authorization: Bearer $STUDENT" \
  -H "Content-Type: application/json" \
  -d '{"token":"<invite_token>"}'
```

### Sessions

```bash
curl -X POST $BASE/sessions \
  -H "Authorization: Bearer $TRAINER" \
  -H "Content-Type: application/json" \
  -d '{"batch_id":1,"title":"Python Basics","date":"2026-05-04","start_time":"10:00","end_time":"11:00"}'
```

### Attendance

```bash
curl -X POST $BASE/attendance/mark \
  -H "Authorization: Bearer $STUDENT" \
  -H "Content-Type: application/json" \
  -d '{"session_id":1,"status":"present"}'
```

### Reports

```bash
# Trainer: full attendance for a session
curl $BASE/sessions/1/attendance -H "Authorization: Bearer $TRAINER"

# Institution: summary for one batch
curl $BASE/batches/1/summary -H "Authorization: Bearer $INSTITUTION"

# Programme Manager: summary for one institution
curl $BASE/institutions/1/summary -H "Authorization: Bearer $MANAGER"

# Programme Manager: programme-wide summary
curl $BASE/programme/summary -H "Authorization: Bearer $MANAGER"
```

### Monitoring (scoped token only)

```bash
curl $BASE/monitoring/attendance -H "Authorization: Bearer $MONITOR_SCOPED"

# This must return 405:
curl -X POST $BASE/monitoring/attendance -H "Authorization: Bearer $MONITOR_SCOPED"
```

---

## 9. JWT payload structure (normal token)

```json
{
  "user_id": 1,
  "role": "student",
  "iat": 1717420800,
  "exp": 1717507200
}
```

`iat` and `exp` are integer Unix timestamps. Default lifetime: 24 hours.

## 10. JWT payload structure (monitoring token)

```json
{
  "user_id": 5,
  "role": "monitoring_officer",
  "scope": "monitoring:read",
  "iat": 1717420800,
  "exp": 1717424400
}
```

The presence of `scope: "monitoring:read"` is what distinguishes a
monitoring token from a normal login token. Default lifetime: 60 minutes.

---

## 11. Schema decisions

- **One `users` table for all roles** including `institution`. An
  "institution" is a `User` row whose `role = 'institution'`. This avoids
  a separate `institutions` table and keeps foreign keys uniform.
- **`users.institution_id`** (nullable) links a trainer/student to the
  institution they belong to.
- **`batches.institution_id`** is the user_id of the institution that
  owns the batch.
- **Two M2M tables** (`batch_trainers`, `batch_students`) instead of
  embedding membership lists — needed because a batch has multiple
  trainers and a student can join multiple batches.
- **Unique constraint on `(session_id, student_id)`** in `attendance`
  prevents duplicate marks at the database level.

### Explanation of `batch_trainers`

Many-to-many between batches and trainers. A batch can have multiple
trainers; a trainer can run multiple batches. Membership in this table
is what authorises a trainer to (a) generate invites for that batch,
(b) create sessions in that batch, and (c) read the session attendance
report. When a trainer creates a batch, they are auto-added to this
table.

### Explanation of `batch_invites`

Holds short-lived invite tokens generated by trainers. Each row records
the issuing trainer, the batch, expiry timestamp, and a `used` boolean.
We chose **one-time use** — the first student to redeem a token sets
`used = true` and any further attempts return `400 Bad Request`. Default
expiry is 24 hours.

### Explanation of the dual-token Monitoring Officer approach

Two separate tokens are involved:

1. A **normal login JWT** issued to the monitoring officer at
   `/auth/login`. This token has `role = "monitoring_officer"` but **no
   scope**. It cannot be used to call `/monitoring/attendance`.
2. A **scoped monitoring token** issued at `/auth/monitoring-token`.
   Issuing this token requires both the normal login JWT (to prove the
   caller is a monitoring officer) **and** a pre-shared `MONITORING_API_KEY`
   from the environment. The token carries `scope = "monitoring:read"`
   and is short-lived (60 min by default).

The dependency `get_monitoring_user` rejects any token that lacks
`scope = "monitoring:read"`, and `get_current_user` (used by every other
protected route) explicitly rejects any token that **has** that scope —
so the two token types cannot cross over.

---

## 12. Status of features

### What is fully working

- Signup + login with bcrypt password hashing
- JWT issuance and validation (HS256, `iat`/`exp` enforced)
- Role-based access control on every protected route
- Batch creation by trainer or institution
- Trainer-issued batch invite tokens (one-time, expiring)
- Student join by invite token
- Session creation by an assigned trainer
- Student attendance marking with enrollment check + duplicate handling
- `GET /sessions/{id}/attendance` with `not_marked` for absent students
- Batch / institution / programme summaries with present/absent/late breakdowns
- Dual-token monitoring flow + read-only `/monitoring/attendance`
- 405 enforcement on POST/PUT/DELETE/PATCH to `/monitoring/attendance`
- Seed script with the required 2 institutions / 4 trainers / 15 students / 3 batches / 8 sessions
- 24 pytest tests, all passing, all hitting a real (file-backed SQLite) DB

### What is partially working

- The `attendance_percentage` calculation treats `late` as **not present**
  (only `present` counts towards the percentage). If you want late to
  count partially (e.g. 0.5 weight) the formula in
  `src/routers/reports.py:_attendance_pct` needs adjustment.
- The institution endpoint scope check assumes one institution user per
  institution. If a future requirement allows multiple admin users per
  institution this needs widening.

### What was skipped

- Alembic migrations (used `create_all` instead — fine for an
  assignment, not for production).
- Pagination on `/monitoring/attendance` (returns all records).
- Refresh tokens / token revocation list.
- Rate limiting.
- Email verification on signup.

### One thing to improve with more time

Move heavy report aggregations into SQL (`GROUP BY status`) so we
don't load every attendance row into Python. The current code is
correct but O(records) in memory; for ~1M attendance rows it will
become noticeably slow.

### One security issue and how to fix it

The `MONITORING_API_KEY` is checked with a plain `==` string comparison
in `src/routers/auth.py`, which is technically vulnerable to a timing
side-channel. Fix: use `hmac.compare_digest(payload.key, settings.MONITORING_API_KEY)`.
The window in practice is small (key is short and the endpoint is
authenticated), but the fix is a one-liner and worth doing.

---

## 13. Deployment notes

Target: Render (free web service).

1. Push the `submission/` folder to a GitHub repo.
2. Create a new "Web Service" on Render, point at the repo.
3. **Build command:** `pip install -r requirements.txt`
4. **Start command:** `uvicorn src.main:app --host 0.0.0.0 --port $PORT`
5. **Environment:** add these variables in the Render dashboard:
   - `DATABASE_URL` — your Neon PostgreSQL connection string
   - `JWT_SECRET_KEY` — a random string (generate with `python -c "import secrets; print(secrets.token_urlsafe(64))"`)
   - `MONITORING_API_KEY` — a random string (generate with `python -c "import secrets; print(secrets.token_urlsafe(32))"`)
   - Leave the rest to defaults.
6. **After first deploy**, the service boots and tables auto-create. Seed the database via:
   ```bash
   curl -X POST https://your-service-name.onrender.com/seed
   ```
   (Render's free tier doesn't include shell access, so use the `/seed` HTTP endpoint instead.)
7. Verify it worked:
   ```bash
   curl https://your-service-name.onrender.com/health
   ```
8. Test a login:
   ```bash
   curl -X POST https://your-service-name.onrender.com/auth/login \
     -H "Content-Type: application/json" \
     -d '{"email":"student@example.com","password":"password123"}'
   ```

> **Deployment status:** The project has been tested locally (uvicorn boots,
> `/health` returns 200, all 24 pytest tests pass, `/seed` endpoint works).
> Update section 1 with the live Render URL once deployed.

---

## 14. Project layout

```
submission/
  CONTACT.txt
  README.md
  requirements.txt
  .env.example
  .gitignore
  src/
    main.py            FastAPI app + global error handlers
    config.py          Pydantic settings (env vars)
    database.py        SQLAlchemy engine + session factory
    models.py          ORM models + role/status constants
    schemas.py         Pydantic request/response models
    auth.py            Bcrypt + JWT helpers
    dependencies.py    get_current_user, require_roles, get_monitoring_user
    routers/
      auth.py          /auth/signup, /auth/login, /auth/monitoring-token
      batches.py       /batches, /batches/{id}/invite, /batches/join
      sessions.py      /sessions, /sessions/{id}/attendance
      attendance.py    /attendance/mark
      reports.py       /batches/{id}/summary, /institutions/{id}/summary, /programme/summary
      monitoring.py    /monitoring/attendance (+405 guard)
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
