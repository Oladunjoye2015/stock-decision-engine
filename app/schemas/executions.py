from pydantic import BaseModel


class ExecutionOut(BaseModel):
    execution_id: str
    ticket_id: str
    action: str
    price: float
    quantity: float

