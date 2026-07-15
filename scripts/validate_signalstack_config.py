import json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.compliance.approval_state import validate_live_approval
from app.compliance.trade_the_pool_rules import policy_state
from app.config import get_settings


if __name__ == "__main__":
    settings = get_settings()
    print(json.dumps({"approval": validate_live_approval(settings), "policy": policy_state(settings), "outbound_transport_enabled": False}, default=str, indent=2))
