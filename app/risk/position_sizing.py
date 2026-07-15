import math

from app.core.exceptions import RiskCheckError


def calculate(entry_price: float, stop_price: float, buying_power: float, account_size: float, max_risk: float, max_symbol_exposure_pct: float, strategy_cap: int | None = None, volume_cap: int | None = None) -> dict:
    if entry_price <= 0 or stop_price <= 0: raise RiskCheckError("Entry and stop prices must be positive")
    risk_per_share = abs(entry_price - stop_price)
    if risk_per_share <= 0: raise RiskCheckError("Risk per share must be greater than zero")
    quantities = {
        "risk": math.floor(max_risk / risk_per_share),
        "buying_power": math.floor(buying_power / entry_price),
        "symbol_exposure": math.floor(account_size * max_symbol_exposure_pct / 100 / entry_price),
    }
    if strategy_cap is not None: quantities["strategy_cap"] = strategy_cap
    if volume_cap is not None: quantities["volume_rule"] = volume_cap
    quantity = min(quantities.values())
    if quantity < 1: raise RiskCheckError("Calculated quantity is below one")
    return {"quantity": quantity, "risk_per_share": risk_per_share, "estimated_risk_usd": quantity * risk_per_share, "limits": quantities}
