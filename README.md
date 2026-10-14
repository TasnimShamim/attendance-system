This project is an employee attendance and analytics API built with FastAPI and MongoDB. The main goal is to model a real HR workflow: create employees, log punch-ins and punch-outs, compute attendance metrics, and expose analytics such as monthly summaries, late leaderboards, and department trends.
The project contract is defined in openapi.yaml, and the setup/usage docs are in README.md. The app entry point is main.py.
//What problem it solves
It is not just a CRUD API. It enforces business rules around:

IST timezone handling
overnight shifts
late calculations
overtime and work-hours calculations
presence vs leave logic
department-level analytics
concurrency-safe attendance updates
The business rules are implemented in time_rules.py, and the MongoDB aggregation pipelines used for analytics live in analytics.py.
What a typical flow looks like
An employee is created with fields like employee code, department, shift start/end, and joined date.
Attendance is recorded via punch-in and punch-out.
The API computes derived values like:
late_minutes
work_hours
overtime_minutes
half_day
These derived values are stored and then used in analytics.
Analytics queries aggregate over MongoDB collections rather than doing all the math in Python.
