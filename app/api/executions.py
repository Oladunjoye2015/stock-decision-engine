from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.engine import get_db
from app.database.models import ManualExecution, PaperExecution
from app.database.repositories import list_recent

router = APIRouter(prefix="/executions", tags=["executions"])


@router.get("")
def executions(db: Session = Depends(get_db)):
    values = list_recent(db, ManualExecution, 100) + list_recent(db, PaperExecution, 100)
    return [{"execution_id": x.execution_id, "ticket_id": x.ticket_id, "action": x.action, "price": x.price, "quantity": x.quantity, "fees": x.fees} for x in values]

