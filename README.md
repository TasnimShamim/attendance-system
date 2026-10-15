# Employee Attendance & Analytics API

A backend service built with **FastAPI and MongoDB** to manage employee records, track attendance, calculate working hours, and generate HR analytics through efficient database aggregation pipelines.

The project models a real-world HR attendance workflow with timezone-aware calculations, shift management, overtime tracking, department-level analytics, and audit-friendly attendance corrections.

## Features

### Employee Management
- Create, retrieve, update, and manage employee records.
- Store employee codes, departments, shift timings, and joining dates.
- Validate incoming requests and enforce business rules.

### Attendance Management
- Record employee punch-in and punch-out events.
- Calculate attendance metrics automatically.
- Handle duplicate submissions to prevent double logging for the same date.
- Support overnight shifts and timezone-aware attendance records.
- Track attendance history and manual corrections.

### Attendance Calculations
The service calculates and maintains derived attendance metrics, including:

- **Late Minutes:** Measures how late an employee arrives relative to their scheduled shift.
- **Work Hours:** Calculates the duration of an employee's work session.
- **Overtime Minutes:** Tracks time worked beyond the applicable shift duration.
- **Half-Day Status:** Determines whether attendance qualifies as a half-day based on configured business rules.

### HR Analytics
- Monthly employee attendance summaries.
- Department-level attendance summaries.
- Late-arrival leaderboards.
- Attendance and department trend analysis.
- MongoDB aggregation pipelines for efficient analytics processing.

### Reliability and Data Integrity
- IST timezone handling for consistent attendance calculations.
- Concurrency-aware punch-in and punch-out operations.
- Request validation and pagination enforcement.
- Centralized error handling and response serialization.
- Audit trail support for attendance corrections, including before-and-after values.
- Database indexes initialized during application startup.

### API Documentation and Diagnostics
- OpenAPI contract maintained in `openapi.yaml`.
- Interactive API documentation provided by FastAPI.
- Readiness health-check endpoint.
- Admin/debug endpoint for inspecting MongoDB query execution plans.

## Tech Stack

| Technology | Purpose |
|---|---|
| Python | Backend programming language |
| FastAPI | REST API framework |
| MongoDB | Employee and attendance data storage |
| MongoDB Aggregation Pipeline | Database-level analytics and reporting |
| OpenAPI | API contract and endpoint documentation |
| Pydantic / Validators | Request validation, where configured |
| PyMongo or MongoDB driver | Database connectivity, depending on project configuration |

## Project Structure

```text
.
├── main.py
├── database.py
├── api.py
├── employees.py
├── attendance.py
├── analytics.py
├── admin.py
├── time_rules.py
├── openapi.yaml
├── services/
├── validators/
├── handlers/
└── README.md
```

> The structure above summarizes the main files and directories. Additional configuration, test, and dependency files may exist in the repository.

### Key Files and Responsibilities

| File / Directory | Responsibility |
|---|---|
| `main.py` | Initializes the FastAPI application, manages the database lifecycle, exposes readiness checks, and registers routes. |
| `database.py` | Establishes the MongoDB connection and creates required indexes. |
| `api.py` | Combines route modules into a unified API router. |
| `employees.py` | Implements employee management endpoints. |
| `attendance.py` | Handles punch-in, punch-out, attendance listing, and related operations. |
| `analytics.py` | Provides monthly summaries, department analytics, leaderboards, and trends. |
| `admin.py` | Exposes diagnostic functionality for inspecting analytics query execution plans. |
| `time_rules.py` | Contains attendance business rules, time calculations, and shift-related logic. |
| `services/` | Encapsulates reusable business logic and MongoDB query builders. |
| `validators/` | Validates requests and enforces pagination constraints. |
| `handlers/` | Centralizes error handling and response serialization. |
| `openapi.yaml` | Defines the API contract and endpoint specifications. |

## How It Works

The application follows an employee-to-attendance-to-analytics workflow.

1. **Create an employee:** Store the employee code, department, shift start and end times, and joining date.
2. **Record punch-in:** Capture the employee's attendance start time while applying the relevant timezone and duplicate-submission rules.
3. **Record punch-out:** Capture the end time and calculate the applicable attendance metrics.
4. **Apply business rules:** Determine late minutes, work hours, overtime, and half-day status.
5. **Persist attendance data:** Store attendance records and derived values in MongoDB.
6. **Generate analytics:** Execute aggregation pipelines to produce employee summaries, department reports, leaderboards, and trends.

```text
Employee Management
        |
        v
Attendance Punch-In / Punch-Out
        |
        v
Time Rules & Validation
        |
        v
MongoDB Attendance Records
        |
        v
Aggregation Pipelines
        |
        v
HR Analytics & Reports
```

## Architecture and Design Decisions

### 1. MongoDB-First Analytics

Analytics are computed using MongoDB aggregation pipelines rather than fetching all records and performing every calculation in Python. This keeps filtering, grouping, and summarization close to the stored data.

### 2. Centralized Business Rules

Attendance calculations are handled through dedicated time-rule logic. This provides a consistent approach to timezone conversion, overnight shifts, lateness, work duration, and overtime.

### 3. Concurrency-Aware Attendance Updates

Punch-in and punch-out operations account for duplicate requests and concurrent submissions. The goal is to prevent multiple requests for the same attendance event from producing duplicate records.

### 4. Audit-Friendly Corrections

Attendance corrections preserve history so that manual adjustments can be tracked alongside their previous and updated values.

### 5. Contract-Driven API Development

The `openapi.yaml` file defines the expected API contract, helping keep endpoint behavior, request validation, and API documentation aligned.

## Getting Started

### Prerequisites

- Python 3.10 or later, subject to the project's configured Python version.
- A running MongoDB instance or MongoDB connection URI.
- Git.

### 1. Clone the Repository

```bash
git clone <your-repository-url>
cd <your-project-directory>
```

Replace the placeholders with your repository URL and project directory.

### 2. Create a Virtual Environment

```bash
python -m venv .venv
```

Activate it on Linux or macOS:

```bash
source .venv/bin/activate
```

On Windows:

```bash
.venv\Scripts\activate
```

### 3. Install Dependencies

If the repository contains a `requirements.txt` file:

```bash
pip install -r requirements.txt
```

Otherwise, install the dependencies specified by your project's dependency configuration.

### 4. Configure Environment Variables

Configure the MongoDB connection string and any other settings required by the application.

For example, if the application reads `MONGODB_URI`:

```env
MONGODB_URI=mongodb://localhost:27017
```

The variable name and database name must match the application's actual configuration. Keep credentials in environment variables and never commit real secrets.

### 5. Start the API Server

If `main.py` defines the FastAPI application as `app`:

```bash
uvicorn main:app --reload
```

The development server will generally be available at:

`http://127.0.0.1:8000`

### 6. Explore the API

Once the server is running, open:

- **Swagger UI:** `http://127.0.0.1:8000/docs`
- **ReDoc:** `http://127.0.0.1:8000/redoc`
- **OpenAPI schema:** `http://127.0.0.1:8000/openapi.json`

The actual routes and documentation availability depend on the application's configuration.

## API Capabilities

The API is organized around three primary areas:

| Area | Capabilities |
|---|---|
| Employees | Employee creation, retrieval, and management |
| Attendance | Punch-in, punch-out, attendance listing, and correction workflows |
| Analytics | Monthly summaries, department reports, late-arrival leaderboards, and trends |

Refer to `openapi.yaml` or the interactive Swagger documentation for the exact endpoint paths, HTTP methods, request schemas, response formats, and status codes.

## Business Rules and Edge Cases

The application is designed to account for real-world attendance scenarios, including:

- **Timezone consistency:** Apply IST-aware time handling.
- **Overnight shifts:** Handle shifts that continue past midnight.
- **Late arrival:** Calculate lateness against the employee's scheduled shift.
- **Overtime:** Derive overtime from recorded work duration and applicable rules.
- **Presence versus leave:** Distinguish attendance from leave-related states according to the configured business logic.
- **Duplicate requests:** Avoid duplicate attendance logging when requests are repeated.
- **Attendance corrections:** Preserve before-and-after values for manual adjustments.

Exact thresholds, leave policies, and rounding behavior are defined by the implementation rather than assumed by this README.

## Testing

Run the test suite using the testing framework configured in the repository.

For a project using `pytest`:

```bash
pytest
```

If tests are organized under a `tests/` directory, you can run:

```bash
pytest tests/
```

These commands assume the relevant tests and dependencies are present.

## Future Enhancements

Potential extensions include:

- Role-based access control for employees, managers, and administrators.
- Automated leave request and approval workflows.
- Exportable attendance reports in CSV or Excel format.
- Dashboard integration for visualizing attendance trends.
- Automated notifications for missed punch-outs and repeated late arrivals.
- Expanded integration and concurrency tests.

## What Makes This Project Interesting?

This project goes beyond basic CRUD operations by combining REST API development with time-sensitive business logic, data integrity, and database-level analytics.

It demonstrates practical backend engineering concepts such as:

- API design and request validation.
- Database modeling and indexing.
- MongoDB aggregation pipelines.
- Timezone-aware calculations.
- Concurrency-aware updates.
- Audit trails and centralized error handling.
- Contract-driven API documentation.

## Summary

The Employee Attendance & Analytics API is a FastAPI and MongoDB-based backend that models a practical HR attendance system. It centralizes attendance rules, records employee work sessions, calculates working-hour metrics, and generates HR analytics using MongoDB aggregation pipelines.

**Core focus:** Reliable attendance processing, maintainable backend architecture, and efficient data-driven HR reporting.
