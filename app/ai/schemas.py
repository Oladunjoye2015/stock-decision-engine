from pydantic import BaseModel, Field


class AIReviewResult(BaseModel):
    approved: bool
    confidence: float = Field(ge=0, le=1)
    reason: str
    primary_risks: list[str] = []
    invalidation_condition: str = ""
    recommended_action: str

