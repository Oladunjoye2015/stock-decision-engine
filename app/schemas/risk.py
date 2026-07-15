from pydantic import BaseModel


class KillSwitchRequest(BaseModel):
    reason: str = "manual"


class ReconcileRequest(BaseModel):
    realized_pnl: float = 0
    open_risk: float = 0
    trades_count: int = 0

