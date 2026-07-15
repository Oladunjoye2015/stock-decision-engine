from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.api import compliance, decisions, executions, health, risk, shadow, signals, signalstack, tickets, tradingview
from app.config import get_settings
from app.core.logging import configure_logging
from app.database.engine import init_database


@asynccontextmanager
async def lifespan(_app: FastAPI):
    configure_logging(); init_database(); yield


settings = get_settings()
app = FastAPI(title=settings.app_name, version="1.0.0", lifespan=lifespan)


@app.get("/", include_in_schema=False)
def home():
    return RedirectResponse(url="/dashboard/", status_code=307)


for router in (health.router, signals.router, tradingview.router, decisions.router, tickets.router, risk.router, compliance.router, executions.router, signalstack.router, shadow.router): app.include_router(router)
app.mount("/dashboard", StaticFiles(directory="app/dashboard", html=True), name="dashboard")
