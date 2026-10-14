"""Real MongoDB tests: isolated databases, concurrency, pipelines and query plans."""
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Barrier
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from pymongo import MongoClient
from app import database
from app.main import app
from app.services import attendance as attendance_service

pytestmark = pytest.mark.integration

@pytest.fixture
def mongo(monkeypatch):
    uri = os.getenv('TEST_MONGO_URI')
    if not uri:
        pytest.skip('Set TEST_MONGO_URI to run real MongoDB integration checks')
    conn = MongoClient(uri, tz_aware=True, serverSelectionTimeoutMS=3000)
    conn.admin.command('ping')
    name = 'candidate_kit_test_' + uuid4().hex
    db = conn[name]
    monkeypatch.setattr(database, 'db', db)
    database.create_indexes()
    yield db, TestClient(app)
    conn.drop_database(name)
    conn.close()


def employee(code, joined='2026-07-01', department='Engineering'):
    return dict(emp_code=code, name=code, email=code+'@example.com', department=department, joined_on=joined, shift_start='09:30', shift_end='18:30', created_at=datetime(2026, 1, 1, tzinfo=timezone.utc))


def log(code, day, hours=8, late=0, half=False, status='PRESENT', overtime=0):
    # Deliberately store derived values that differ from punch times: analytics
    # must use the authoritative stored metrics, not recompute them.
    pin = datetime.fromisoformat(day+'T04:00:00+00:00')
    return dict(emp_code=code, date=day, status=status, punch_in=pin if status in ('PRESENT', 'WFH', 'ON_DUTY') else None, punch_out=pin+timedelta(hours=8) if hours is not None and status in ('PRESENT', 'WFH', 'ON_DUTY') else None, work_hours=hours, late_minutes=late, overtime_minutes=overtime, half_day=half)

@pytest.fixture
def seeded(mongo):
    db, client = mongo
    db.employees.insert_many([employee('EMP0001'), employee('EMP0002'), employee('EMP0003'), employee('EMP0004', '2026-07-08'), employee('EMP0005', '2026-08-01', 'Future')])
    db.attendance_logs.insert_many([
        log('EMP0001', '2026-07-06', hours=8, late=15, overtime=45),
        log('EMP0001', '2026-07-07', hours=6),
        log('EMP0001', '2026-07-11', hours=2, late=5),
        log('EMP0002', '2026-07-06', hours=3, late=10, half=True, status='WFH'),
        log('EMP0002', '2026-07-08', hours=None, status='LEAVE'),
        log('EMP0003', '2026-07-06', hours=7, late=10, status='ON_DUTY'),
    ])
    return db, client

def get(client, url):
    response = client.get(url)
    assert response.status_code == 200, response.text
    return response.json()

def test_analytics_authoritative_values_headcount_and_ties(seeded):
    _, client = seeded
    monthly = get(client, '/analytics/employees/EMP0001/monthly?month=2026-07')
    assert monthly == dict(emp_code='EMP0001', month='2026-07', working_days=23, present_days=2, leave_days=0, late_count=2, total_late_minutes=20, total_overtime_minutes=45, attendance_pct=8.7)
    joined = get(client, '/analytics/employees/EMP0004/monthly?month=2026-07')
    assert joined['working_days'] == 18 and joined['present_days'] == 0
    future = get(client, '/analytics/employees/EMP0005/monthly?month=2026-07')
    assert future['working_days'] == 0 and future['attendance_pct'] is None
    summary = get(client, '/analytics/departments/summary?month=2026-07')['items']
    assert summary == [dict(department='Engineering', headcount=4, present_days=3.5, avg_work_hours=5.2, late_count=4, total_late_minutes=40, leave_count=1, on_duty_count=1)]
    board = get(client, '/analytics/leaderboard/late?month=2026-07&limit=2')['items']
    assert [(row['emp_code'], row['rank']) for row in board] == [('EMP0001', 1), ('EMP0002', 2), ('EMP0003', 2)]
    assert get(client, '/analytics/leaderboard/late?month=2026-07&department=Other')['items'] == []

def test_trend_calendar_gaps_weekends_and_joiners(seeded):
    _, client = seeded
    rows = get(client, '/analytics/departments/Engineering/trend?from=2026-07-06&to=2026-07-12')['items']
    assert len(rows) == 7
    assert rows[0]['headcount'] == 3 and rows[0]['present_count'] == 2.5 and rows[0]['attendance_rate'] == .8333
    assert rows[1]['attendance_rate'] == .3333
    assert rows[2]['headcount'] == 4 and rows[2]['attendance_rate'] == 0
    assert rows[5]['present_count'] == 1 and rows[5]['attendance_rate'] is None
    assert rows[6]['moving_avg_7d'] == .2333
    future = get(client, '/analytics/departments/Future/trend?from=2026-07-01&to=2026-07-03')['items']
    assert len(future) == 3 and all(r['headcount'] == 0 and r['moving_avg_7d'] is None for r in future)
    assert client.get('/analytics/departments/Missing/trend?from=2026-07-01&to=2026-07-03').status_code == 404

def test_pagination_and_legacy_serialization(seeded):
    _, client = seeded
    page = get(client, '/employees?department=Engineering&page=1&page_size=2')
    assert page['total'] == 4 and [r['emp_code'] for r in page['items']] == ['EMP0001', 'EMP0002']
    assert isinstance(page['items'][0]['created_at'], int)
    logs = get(client, '/attendance?page_size=2')
    assert logs['total'] == 6 and logs['items'][0]['date'] == '2026-07-11'
    assert logs['items'][0]['history'] == [] and 'id' not in logs['items'][0] and '_id' not in logs['items'][0]
    assert get(client, '/attendance?status=LEAVE')['total'] == 1

def milliseconds(value):
    return int(datetime.fromisoformat(value).timestamp()*1000)

def test_overnight_punches_and_correction_audit(mongo):
    db, client = mongo
    emp = employee('EMP0001')
    emp.update(shift_start='22:00', shift_end='06:00')
    db.employees.insert_one(emp)
    pin = milliseconds('2026-07-07T01:00:00+05:30')
    pout = milliseconds('2026-07-07T06:40:00+05:30')
    response = client.post('/attendance/punch-in', json=dict(emp_code='EMP0001', punched_at=pin+999, status='WFH'))
    assert response.status_code == 201
    assert response.json()['date'] == '2026-07-06' and response.json()['punch_in'] == pin
    closed = client.post('/attendance/punch-out', json=dict(emp_code='EMP0001', punched_at=pout))
    assert closed.status_code == 200
    assert closed.json()['work_hours'] == 5.67 and closed.json()['overtime_minutes'] == 40
    assert closed.json()['history'] == []
    response = client.patch('/attendance/EMP0001/2026-07-06', json=dict(punch_in=milliseconds('2026-07-06T21:55:00+05:30'), reason='Clock correction', regularized_by='HR'))
    assert response.status_code == 200
    history = response.json()['history']
    assert len(history) == 1 and history[0]['changes']['late_minutes'] == {'from': 180, 'to': 0}
    assert isinstance(history[0]['changes']['punch_in']['from'], int)
    assert client.patch('/attendance/EMP0001/2026-07-06', json=dict(status='WFH', reason='No change here', regularized_by='HR')).status_code == 422
    leave = client.patch('/attendance/EMP0001/2026-07-06', json=dict(status='LEAVE', reason='Approved leave', regularized_by='HR'))
    assert leave.status_code == 200 and leave.json()['punch_in'] is None and leave.json()['work_hours'] is None
    assert len(leave.json()['history']) == 2

def parallel(count, fn):
    barrier = Barrier(count)
    def task(_):
        barrier.wait()
        return fn()
    with ThreadPoolExecutor(max_workers=count) as pool:
        return list(pool.map(task, range(count)))

def test_concurrent_create_punch_in_and_punch_out(mongo):
    _, client = mongo
    body = {k: v for k, v in employee('EMP0001').items() if k != 'created_at'}
    responses = parallel(8, lambda: client.post('/employees', json=body))
    assert sorted(r.status_code for r in responses) == [201]+[409]*7
    pin = dict(emp_code='EMP0001', punched_at=milliseconds('2026-07-06T09:40:01+05:30'))
    responses = parallel(8, lambda: client.post('/attendance/punch-in', json=pin))
    assert sorted(r.status_code for r in responses) == [201]+[409]*7
    pout = dict(emp_code='EMP0001', punched_at=milliseconds('2026-07-06T19:00:00+05:30'))
    responses = parallel(8, lambda: client.post('/attendance/punch-out', json=pout))
    assert sorted(r.status_code for r in responses) == [200]+[409]*7

def test_concurrent_corrections_preserve_history(seeded, monkeypatch):
    db, client = seeded
    barrier = Barrier(2)
    original = attendance_service.compare_filter
    def synchronized(record):
        result = original(record)
        barrier.wait(timeout=10)
        return result
    monkeypatch.setattr(attendance_service, 'compare_filter', synchronized)
    bodies = [dict(status='WFH', reason='Remote correction', regularized_by='HR1'), dict(status='ON_DUTY', reason='Duty correction', regularized_by='HR2')]
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda body: client.patch('/attendance/EMP0001/2026-07-06', json=body), bodies))
    assert sorted(r.status_code for r in responses) == [200, 409]
    stored = db.attendance_logs.find_one({'emp_code': 'EMP0001', 'date': '2026-07-06'})
    assert len(stored['history']) == 1

def test_noop_corrections_preserve_authoritative_metrics(seeded):
    db, client = seeded
    before = db.attendance_logs.find_one({'emp_code': 'EMP0001', 'date': '2026-07-06'})
    for fields in ({}, {'status': 'PRESENT'}, {'punch_in': milliseconds('2026-07-06T09:30:00+05:30')}):
        response = client.patch('/attendance/EMP0001/2026-07-06', json={
            **fields, 'reason': 'No actual change', 'regularized_by': 'HR',
        })
        assert response.status_code == 422
    assert db.attendance_logs.find_one({'_id': before['_id']}) == before

def test_leave_correction_cannot_supply_times_without_status(seeded):
    db, client = seeded
    before = db.attendance_logs.find_one({'emp_code': 'EMP0002', 'date': '2026-07-08'})
    response = client.patch('/attendance/EMP0002/2026-07-08', json={
        'punch_in': milliseconds('2026-07-08T09:30:00+05:30'),
        'reason': 'Invalid leave punch', 'regularized_by': 'HR',
    })
    assert response.status_code == 422
    assert db.attendance_logs.find_one({'_id': before['_id']}) == before

def scan_stages(value):
    if isinstance(value, dict):
        if 'stage' in value: yield value['stage']
        for child in value.values(): yield from scan_stages(child)
    elif isinstance(value, list):
        for child in value: yield from scan_stages(child)

def assert_indexed(result):
    stages = list(scan_stages(result['explain']))
    assert 'IXSCAN' in stages, stages
    assert 'COLLSCAN' not in stages, stages
    def check_lookup(value):
        if isinstance(value, dict):
            if 'collectionScans' in value: assert value['collectionScans'] == 0
            for v in value.values(): check_lookup(v)
        elif isinstance(value, list):
            for v in value: check_lookup(v)
    check_lookup(result['explain'])

EXPLAINS = [
    'attendance_list?emp_code=EMP0001&page_size=2',
    'attendance_list?status=WFH&page=2&page_size=2',
    'attendance_list?date_from=2026-07-01&date_to=2026-07-31',
    'employee_monthly?emp_code=EMP0001&month=2026-07',
    'department_summary?month=2026-07',
    'department_summary?month=2026-07&department=Engineering',
    'late_leaderboard?month=2026-07&limit=2',
    'department_trend?department=Engineering&from=2026-07-06&to=2026-07-12',
]

@pytest.mark.parametrize('query', EXPLAINS)
def test_explain_actual_queries_use_indexes(seeded, query):
    _, client = seeded
    assert_indexed(get(client, '/admin/explain/'+query))

@pytest.mark.performance
def test_100000_record_queries(mongo):
    if os.getenv('RUN_PERFORMANCE') != '1':
        pytest.skip('Set RUN_PERFORMANCE=1 for the 100000-document verification')
    db, client = mongo
    employees = [employee(f'EMP{i:04}', '2026-01-01') for i in range(1000)]
    db.employees.insert_many(employees)
    start = datetime(2026, 1, 1)
    for offset in range(100):
        day = (start+timedelta(days=offset)).date().isoformat()
        db.attendance_logs.insert_many([log(e['emp_code'], day, late=int(e['emp_code'][3:]) % 30) for e in employees])
    assert db.attendance_logs.count_documents({}) == 100000
    queries = [
        'attendance_list?page=3&page_size=20',
        'employee_monthly?emp_code=EMP0001&month=2026-02',
        'department_summary?month=2026-02',
        'late_leaderboard?month=2026-02&limit=10',
        'department_trend?department=Engineering&from=2026-02-01&to=2026-02-28',
    ]
    for query in queries: assert_indexed(get(client, '/admin/explain/'+query))
    assert get(client, '/attendance?page=3')['total'] == 100000
    assert len(get(client, '/analytics/departments/Engineering/trend?from=2026-02-01&to=2026-02-28')['items']) == 28

def test_errors_and_idempotent_startup_indexes(seeded):
    db, client = seeded
    database.create_indexes()
    database.create_indexes()
    assert db.employees.index_information()['employee_code']['unique'] is True
    assert db.attendance_logs.index_information()['attendance_employee_date']['unique'] is True
    assert get(client, '/health') == {'status': 'ok'}
    assert client.post('/attendance/punch-in', json={'emp_code': 'EMP9999'}).status_code == 404
    assert client.post('/attendance/punch-out', json={'emp_code': 'EMP0004'}).status_code == 404
    assert client.get('/analytics/employees/EMP9999/monthly?month=2026-07').status_code == 404
    assert client.get('/analytics/departments/summary?month=2026-13').status_code == 422
    assert client.get('/analytics/departments/Engineering/trend?from=2026-01-01&to=2026-04-03').status_code == 422
    assert client.patch('/attendance/EMP0004/2026-07-06', json=dict(status='LEAVE', reason='Approved leave', regularized_by='HR')).status_code == 404
    assert client.patch('/attendance/EMP0001/2026-07-06', json=dict(status='LEAVE', punch_in=milliseconds('2026-07-06T09:30:00+05:30'), reason='Approved leave', regularized_by='HR')).status_code == 422
    assert client.patch('/attendance/EMP0001/2026-07-06', json=dict(punch_in=milliseconds('2026-07-07T09:30:00+05:30'), reason='Wrong attendance day', regularized_by='HR')).status_code == 422
    early = dict(emp_code='EMP0003', punched_at=milliseconds('2026-07-09T09:30:00+05:30'))
    assert client.post('/attendance/punch-in', json=early).status_code == 201
    assert client.post('/attendance/punch-out', json=early).status_code == 422
    too_long = dict(emp_code='EMP0003', punched_at=milliseconds('2026-07-10T09:30:01+05:30'))
    assert client.post('/attendance/punch-out', json=too_long).status_code == 422
