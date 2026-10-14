"""Validation and readiness checks do not require a MongoDB server."""
from fastapi.testclient import TestClient
from pymongo.errors import ConnectionFailure
from app.main import app
from app import database

client = TestClient(app)  # No context manager: unit checks deliberately omit startup.

def test_health_checks_database(monkeypatch):
    class DB:
        def command(self, name): raise ConnectionFailure('offline')
    monkeypatch.setattr(database, 'db', DB())
    response = client.get('/health')
    assert response.status_code == 503
    assert 'x-request-id' in response.headers

def test_invalid_inputs_do_not_touch_database():
    for url in ('/attendance?page=0', '/employees?page_size=101', '/attendance?status=INVALID', '/attendance?date_from=', '/analytics/leaderboard/late?month=2026-07&limit=51'):
        assert client.get(url).status_code == 422
    assert client.post('/attendance/punch-in', json={'emp_code': 'EMP0001', 'punched_at': '1783312500000'}).status_code == 422
    assert client.get('/attendance?date_from=2026-02-30').status_code == 422
    assert client.get('/admin/explain/employee_monthly').status_code == 422
    assert client.get('/admin/explain/invalid').status_code == 422


def test_all_contract_routes_registered():
    expected = {('/health', 'GET'), ('/employees', 'GET'), ('/employees', 'POST'), ('/attendance', 'GET'), ('/attendance/punch-in', 'POST'), ('/attendance/punch-out', 'POST'), ('/attendance/{emp_code}/{date}', 'PATCH'), ('/analytics/employees/{emp_code}/monthly', 'GET'), ('/analytics/departments/summary', 'GET'), ('/analytics/leaderboard/late', 'GET'), ('/analytics/departments/{department}/trend', 'GET'), ('/admin/explain/{endpoint}', 'GET')}
    actual = {(route.path, method) for route in app.routes for method in getattr(route, 'methods', [])}
    assert expected <= actual
