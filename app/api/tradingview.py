import hmac

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from app.api.signals import process_signal
from app.config import Settings, get_settings
from app.database.engine import SessionLocal
from app.schemas.signals import SignalIn, TradingViewSignalIn


router = APIRouter(prefix="/tradingview", tags=["tradingview"])


def _process_in_background(signal: SignalIn, settings: Settings):
    with SessionLocal() as db:
        process_signal(signal, db, settings)


@router.post("/signals")
def tradingview_signal(body: TradingViewSignalIn, background_tasks: BackgroundTasks, settings: Settings = Depends(get_settings)):
    expected = settings.tradingview_webhook_token
    if not expected or not hmac.compare_digest(body.webhook_token, expected):
        raise HTTPException(401, "Invalid TradingView webhook token")
    signal = SignalIn.model_validate(body.model_dump(exclude={"webhook_token"}))
    background_tasks.add_task(_process_in_background, signal, settings)
    return {"accepted": True, "signal_id": signal.signal_id, "processing": "background"}
