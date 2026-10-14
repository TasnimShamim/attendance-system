from datetime import datetime
import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from app.services.time_rules import IST, derived, attendance_date, instant
from app.validators.models import PunchInIn, EmployeeIn, RegularizeIn, month_bounds, date_range
from app.handlers.serialization import attendance

EMP = {'shift_start': '09:30', 'shift_end': '18:30'}

def record(pin, pout=None, status='PRESENT'):
    return dict(date='2026-07-06', status=status, punch_in=datetime.fromisoformat('2026-07-06T'+pin).replace(tzinfo=IST), punch_out=datetime.fromisoformat('2026-07-06T'+pout).replace(tzinfo=IST) if pout else None)

@pytest.mark.parametrize('pin,late', [('09:40:00', 0), ('09:40:01', 10), ('10:15:59', 45), ('09:29:00', 0)])
def test_grace_boundary(pin, late):
    assert derived(EMP, record(pin))['late_minutes'] == late

@pytest.mark.parametrize('pout,ot', [('18:59:59', 0), ('19:00:00', 30), ('19:00:59', 30)])
def test_overtime_threshold(pout, ot):
    assert derived(EMP, record('09:30:00', pout))['overtime_minutes'] == ot

def test_half_up_and_half_day_use_rounded_hours():
    assert derived(EMP, record('09:30:00', '13:58:30'))['work_hours'] == 4.48
    result = derived(EMP, record('09:30:00', '13:59:42'))
    assert result['work_hours'] == 4.5
    assert result['half_day'] is False

def test_overnight_date_and_end():
    emp = {'shift_start': '22:00', 'shift_end': '06:00'}
    pin = datetime(2026, 7, 7, 1, 0, tzinfo=IST)
    assert attendance_date(pin, emp) == '2026-07-06'
    result = derived(emp, dict(date='2026-07-06', status='WFH', punch_in=pin, punch_out=datetime(2026, 7, 7, 6, 40, tzinfo=IST)))
    assert result['late_minutes'] == 180
    assert result['overtime_minutes'] == 40
    assert attendance_date(datetime(2026, 7, 7, 6, tzinfo=IST), emp) == '2026-07-07'

@pytest.mark.parametrize('value', [1783312500, 1783312500000.0, '1783312500000', True, 4102444800001, None])
def test_bad_timestamp(value):
    with pytest.raises(ValidationError):
        PunchInIn(emp_code='EMP0001', punched_at=value)

def test_truncation():
    assert instant(1783312500999) == instant(1783312500000)
    assert PunchInIn(emp_code='EMP0001').punched_at is None

@pytest.mark.parametrize('kwargs', [{'shift_end': '09:30'}, {'joined_on': '2026-02-30'}, {'shift_start': '25:00'}, {'email': 'invalid'}, {'emp_code': '123'}])
def test_employee_validation(kwargs):
    data = dict(emp_code='EMP0001', name='A', email='a@b.co', department='D', joined_on='2026-01-01')
    with pytest.raises(ValidationError): EmployeeIn(**{**data, **kwargs})

def test_derived_input_ignored():
    body = PunchInIn(emp_code='EMP0001', work_hours=100)
    assert 'work_hours' not in body.model_dump()

def test_invalid_ranges():
    for month in ('2026-13', '2026-1', '0000-01'):
        with pytest.raises(HTTPException): month_bounds(month)
    with pytest.raises(HTTPException): date_range('2026-07-02', '2026-07-01')
    with pytest.raises(HTTPException): date_range('2026-01-01', '2026-04-03', 92)

def test_duration_validation():
    with pytest.raises(HTTPException): derived(EMP, record('09:30:00', '09:30:00'))

def test_absence_resets_derived_values():
    result = derived(EMP, record('09:30:00', '19:00:00', 'LEAVE'))
    assert result == dict(punch_in=None, punch_out=None, work_hours=None, late_minutes=0, overtime_minutes=0, half_day=False)

def test_nested_history_serialization_and_legacy_defaults():
    ts = instant(1783312500000)
    result = attendance({'_id': 'internal', '_version': 2, 'history': [{'at': ts, 'changes': {'punch_in': {'from': None, 'to': ts}}}]})
    assert '_id' not in result and '_version' not in result
    assert result['half_day'] is False
    assert result['history'][0]['changes']['punch_in']['to'] == 1783312500000
