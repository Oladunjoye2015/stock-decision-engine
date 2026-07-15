from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.compliance.approval_state import current_approval
from app.compliance.audit import record
from app.compliance.trade_the_pool_rules import policy_state
from app.compliance.rule_engine import status
from app.config import get_settings
from app.database.engine import get_db
from app.database.models import PolicyVersion

router = APIRouter(prefix="/compliance", tags=["compliance"])


@router.get("/status")
def compliance_status(): return status(get_settings())


@router.get("/approval")
def approval(): return current_approval(get_settings())


@router.post("/verify-policy")
def verify_policy(db: Session = Depends(get_db)):
    settings = get_settings(); state = policy_state(settings)
    event = PolicyVersion(event_type="policy_verification", subject_id=settings.ttp_rule_version or "unconfigured", data=state); db.add(event); db.commit()
    record(db, "policy_verification", settings.ttp_rule_version or "unconfigured", state, True)
    return state
