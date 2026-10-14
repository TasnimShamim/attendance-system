"""Explain the actual shared query builders, preserving filters and pagination."""
import json
from bson import json_util
from fastapi import HTTPException
from app import database
from app.services import analytics, attendance

ENDPOINTS = ('attendance_list', 'employee_monthly', 'department_summary', 'late_leaderboard', 'department_trend')

def explain(endpoint, **params):
    if endpoint not in ENDPOINTS:
        raise HTTPException(422, 'Unknown explain endpoint')
    required = {'employee_monthly': ('emp_code', 'month'), 'department_summary': ('month',), 'late_leaderboard': ('month',), 'department_trend': ('department', 'from_', 'to')}.get(endpoint, ())
    if any(params.get(key) is None for key in required):
        raise HTTPException(422, 'Missing required explain query parameters')
    if endpoint == 'attendance_list':
        collection = 'attendance_logs'
        query = attendance.list_query(params['emp_code'], params['date_from'], params['date_to'], params['status'])
        command = {'find': collection, 'filter': query, 'sort': {'date': -1, 'emp_code': 1}, 'skip': (params['page']-1)*params['page_size'], 'limit': params['page_size'], 'hint': attendance.list_hint(query)}
    else:
        if endpoint == 'employee_monthly':
            spec = analytics.employee_monthly(params['emp_code'], params['month'])
        elif endpoint == 'department_summary':
            spec = analytics.department_summary(params['month'], params['department'])
        elif endpoint == 'late_leaderboard':
            spec = analytics.late_leaderboard(params['month'], params['limit'], params['department'])
        else:
            spec = analytics.department_trend(params['department'], params['from_'], params['to'])
        collection, pipeline, hint = spec
        command = {'aggregate': collection, 'pipeline': pipeline, 'cursor': {}, 'hint': hint, 'allowDiskUse': True}
    result = database.db.command('explain', command, verbosity='executionStats')
    return {'endpoint': endpoint, 'collection': collection, 'explain': json.loads(json_util.dumps(result))}
