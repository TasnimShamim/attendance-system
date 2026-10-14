"""Convert BSON instants, including nested audit values, at the API boundary."""
from datetime import datetime
from bson import ObjectId, Decimal128
from app.services.time_rules import aware

def serialize(value):
    if isinstance(value, datetime):
        return int(aware(value).timestamp() * 1000)
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, Decimal128):
        return float(value.to_decimal())
    if isinstance(value, dict):
        return {k: serialize(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [serialize(v) for v in value]
    return value

def attendance(record):
    result = {k: v for k, v in record.items() if k not in ('_id', '_version')}
    for key, default in [('punch_in', None), ('punch_out', None), ('work_hours', None), ('late_minutes', 0), ('overtime_minutes', 0), ('half_day', False), ('history', [])]:
        result.setdefault(key, default)
    return serialize(result)


def employee(record):
    return serialize({k: v for k, v in record.items() if k != '_id'})
