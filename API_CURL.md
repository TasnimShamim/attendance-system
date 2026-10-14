# Manual API tests

Start MongoDB, install dependencies, and run the API in one terminal:

```bash
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
export MONGO_URI='mongodb://localhost:27017'
export MONGO_DB='attendance_manual_test'
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Use a disposable database. The following commands create one employee and correct its attendance. They require no authentication. Run them in order in another terminal; `-i` shows the HTTP status and response headers. Repeating employee creation or punch-in returns 409; use a fresh employee code for another run. All timestamps are epoch milliseconds, and the attendance date is in IST.

```bash
BASE='http://127.0.0.1:8000'
EMP='EMP990001'

# Readiness: 200 when MongoDB is reachable.
curl -i "$BASE/health"

# Create employee: 201.
curl -i -X POST "$BASE/employees" -H 'Content-Type: application/json' \
  -d "{\"emp_code\":\"$EMP\",\"name\":\"Manual Tester\",\"email\":\"manual@example.com\",\"department\":\"ManualQA\",\"shift_start\":\"09:30\",\"shift_end\":\"18:30\",\"joined_on\":\"2026-07-01\"}"

# List employees, with department and pagination: 200.
curl -i "$BASE/employees?department=ManualQA&page=1&page_size=20"

# Punch in July 6 at 09:45 IST: 201, late_minutes=15.
curl -i -X POST "$BASE/attendance/punch-in" -H 'Content-Type: application/json' \
  -d "{\"emp_code\":\"$EMP\",\"punched_at\":1783311300000,\"status\":\"PRESENT\"}"

# Punch out July 6 at 19:00 IST: 200, work_hours=9.25, overtime_minutes=30.
curl -i -X POST "$BASE/attendance/punch-out" -H 'Content-Type: application/json' \
  -d "{\"emp_code\":\"$EMP\",\"punched_at\":1783344600000}"

# List attendance with all supported filters: 200.
curl -i "$BASE/attendance?emp_code=$EMP&date_from=2026-07-01&date_to=2026-07-31&status=PRESENT&page=1&page_size=20"

# Correct punch-in to 09:30 IST: 200, late_minutes=0, work_hours=9.5,
# and one history entry containing actual changes.
curl -i -X PATCH "$BASE/attendance/$EMP/2026-07-06" -H 'Content-Type: application/json' \
  -d '{"punch_in":1783310400000,"reason":"Correct biometric clock","regularized_by":"manual.qa"}'

# Monthly metrics: 200, working_days=23, present_days=1, attendance_pct=4.35.
curl -i "$BASE/analytics/employees/$EMP/monthly?month=2026-07"

# Department summary: 200.
curl -i "$BASE/analytics/departments/summary?month=2026-07&department=ManualQA"

# Late leaderboard: 200, empty after the correction above.
curl -i "$BASE/analytics/leaderboard/late?month=2026-07&limit=10&department=ManualQA"

# Daily trend: 200, seven rows including weekends and days with no logs.
curl -i "$BASE/analytics/departments/ManualQA/trend?from=2026-07-06&to=2026-07-12"

# All five supported explain variants: 200, executionStats in explain.
curl -i "$BASE/admin/explain/attendance_list?emp_code=$EMP&date_from=2026-07-01&date_to=2026-07-31&status=PRESENT&page=1&page_size=20"
curl -i "$BASE/admin/explain/employee_monthly?emp_code=$EMP&month=2026-07"
curl -i "$BASE/admin/explain/department_summary?month=2026-07&department=ManualQA"
curl -i "$BASE/admin/explain/late_leaderboard?month=2026-07&limit=10&department=ManualQA"
curl -i "$BASE/admin/explain/department_trend?department=ManualQA&from=2026-07-06&to=2026-07-12"

# Interactive docs and generated schema: 200.
curl -i "$BASE/docs"
curl -i "$BASE/openapi.json"
curl -i "$BASE/redoc"
```

## Error checks

Run after the successful sequence above.

```bash
# Duplicate punch-in: 409.
curl -i -X POST "$BASE/attendance/punch-in" -H 'Content-Type: application/json' \
  -d "{\"emp_code\":\"$EMP\",\"punched_at\":1783311300000}"

# Repeated punch-out: 409.
curl -i -X POST "$BASE/attendance/punch-out" -H 'Content-Type: application/json' \
  -d "{\"emp_code\":\"$EMP\",\"punched_at\":1783344600000}"

# No-op correction: 422, stored metrics/history unchanged.
curl -i -X PATCH "$BASE/attendance/$EMP/2026-07-06" -H 'Content-Type: application/json' \
  -d '{"status":"PRESENT","reason":"Nothing has changed","regularized_by":"manual.qa"}'

# Mark leave: 200; clears punch times and derived metrics.
curl -i -X PATCH "$BASE/attendance/$EMP/2026-07-06" -H 'Content-Type: application/json' \
  -d '{"status":"LEAVE","reason":"Approved leave correction","regularized_by":"manual.qa"}'

# Supply punch time while status remains LEAVE: 422.
curl -i -X PATCH "$BASE/attendance/$EMP/2026-07-06" -H 'Content-Type: application/json' \
  -d '{"punch_in":1783310400000,"reason":"Invalid leave punch","regularized_by":"manual.qa"}'

# Restore presence with both times: 200.
curl -i -X PATCH "$BASE/attendance/$EMP/2026-07-06" -H 'Content-Type: application/json' \
  -d '{"status":"PRESENT","punch_in":1783310400000,"punch_out":1783344600000,"reason":"Restore working day","regularized_by":"manual.qa"}'

# Timestamp supplied in seconds: 422.
curl -i -X POST "$BASE/attendance/punch-in" -H 'Content-Type: application/json' \
  -d "{\"emp_code\":\"$EMP\",\"punched_at\":1783311300}"

# Invalid calendar date, pagination, month, trend range, explain target: 422.
curl -i "$BASE/attendance?date_from=2026-02-30"
curl -i "$BASE/employees?page=0"
curl -i "$BASE/analytics/departments/summary?month=2026-13"
curl -i "$BASE/analytics/departments/ManualQA/trend?from=2026-07-12&to=2026-07-06"
curl -i "$BASE/admin/explain/invalid"
curl -i "$BASE/admin/explain/employee_monthly"

# Unknown employee: 404 (assuming this code does not exist).
curl -i "$BASE/analytics/employees/EMP999999/monthly?month=2026-07"
```

## Automated verification

```bash
python -m pytest -m 'not integration'
TEST_MONGO_URI=mongodb://localhost:27017 python -m pytest -m 'integration and not performance'
TEST_MONGO_URI=mongodb://localhost:27017 RUN_PERFORMANCE=1 python -m pytest -m performance
```

Integration tests use unique temporary databases and remove them afterwards.
