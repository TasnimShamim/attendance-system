# Employee Attendance & Analytics API

FastAPI + PyMongo, Python 3.11+, MongoDB 6.0+ (7.0 recommended). Implements all twelve method/path combinations in `openapi.yaml`, including IST overnight shifts, atomic punches/corrections, stored-value analytics, tie-aware ranking, daily gap filling and executionStats explain.

## Run

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
# Set MONGO_URI and MONGO_DB in .env, or export them in your shell.
uvicorn app.main:app --port 8000
```

MongoDB must be reachable before startup. Indexes are created automatically and idempotently, without dropping existing data. `/health` pings MongoDB; `/docs` provides interactive API documentation. Real environment variables override `.env`. Optionally run `python sample_seed.py` against a disposable local database: it **deletes existing employees and attendance_logs** before loading samples.

## Structure

```text
app/
  main.py                 application startup and readiness
  database.py             connection and startup indexes
  routes/                 employees, attendance, analytics and admin HTTP routes
  services/               CRUD, time rules, aggregation builders and explain
  handlers/               response serialization and database error handling
  validators/             request models, calendars and pagination bounds
  middleware/             request correlation header
```

Application code is modular as requested. **This differs from the assignment's requirement to put all code in app/main.py.** The prescribed launch command still works, but a submission must include the entire `app/` directory. The original API and stored-data contracts remain in `openapi.yaml` and `DATA_MODEL.md`. Corrections and punch-outs use an internal `_version` field for optimistic concurrency; it is never exposed in attendance responses.

## Tests

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -m 'not integration'
TEST_MONGO_URI=mongodb://localhost:27017 python -m pytest -m 'integration and not performance'
TEST_MONGO_URI=mongodb://localhost:27017 RUN_PERFORMANCE=1 python -m pytest -m performance
```

Integration tests create and remove a uniquely named temporary database; the MongoDB user must have permission to do so. They verify real pipelines, concurrency, nested history timestamps, stored metrics, no-log employees, mid-month joiners, weekends, gap filling, ranks and index plans. The opt-in performance check seeds 100000 records and checks the required execution plans. No test uses or clears the configured application database.

Examples:

See [API_CURL.md](API_CURL.md) for ordered curl commands covering every endpoint, all five explain variants, expected responses, and error cases against a disposable database.

```bash
curl 'http://localhost:8000/analytics/employees/EMP0001/monthly?month=2026-07'
curl 'http://localhost:8000/analytics/departments/Engineering/trend?from=2026-07-01&to=2026-07-31'
curl 'http://localhost:8000/admin/explain/late_leaderboard?month=2026-07&limit=10'
```

Explain uses the same builders, hints, filters and pagination as real queries. Its `explain` field preserves MongoDB output using Extended JSON for BSON-only types.

## Validation status and submission

All Python files passed compilation, and 20 isolated time-rule checks passed (with only the unavailable FastAPI exception import substituted). These checks are not a replacement for the full test suite. Full tests, a clean runtime start and MongoDB execution plans could not be verified there: PyPI DNS resolution failed, MongoDB was not installed and Docker daemon access was denied. Run the commands above against MongoDB before submission; index hints are not a substitute for measured explain results.

`REVIEW.md` lists starter defects and fixes; `DECISIONS.md` answers the five design questions. Submit the full application and requirements in a public Git repository, excluding `.env`, secrets, virtual environments, test databases and Dockerfiles. Repository publishing and deadline submission have not been performed.
