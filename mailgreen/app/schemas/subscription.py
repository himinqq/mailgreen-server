from pydantic import BaseModel
from uuid import UUID
from typing import List


class SubscriptionOut(BaseModel):
    id: UUID
    sender: str
    unsubscribe_link: str

    class Config:
        from_attributes = True


class SubscriptionSyncResult(BaseModel):
    success: bool
    new_count: int
    new_subscriptions: List[SubscriptionOut]
