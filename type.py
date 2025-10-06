from pydantic import BaseModel


class Money(BaseModel):
    currency: str
    type: int
    amount: int