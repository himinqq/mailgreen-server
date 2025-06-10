from pydantic import BaseModel
from uuid import UUID
from typing import Optional


class SubscriptionOut(BaseModel):
    id: UUID
    sender: str
    subject: str | None
    unsubscribe_link: str

    subject: Optional[str]
    snippet: Optional[str]

    class Config:
        from_attributes = True
