"""HTTP routes for employees."""
from fastapi import APIRouter
from app.services import attendance
from app.validators.models import EmployeeIn
from app.validators.pagination import Page, PageSize

router = APIRouter()

@router.post('/employees', status_code=201, tags=['employees'])
def create_employee(body: EmployeeIn):
    return attendance.create_employee(body)

@router.get('/employees', tags=['employees'])
def list_employees(department: str | None = None, page: Page = 1, page_size: PageSize = 20):
    return attendance.list_employees(department, page, page_size)

