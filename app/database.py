"""MongoDB connection and idempotent, named startup indexes."""
import os
from dotenv import load_dotenv
from pymongo import MongoClient
load_dotenv(override=False)
client = MongoClient(os.getenv('MONGO_URI', 'mongodb://localhost:27017'), tz_aware=True, serverSelectionTimeoutMS=3000, connectTimeoutMS=3000)
db = client[os.getenv('MONGO_DB', 'attendance_db')]

def create_indexes():
    db.employees.create_index([('emp_code', 1)], unique=True, name='employee_code')
    db.employees.create_index([('department', 1), ('emp_code', 1)], name='employee_department')
    db.employees.create_index([('joined_on', 1), ('department', 1)], name='employee_joined')
    db.attendance_logs.create_index([('emp_code', 1), ('date', -1)], unique=True, name='attendance_employee_date')
    db.attendance_logs.create_index([('date', -1), ('emp_code', 1)], name='attendance_date')
    db.attendance_logs.create_index([('status', 1), ('date', -1), ('emp_code', 1)], name='attendance_status_date')
    db.attendance_logs.create_index([('emp_code', 1), ('punch_in', -1)], name='attendance_punch')
