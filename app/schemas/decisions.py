from pydantic import BaseModel


class DecisionOut(BaseModel):
    decision_id: str
    signal_id: str
    final_decision: str
    reason: str

