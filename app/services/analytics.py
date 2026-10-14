"""Shared pipeline builders used by both analytics and executionStats explain."""
from fastapi import HTTPException
from app import database
from app.handlers.serialization import serialize
from app.services.time_rules import PRESENCE
from app.validators.models import month_bounds, date_range

ZERO = {'present_days': 0, 'leave_days': 0, 'late_count': 0, 'total_late_minutes': 0, 'total_overtime_minutes': 0, 'work_sum': 0, 'work_count': 0, 'on_duty_count': 0}

def rounded(expression, places=2):
    # All reported metrics are nonnegative. Decimal arithmetic avoids binary ties;
    # MongoDB $round uses half-even, so implement half-up explicitly.
    scale = 10 ** places
    return {'$toDouble': {'$divide': [{'$floor': {'$add': [{'$multiply': [{'$toDecimal': expression}, scale]}, {'$toDecimal': '0.5'}]}}, scale]}}

def parsed_date(expression):
    return {'$dateFromString': {'dateString': expression, 'format': '%Y-%m-%d', 'timezone': 'Asia/Kolkata'}}

def weekday(expression):
    return {'$in': [{'$dayOfWeek': {'date': expression, 'timezone': 'Asia/Kolkata'}}, [2, 3, 4, 5, 6]]}

def weighted_presence():
    return {'$cond': [{'$in': ['$status', PRESENCE]}, {'$cond': [{'$ifNull': ['$half_day', False]}, 0.5, 1]}, 0]}

def metric_group():
    present = {'$and': [{'$in': ['$status', PRESENCE]}, weekday(parsed_date('$date'))]}
    valid_work = {'$and': [{'$in': ['$status', PRESENCE]}, {'$ne': [{'$ifNull': ['$work_hours', None]}, None]}]}
    return {'$group': {
        '_id': None,
        'present_days': {'$sum': {'$cond': [present, weighted_presence(), 0]}},
        'leave_days': {'$sum': {'$cond': [{'$eq': ['$status', 'LEAVE']}, 1, 0]}},
        'late_count': {'$sum': {'$cond': [{'$gt': [{'$ifNull': ['$late_minutes', 0]}, 0]}, 1, 0]}},
        'total_late_minutes': {'$sum': {'$ifNull': ['$late_minutes', 0]}},
        'total_overtime_minutes': {'$sum': {'$ifNull': ['$overtime_minutes', 0]}},
        'work_sum': {'$sum': {'$cond': [valid_work, {'$toDecimal': '$work_hours'}, 0]}},
        'work_count': {'$sum': {'$cond': [valid_work, 1, 0]}},
        'on_duty_count': {'$sum': {'$cond': [{'$eq': ['$status', 'ON_DUTY']}, 1, 0]}},
    }}

def logs_lookup(start, end):
    return {'$lookup': {'from': 'attendance_logs', 'let': {'code': '$emp_code'}, 'pipeline': [
        {'$match': {'$expr': {'$eq': ['$emp_code', '$$code']}, 'date': {'$gte': start.isoformat(), '$lte': end.isoformat()}}},
        metric_group(), {'$project': {'_id': 0}},
    ], 'as': 'metrics'}}

def metrics_default():
    return {'$set': {'metrics': {'$ifNull': [{'$arrayElemAt': ['$metrics', 0]}, ZERO]}}}

def employee_monthly(code, month):
    start, end = month_bounds(month)
    # Calendar generation and weekday counting also execute inside MongoDB.
    first = parsed_date(start.isoformat())
    dates = {'$map': {'input': {'$range': [0, (end-start).days+1]}, 'as': 'offset', 'in': {'$dateAdd': {'startDate': first, 'unit': 'day', 'amount': '$$offset', 'timezone': 'Asia/Kolkata'}}}}
    working = {'$size': {'$filter': {'input': dates, 'as': 'd', 'cond': {'$and': [weekday('$$d'), {'$gte': ['$$d', parsed_date('$joined_on')]}]}}}}
    pipeline = [{'$match': {'emp_code': code}}, logs_lookup(start, end), metrics_default(), {'$set': {'working_days': working}}, {'$project': {
        '_id': 0, 'emp_code': 1, 'month': {'$literal': month}, 'working_days': 1,
        **{k: '$metrics.'+k for k in ('present_days', 'leave_days', 'late_count', 'total_late_minutes', 'total_overtime_minutes')},
        'attendance_pct': {'$cond': [{'$gt': ['$working_days', 0]}, rounded({'$multiply': [{'$divide': [{'$toDecimal': '$metrics.present_days'}, '$working_days']}, 100]}), None]},
    }}]
    return 'employees', pipeline, 'employee_code'

def department_summary(month, department=None):
    start, end = month_bounds(month)
    query = {'joined_on': {'$lte': end.isoformat()}}
    if department is not None: query['department'] = department
    group = {'_id': '$department', 'headcount': {'$sum': 1}, **{k: {'$sum': '$metrics.'+k} for k in ZERO}}
    pipeline = [{'$match': query}, logs_lookup(start, end), metrics_default(), {'$group': group}, {'$project': {
        '_id': 0, 'department': '$_id', 'headcount': 1, 'present_days': 1,
        'avg_work_hours': {'$cond': [{'$gt': ['$work_count', 0]}, rounded({'$divide': ['$work_sum', '$work_count']}), None]},
        'late_count': 1, 'total_late_minutes': 1, 'leave_count': '$leave_days', 'on_duty_count': 1,
    }}, {'$sort': {'department': 1}}]
    return 'employees', pipeline, 'employee_joined' if department is None else 'employee_department'

def late_leaderboard(month, limit=10, department=None):
    start, end = month_bounds(month)
    pipeline = [{'$match': {'date': {'$gte': start.isoformat(), '$lte': end.isoformat()}}}, {'$group': {
        '_id': '$emp_code', 'total_late_minutes': {'$sum': {'$ifNull': ['$late_minutes', 0]}},
        'late_count': {'$sum': {'$cond': [{'$gt': [{'$ifNull': ['$late_minutes', 0]}, 0]}, 1, 0]}},
    }}, {'$match': {'total_late_minutes': {'$gt': 0}}}, {'$lookup': {'from': 'employees', 'localField': '_id', 'foreignField': 'emp_code', 'as': 'employee'}}, {'$unwind': '$employee'}]
    if department is not None: pipeline.append({'$match': {'employee.department': department}})
    pipeline.extend([
        {'$setWindowFields': {'sortBy': {'total_late_minutes': -1}, 'output': {'rank': {'$rank': {}}}}},
        {'$match': {'rank': {'$lte': limit}}},
        {'$project': {'_id': 0, 'emp_code': '$_id', 'name': '$employee.name', 'department': '$employee.department', 'rank': 1, 'total_late_minutes': 1, 'late_count': 1}},
        {'$sort': {'total_late_minutes': -1, 'emp_code': 1}},
    ])
    return 'attendance_logs', pipeline, 'attendance_date'

def department_trend(department, start_str, end_str):
    start, end = date_range(start_str, end_str, 92)
    first = parsed_date(start_str)
    pipeline = [
        {'$match': {'department': department}},
        {'$group': {'_id': None, 'joined': {'$push': '$joined_on'}, 'codes': {'$push': '$emp_code'}}},
        {'$set': {'days': {'$range': [0, (end-start).days+1]}}}, {'$unwind': '$days'},
        {'$set': {'day': {'$dateAdd': {'startDate': first, 'unit': 'day', 'amount': '$days', 'timezone': 'Asia/Kolkata'}}}},
        {'$set': {'date': {'$dateToString': {'date': '$day', 'format': '%Y-%m-%d', 'timezone': 'Asia/Kolkata'}}, 'is_working_day': weekday('$day')}},
        {'$set': {'headcount': {'$size': {'$filter': {'input': '$joined', 'as': 'j', 'cond': {'$lte': ['$$j', '$date']}}}}}},
        {'$lookup': {'from': 'attendance_logs', 'let': {'date': '$date', 'codes': '$codes'}, 'pipeline': [
            {'$match': {'$expr': {'$and': [{'$eq': ['$date', '$$date']}, {'$in': ['$emp_code', '$$codes']}]}}},
            {'$group': {'_id': None, 'present_count': {'$sum': weighted_presence()}, 'late_count': {'$sum': {'$cond': [{'$gt': [{'$ifNull': ['$late_minutes', 0]}, 0]}, 1, 0]}}}},
        ], 'as': 'logs'}},
        {'$set': {'present_count': {'$ifNull': [{'$arrayElemAt': ['$logs.present_count', 0]}, 0]}, 'late_count': {'$ifNull': [{'$arrayElemAt': ['$logs.late_count', 0]}, 0]}}},
        {'$set': {'attendance_rate': {'$cond': [{'$and': ['$is_working_day', {'$gt': ['$headcount', 0]}]}, rounded({'$divide': [{'$toDecimal': '$present_count'}, '$headcount']}, 4), None]}}},
        {'$setWindowFields': {'sortBy': {'date': 1}, 'output': {'moving': {'$avg': {'$toDecimal': '$attendance_rate'}, 'window': {'documents': [-6, 0]}}}}},
        {'$project': {'_id': 0, 'date': 1, 'is_working_day': 1, 'headcount': 1, 'present_count': 1, 'late_count': 1, 'attendance_rate': 1, 'moving_avg_7d': {'$cond': [{'$ne': ['$moving', None]}, rounded('$moving', 4), None]}}},
        {'$sort': {'date': 1}},
    ]
    return 'employees', pipeline, 'employee_department'

def execute(spec):
    collection, pipeline, hint = spec
    return serialize(list(database.db[collection].aggregate(pipeline, hint=hint, allowDiskUse=True)))

def monthly(code, month):
    rows = execute(employee_monthly(code, month))
    if not rows: raise HTTPException(404, 'Employee not found')
    return rows[0]

def summary(month, department):
    return {'month': month, 'items': execute(department_summary(month, department))}

def leaderboard(month, limit, department):
    return {'month': month, 'items': execute(late_leaderboard(month, limit, department))}

def trend(department, start, end):
    rows = execute(department_trend(department, start, end))
    if not rows: raise HTTPException(404, 'Department not found')
    return {'department': department, 'items': rows}
