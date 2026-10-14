"""HTTP routes for attendance."""
from fastapi import APIRouter
from app.services import attendance
from app.validators.models import PunchInIn, PunchOutIn, RegularizeIn, Status
from app.validators.pagination import Page, PageSize

router = APIRouter()

@router.post('/attendance/punch-in', status_code=201, tags=['attendance'])
def punch_in(body: PunchInIn):
    return attendance.punch_in(body)

@router.post('/attendance/punch-out', tags=['attendance'])
def punch_out(body: PunchOutIn):
    return attendance.punch_out(body)

@router.get('/attendance', tags=['attendance'])
def list_attendance(emp_code: str | None = None, date_from: str | None = None, date_to: str | None = None, status: Status | None = None, page: Page = 1, page_size: PageSize = 20):
    return attendance.list_attendance(emp_code, date_from, date_to, status, page, page_size)

@router.patch('/attendance/{emp_code}/{date}', tags=['attendance'])
def regularize(emp_code: str, date: str, body: RegularizeIn):
    return attendance.regularize(emp_code, date, body)

