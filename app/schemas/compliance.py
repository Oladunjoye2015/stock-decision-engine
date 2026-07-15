from pydantic import BaseModel


class ComplianceStatus(BaseModel):
    compliant: bool
    reason: str
