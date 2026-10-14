"""IST attendance boundaries and exact half-up arithmetic."""
from datetime import datetime, time, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from fastapi import HTTPException

UTC = timezone.utc
IST = timezone(timedelta(hours=5, minutes=30))
PRESENCE = ['PRESENT', 'WFH', 'ON_DUTY']

def instant(ms=None):
    return (datetime.now(UTC) if ms is None else datetime.fromtimestamp(ms // 1000, UTC)).replace(microsecond=0)

def aware(value):
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)

def half_up(value, places=2):
    return float(Decimal(str(value)).quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP))

def attendance_date(punch, employee):
    local = aware(punch).astimezone(IST)
    result = local.date()
    if employee['shift_end'] <= employee['shift_start'] and local.time().replace(tzinfo=None) < time.fromisoformat(employee['shift_end']):
        result -= timedelta(days=1)
    return result.isoformat()

def shift_bounds(employee, date_str):
    start = datetime.fromisoformat(date_str + 'T' + employee['shift_start']).replace(tzinfo=IST)
    end = datetime.fromisoformat(date_str + 'T' + employee['shift_end']).replace(tzinfo=IST)
    if employee['shift_end'] <= employee['shift_start']:
        end += timedelta(days=1)
    return start, end

def derived(employee, record):
    if record['status'] not in PRESENCE:
        return dict(punch_in=None, punch_out=None, work_hours=None, late_minutes=0, overtime_minutes=0, half_day=False)
    pin, pout = record.get('punch_in'), record.get('punch_out')
    if pin is None:
        raise HTTPException(422, 'Presence requires punch_in')
    if attendance_date(pin, employee) != record['date']:
        raise HTTPException(422, 'punch_in must belong to the attendance date')
    start, end = shift_bounds(employee, record['date'])
    seconds = (aware(pin) - start).total_seconds()
    result = dict(late_minutes=int(seconds // 60) if seconds > 600 else 0, work_hours=None, overtime_minutes=0, half_day=False)
    if pout is not None:
        elapsed = int((aware(pout) - aware(pin)).total_seconds())
        if not 0 < elapsed <= 86400:
            raise HTTPException(422, 'punch_out must be after punch_in and within 24 hours')
        hours = float((Decimal(elapsed) / Decimal(3600)).quantize(Decimal('.01'), rounding=ROUND_HALF_UP))
        overtime = int((aware(pout) - end).total_seconds() // 60)
        result.update(work_hours=hours, overtime_minutes=overtime if overtime >= 30 else 0, half_day=hours < 4.5)
    return result
