from datetime import timedelta

from app.compliance.approval_state import validate_live_approval
from app.core.time_utils import ensure_utc, utc_now


def policy_state(settings) -> dict:
    missing = [name for name, value in {"account_program": settings.ttp_account_program, "rule_version": settings.ttp_rule_version, "rule_last_verified_at": settings.ttp_rule_last_verified_at, "daily_pause_threshold": settings.ttp_daily_pause_threshold_usd, "maximum_loss_limit": settings.ttp_maximum_loss_limit_usd}.items() if value in {None, ""}]
    stale = True
    if settings.ttp_rule_last_verified_at:
        stale = ensure_utc(settings.ttp_rule_last_verified_at) < utc_now() - timedelta(days=settings.ttp_policy_stale_after_days)
    return {"complete": not missing, "stale": stale, "missing": missing, "rule_version": settings.ttp_rule_version, "last_verified_at": settings.ttp_rule_last_verified_at.isoformat() if settings.ttp_rule_last_verified_at else None}


def evaluate(settings, side: str, entry: float, target: float, daily_state, volume_check: dict | None, rate_state: dict, execution_mode: str) -> dict:
    expected = abs(target-entry); checks = {
        "signalstack_only_execution": execution_mode == "signalstack",
        "approval": validate_live_approval(settings)["passed"],
        "account_program": bool(settings.ttp_account_program),
        "policy_current": policy_state(settings)["complete"] and not policy_state(settings)["stale"],
        "daily_pause": not daily_state.daily_pause,
        "maximum_loss": not daily_state.maximum_loss_buffer_reached,
        "ten_cent_rule": expected >= settings.ttp_min_profit_movement_per_share_usd,
        "volume_rule": bool(volume_check and volume_check.get("passed")),
        "request_rate": bool(rate_state.get("allowed")),
        "short_permission": side != "short" or settings.ttp_allow_shorts,
        "reconciled": daily_state.reconciled,
        "kill_switch": not daily_state.kill_switch,
    }
    if execution_mode != "signalstack":
        checks = {"signalstack_only_execution": True, "local_mode_no_external_execution": True}
    failed = [name for name, passed in checks.items() if not passed]
    return {"passed": not failed, "reason": "passed" if not failed else "failed rules: " + ", ".join(failed), "checks": checks, "rule_version": settings.ttp_rule_version, "policy": policy_state(settings), "expected_movement_per_share": expected, "request_rate_state": rate_state, "disclaimer": "Local checks do not guarantee Trade The Pool compliance."}


def validate_planned_exit(entry_time, planned_exit_time, entry_price: float, exit_price: float, settings, emergency: bool = False) -> dict:
    held = (ensure_utc(planned_exit_time)-ensure_utc(entry_time)).total_seconds(); movement = abs(exit_price-entry_price); reasons = []
    if held < settings.ttp_min_hold_seconds and not emergency: reasons.append("30-second rule conflict")
    if exit_price != entry_price and movement + 1e-9 < settings.ttp_min_profit_movement_per_share_usd: reasons.append("10-cent rule conflict")
    if emergency and held < settings.ttp_min_hold_seconds: reasons.append("emergency interpretation requires current official policy review")
    return {"passed": not reasons, "reason": "passed" if not reasons else "; ".join(reasons), "hold_seconds": held, "movement_per_share": movement, "emergency": emergency}
