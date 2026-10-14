"""Employee Attendance & Analytics API. Run uvicorn app.main:app --port 8000."""
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from pymongo.errors import PyMongoError
from starlette.concurrency import run_in_threadpool
from app import database
from app.handlers.errors import register
from app.middleware.request_id import RequestIdMiddleware
from app.routes.api import router

@asynccontextmanager
async def lifespan(app):
    # Startup is not ready until the database and all indexes are available.
    await run_in_threadpool(database.create_indexes)
    try:
        yield
    finally:
        database.client.close()

app = FastAPI(title='Employee Attendance & Analytics API', version='2.0.0', lifespan=lifespan)
app.add_middleware(RequestIdMiddleware)
register(app)
app.include_router(router)

@app.get('/health', tags=['system'])
def health():
    try:
        database.db.command('ping')
    except PyMongoError:
        raise HTTPException(503, 'MongoDB unavailable')
    return {'status': 'ok'}
