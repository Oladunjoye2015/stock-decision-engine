import json
from pathlib import Path

from fastapi import APIRouter

from app.config import get_settings

router=APIRouter(prefix="/shadow",tags=["shadow"])
STATE_FILES={"breakout":Path("data/breakout_shadow_state.json"),"breakout_ml_filter":Path("data/breakout_ml_shadow_state.json"),"long_trend":Path("data/forward_shadow_state.json"),"refresh":Path("data/alpaca_refresh_manifest.json"),"consolidated":Path("data/shadow_status.json"),"hourly_scanner":Path("data/hourly_breakout_scanner_state.json")}
STATE_KEYS={"breakout":"breakout_shadow_state","breakout_ml_filter":"breakout_ml_shadow_state","long_trend":"forward_shadow_state","refresh":"alpaca_refresh_manifest","consolidated":"shadow_status","hourly_scanner":"hourly_breakout_scanner_state"}


def read_state(path:Path):
    if not path.exists(): return {"available":False,"path":str(path)}
    try: return {"available":True,**json.loads(path.read_text())}
    except (OSError,json.JSONDecodeError) as exc: return {"available":False,"path":str(path),"error":type(exc).__name__}


@router.get("/status")
def shadow_status():
    if get_settings().runtime_storage=="database":
        from app.database.runtime_store import load_runtime_state
        states={name:({"available":True,**value} if (value:=load_runtime_state(key)) is not None else {"available":False,"storage":"database"}) for name,key in STATE_KEYS.items()}
    else: states={name:read_state(path) for name,path in STATE_FILES.items()}
    return {"execution_enabled":False,"automatic_promotion_enabled":False,"runtime_storage":get_settings().runtime_storage,"states":states}
