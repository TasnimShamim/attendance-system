"""HTTP routes for analytics."""
from typing import Annotated
from fastapi import APIRouter, Query
from app.services import analytics
from app.validators.pagination import Limit

router = APIRouter()

@router.get('/analytics/employees/{emp_code}/monthly', tags=['analytics'])
def monthly(emp_code: str, month: str):
    return analytics.monthly(emp_code, month)

@router.get('/analytics/departments/summary', tags=['analytics'])
def summary(month: str, department: str | None = None):
    return analytics.summary(month, department)

@router.get('/analytics/leaderboard/late', tags=['analytics'])
def leaderboard(month: str, limit: Limit = 10, department: str | None = None):
    return analytics.leaderboard(month, limit, department)

@router.get('/analytics/departments/{department}/trend', tags=['analytics'])
def trend(department: str, from_: Annotated[str, Query(alias='from')], to: str):
    return analytics.trend(department, from_, to)

