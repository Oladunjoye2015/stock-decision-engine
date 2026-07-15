from app.database.models import AuditEvent, ComplianceEvent


def record(db, event_type: str, subject_id: str, data: dict, compliance: bool = False):
    model = ComplianceEvent if compliance else AuditEvent
    event = model(event_type=event_type, subject_id=subject_id, data=data)
    db.add(event); db.commit(); return event

