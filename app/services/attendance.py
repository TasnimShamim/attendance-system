"""CRUD operations with database uniqueness and optimistic concurrency."""
from fastapi import HTTPException
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError
from app import database
from app.handlers.serialization import attendance, employee as employee_json
from app.services.time_rules import instant, attendance_date, derived
from app.validators.models import day, date_range

def employee(code):
    result = database.db.employees.find_one({'emp_code': code})
    if result is None:
        raise HTTPException(404, 'Employee not found')
    return result

def create_employee(body):
    doc = body.model_dump()
    doc['created_at'] = instant()
    try:
        database.db.employees.insert_one(doc)
    except DuplicateKeyError:
        raise HTTPException(409, 'emp_code already exists')
    return employee_json(doc)

def list_employees(department, page, page_size):
    query = {} if department is None else {'department': department}
    cursor = database.db.employees.find(query).sort('emp_code', 1).skip((page-1)*page_size).limit(page_size)
    return dict(items=[employee_json(row) for row in cursor], total=database.db.employees.count_documents(query), page=page, page_size=page_size)

def list_query(emp_code=None, date_from=None, date_to=None, status=None):
    query = {}
    if emp_code is not None:
        query['emp_code'] = emp_code
    if status is not None:
        query['status'] = status
    if date_from is not None: day(date_from)
    if date_to is not None: day(date_to)
    if date_from is not None and date_to is not None: date_range(date_from, date_to)
    if date_from is not None or date_to is not None:
        query['date'] = {}
        if date_from is not None: query['date']['$gte'] = date_from
        if date_to is not None: query['date']['$lte'] = date_to
    return query

def list_hint(query):
    return 'attendance_employee_date' if 'emp_code' in query else 'attendance_status_date' if 'status' in query else 'attendance_date'

def list_attendance(emp_code, date_from, date_to, status, page, page_size):
    query = list_query(emp_code, date_from, date_to, status)
    cursor = database.db.attendance_logs.find(query).hint(list_hint(query)).sort([('date', -1), ('emp_code', 1)]).skip((page-1)*page_size).limit(page_size)
    return dict(items=[attendance(row) for row in cursor], total=database.db.attendance_logs.count_documents(query, hint=list_hint(query)), page=page, page_size=page_size)

def punch_in(body):
    emp = employee(body.emp_code)
    ts = instant(body.punched_at)
    doc = dict(emp_code=body.emp_code, date=attendance_date(ts, emp), status=body.status, punch_in=ts, punch_out=None, history=[])
    doc.update(derived(emp, doc))
    try:
        database.db.attendance_logs.insert_one(doc)
    except DuplicateKeyError:
        raise HTTPException(409, 'Already recorded for this date')
    return attendance(doc)

def compare_filter(record):
    # Legacy records have no revision; the first update introduces one atomically.
    return {'_id': record['_id'], '_version': record.get('_version', {'$exists': False})}

def punch_out(body):
    emp = employee(body.emp_code)
    ts = instant(body.punched_at)
    record = database.db.attendance_logs.find_one({'emp_code': body.emp_code, 'punch_in': {'$lte': ts, '$ne': None}}, sort=[('punch_in', -1)])
    if record is None:
        raise HTTPException(404, 'No punch-in found')
    if record.get('punch_out') is not None:
        raise HTTPException(409, 'Already punched out')
    updates = dict(punch_out=ts)
    updates.update(derived(emp, {**record, **updates}))
    result = database.db.attendance_logs.find_one_and_update({**compare_filter(record), 'punch_out': None}, {'$set': updates, '$inc': {'_version': 1}}, return_document=ReturnDocument.AFTER)
    if result is None:
        raise HTTPException(409, 'Record changed concurrently')
    return attendance(result)

def regularize(code, date, body):
    day(date)
    emp = employee(code)
    record = database.db.attendance_logs.find_one({'emp_code': code, 'date': date})
    if record is None:
        raise HTTPException(404, 'Attendance record not found')
    updates = {key: getattr(body, key) for key in ('status', 'punch_in', 'punch_out') if key in body.model_fields_set}
    if updates.get('status', record['status']) in ('ABSENT', 'LEAVE') and any(k in updates for k in ('punch_in', 'punch_out')):
        raise HTTPException(422, 'Absence and leave cannot supply punch times')
    for key in ('punch_in', 'punch_out'):
        if key in updates: updates[key] = instant(updates[key])
    if not any(record.get(key) != value for key, value in updates.items()):
        raise HTTPException(422, 'Correction changes nothing')
    updates.update(derived(emp, {**record, **updates}))
    normalized = {**dict(punch_in=None, punch_out=None, work_hours=None, late_minutes=0, overtime_minutes=0, half_day=False), **record}
    changes = {k: {'from': normalized.get(k), 'to': v} for k, v in updates.items() if normalized.get(k) != v}
    if not changes:
        raise HTTPException(422, 'Correction changes nothing')
    entry = dict(at=instant(), by=body.regularized_by, reason=body.reason, changes=changes)
    result = database.db.attendance_logs.find_one_and_update(compare_filter(record), {'$set': updates, '$push': {'history': entry}, '$inc': {'_version': 1}}, return_document=ReturnDocument.AFTER)
    if result is None:
        raise HTTPException(409, 'Record changed concurrently')
    return attendance(result)
