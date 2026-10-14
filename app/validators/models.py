"""Strict request and calendar validation for the HTTP contract."""
import re
from datetime import date
from typing import Annotated, Literal
from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, AfterValidator, model_validator

Status = Literal['PRESENT', 'ABSENT', 'LEAVE', 'WFH', 'ON_DUTY']
PresenceStatus = Literal['PRESENT', 'WFH', 'ON_DUTY']
Epoch = Annotated[int, Field(strict=True, ge=100000000000, le=4102444800000)]

def calendar(value: str) -> str:
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
        raise ValueError('Expected YYYY-MM-DD')
    date.fromisoformat(value)
    return value

Calendar = Annotated[str, AfterValidator(calendar)]

def day(value: str) -> date:
    try:
        return date.fromisoformat(calendar(value))
    except (ValueError, TypeError):
        raise HTTPException(422, 'Invalid calendar date; expected YYYY-MM-DD')

def month_bounds(value: str):
    if not re.fullmatch(r'\d{4}-(0[1-9]|1[0-2])', value):
        raise HTTPException(422, 'Invalid month; expected YYYY-MM')
    start = day(value + '-01')
    import calendar as cal
    end = start.replace(day=cal.monthrange(start.year, start.month)[1])
    return start, end

def date_range(start, end, max_days=None):
    a, b = day(start), day(end)
    if b < a or (max_days and (b-a).days + 1 > max_days):
        raise HTTPException(422, 'Invalid date range')
    return a, b

class Input(BaseModel):
    model_config = ConfigDict(extra='ignore')

class EmployeeIn(Input):
    emp_code: Annotated[str, Field(pattern=r'^EMP\d{4,6}$')]
    name: Annotated[str, Field(min_length=1, max_length=100)]
    email: Annotated[str, Field(max_length=120, pattern=r'^[^@\s]+@[^@\s]+\.[^@\s]+$')]
    department: Annotated[str, Field(min_length=1, max_length=50)]
    shift_start: Annotated[str, Field(pattern=r'^([01]\d|2[0-3]):[0-5]\d$')] = '09:30'
    shift_end: Annotated[str, Field(pattern=r'^([01]\d|2[0-3]):[0-5]\d$')] = '18:30'
    joined_on: Calendar

    @model_validator(mode='after')
    def distinct_shift(self):
        if self.shift_start == self.shift_end:
            raise ValueError('Shift start and end must differ')
        return self

class PunchOutIn(Input):
    emp_code: str
    punched_at: Epoch | None = None

    @model_validator(mode='after')
    def nonnull_timestamp(self):
        if 'punched_at' in self.model_fields_set and self.punched_at is None:
            raise ValueError('punched_at cannot be null')
        return self

class PunchInIn(PunchOutIn):
    status: PresenceStatus = 'PRESENT'

class RegularizeIn(Input):
    status: Status | None = None
    punch_in: Epoch | None = None
    punch_out: Epoch | None = None
    reason: Annotated[str, Field(min_length=5, max_length=200)]
    regularized_by: Annotated[str, Field(min_length=1, max_length=50)]

    @model_validator(mode='after')
    def nonnull_changes(self):
        for field in ('status', 'punch_in', 'punch_out'):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f'{field} cannot be null')
        return self
