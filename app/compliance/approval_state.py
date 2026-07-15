from app.config import Settings


def current_approval(settings: Settings) -> dict:
    return {
        "written_approval_received": settings.signalstack_written_approval_confirmed,
        "account_program_approved": settings.signalstack_account_program_approved,
        "conditional_and_revocable": True,
        "signalstack_only": True,
        "direct_trade_the_pool_api": False,
        "beta": True,
    }


def validate_live_approval(settings: Settings) -> dict:
    missing = [name for name, value in settings.signalstack_safety_flags.items() if not value]
    return {"passed": not missing, "reason": "passed" if not missing else "missing prerequisites: " + ", ".join(missing), "missing": missing}

