"""Compose domain routers."""
from fastapi import APIRouter
from app.routes import employees, attendance, analytics, admin

router = APIRouter()
for module in (employees, attendance, analytics, admin):
    router.include_router(module.router)
