# Starter review

Line numbers refer to the original starter, before the modular refactor.

| # | Where (original function / line) | What is wrong | How to notice it | Fix |
|---|---|---|---|---|
| 1 | MongoClient, 22 | Default reads return naive datetimes; no explicit UTC policy. | Comparing a stored punch with an IST-aware shift can fail or shift the time. | Request timezone-aware MongoDB reads; interpret legacy naive values as UTC. |
| 2 | Startup | No indexes are created. | Explain shows collection scans; duplicate natural keys are allowed. | Create named indexes idempotently at startup, including both unique natural keys. |
| 3 | compute_late_minutes, 35 | Shift start uses the punch's timezone and calendar date without IST/overnight anchoring. | A 01:00 overnight punch should be anchored to the previous day's 22:00 shift. | Derive the attendance date in IST and construct both shift boundaries from it. |
| 4 | compute_late_minutes, 36–37 | Floors minutes before checking the ten-minute grace boundary. | 09:40:01 for a 09:30 shift returns 0 instead of 10. | Compare elapsed seconds with 600, then floor elapsed minutes. |
| 5 | compute_work_hours, 41 | Binary floating-point and Python round do not implement decimal half-up. | 4h28m30s is 4.475 hours and must become 4.48. | Divide integer seconds using Decimal and ROUND_HALF_UP. |
| 6 | compute_overtime, 46 | Overnight shift end is placed on the start day. | 22:00–06:00, out next day 06:40 produces a day's extra overtime. | Advance an overnight shift end by one day. |
| 7 | compute_overtime, 47 | Missing 30-minute minimum. | Out at 18:59 for an 18:30 end should give 0, not 29. | Count floored overtime only when at least 30 minutes. |
| 8 | Models, 53–66 | No employee format, length, email, shift or calendar checks. | EMP1, 25:00, February 30 and equal shift boundaries are accepted. | Add bounded Pydantic models, calendar validators and a cross-field shift check. |
| 9 | PunchInIn, 65 | Integer coercion accepts strings/floats; no epoch bounds. | Seconds, strings and out-of-range inputs reach the application. | Require strict integer epoch milliseconds within contract bounds. |
| 10 | PunchInIn, 66 | Arbitrary status strings are accepted. | Punch-in with LEAVE or INVALID creates an invalid record. | Restrict punch-in to the three presence statuses. |
| 11 | health, 73 | Always claims readiness. | Disconnect MongoDB: health still returns 200. | Ping MongoDB; return 503 on a database error. |
| 12 | create_employee, 79–83 | Check-then-insert allows concurrent duplicate codes. | Parallel identical creates can both succeed. | Unique employee-code index; map duplicate-key errors to 409. |
| 13 | create_employee, 82 | Server-local naive creation time. | Run under a non-UTC host timezone. | Store explicit UTC server instants. |
| 14 | create_employee and list_employees, 85 / 96 | created_at is serialized as an ISO string. | Contract requires integer epoch milliseconds. | Convert instants at the response boundary. |
| 15 | list_employees, 93 | Pagination skips the first page. | page=1 skips 20 rows. | Use (page - 1) * page_size. |
| 16 | list_employees, 94 | total ignores the department filter. | Engineering page reports company-wide count. | Count using the same filter. |
| 17 | list_employees, 95 | Missing deterministic emp_code ordering. | Results depend on insertion order. | Sort in MongoDB by emp_code ascending. |
| 18 | Both list endpoints, 89 / 130–131 | Pagination bounds are unchecked. | page=0 or page_size=101 is accepted. | Share Query bounds: page >= 1, page_size 1–100. |
| 19 | punch_in, 101 / 113 | Unknown employee is dereferenced. | Unknown code produces a 500. | Look up the employee and raise 404 when absent. |
| 20 | punch_in, 102 | Timestamp conversion and now use host-local timezone. | A UTC host assigns punches near IST midnight to the wrong date. | Convert milliseconds into explicit UTC and derive the day in IST. |
| 21 | punch_in, 102 | Truthiness conflates a supplied zero with an omitted timestamp. | punched_at=0 silently uses now. | Validate supplied values; only omission selects now. |
| 22 | punch_in, 102–103 | No whole-second truncation. | Millisecond input is stored and affects boundary arithmetic. | Truncate before storage and calculation. |
| 23 | punch_in, 103 | Overnight attendance-day rule is absent. | 01:00 for 22:00–06:00 belongs to the preceding day. | Shared attendance_date helper implements the strict end-time comparison. |
| 24 | punch_in, 104–118 | Check-then-insert races. | Parallel requests create duplicate employee/day records. | Unique employee/date index; exactly one insert wins and other requests get 409. |
| 25 | punch_in / list_attendance, 119 / 149 | MongoDB IDs are exposed as id. | Responses contain a field prohibited by the contract. | Exclude internal IDs and revisions from attendance responses. |
| 26 | punch_in / list_attendance | Punch and nested history timestamps are returned as ISO strings. | Inspect punch_in or history.changes.punch_in.to. | Recursively convert BSON dates to integer epoch milliseconds. |
| 27 | list_attendance, 126–143 | Dates, range ordering and statuses are not validated. | Reversed ranges or malformed dates return misleading empty results. | Validate real calendar dates, inclusive ordered ranges and enumerated statuses. |
| 28 | list_attendance, 144–147 | Loads and sorts all matches in Python. | Broad listing across 100000 records consumes memory and time. | Use indexed database sort, skip, limit and filtered count. |
| 29 | list_attendance, 145 | Missing emp_code tie-breaker. | Same-day records are returned in insertion order. | Sort date descending, then emp_code ascending. |
| 30 | list_attendance, 148–150 | Missing legacy defaults. | Seeded record without history or half_day omits required response fields. | Normalize missing history, half_day and derived defaults at serialization. |

Examined and retained: load_dotenv's default non-overriding behavior correctly gives real environment variables priority. Presence records start with null punch_out/work_hours, zero overtime and false half_day. Removing employee _id before responding is correct. The attendance list's original filtered total and page-offset formula were correct, although its implementation fetched too much data. Ignoring extra client fields is intentional: the contract says supplied derived fields must be ignored. Shift/calendar strings in MongoDB are intentional, not a defect.

The remaining endpoints were absent rather than defective implementations. They now use atomic conditional writes, append-only correction history, database aggregation, exact report rounding and shared query builders for executionStats explain.
