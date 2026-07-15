from app.compliance.approval_state import current_approval
from app.compliance.trade_the_pool_rules import policy_state


def status(settings) -> dict:
    policy = policy_state(settings)
    return {"compliant": settings.execution_mode != "signalstack" or (policy["complete"] and not policy["stale"]), "execution_mode": settings.execution_mode, "direct_trade_the_pool": "prohibited", "alpaca_connectivity": "absent", "signalstack": "validated queue; outbound transport disabled pending exact official account payload", "signalstack_prerequisites": settings.signalstack_safety_flags, "approval": current_approval(settings), "policy": policy, "disclaimer": "Local checks do not guarantee compliance."}
