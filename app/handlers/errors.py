"""Database failures retain FastAPI's detail envelope."""
from fastapi.responses import JSONResponse
from pymongo.errors import PyMongoError

def register(app):
    @app.exception_handler(PyMongoError)
    async def database_error(request, exc):
        return JSONResponse(status_code=503, content={'detail': 'Database operation unavailable'})
