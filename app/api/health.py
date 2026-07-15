from fastapi import APIRouter
from sqlalchemy import text

from app.config import get_settings
from app.database.engine import engine

router = APIRouter(tags=["health"])


@router.get("/health")
def health(): return {"status": "ok", "service": get_settings().app_name}


@router.get("/ready")
def ready():
    with engine.connect() as connection: connection.execute(text("SELECT 1"))
    return {"status": "ready", "execution_mode": get_settings().execution_mode}

