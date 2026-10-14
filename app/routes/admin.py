"""HTTP routes for admin."""
from typing import Annotated
from fastapi import APIRouter, Query
from app.services.explain import explain
from app.validators.models import Status
from app.validators.pagination import Page, PageSize, Limit

router = APIRouter()

@router.get('/admin/explain/{endpoint}', tags=['admin'])
def explain_query(endpoint: str, emp_code: str | None = None, month: str | None = None, department: str | None = None, limit: Limit = 10, date_from: str | None = None, date_to: str | None = None, status: Status | None = None, from_: Annotated[str | None, Query(alias='from')] = None, to: str | None = None, page: Page = 1, page_size: PageSize = 20):
    return explain(endpoint, emp_code=emp_code, month=month, department=department, limit=limit, date_from=date_from, date_to=date_to, status=status, from_=from_, to=to, page=page, page_size=page_size)
