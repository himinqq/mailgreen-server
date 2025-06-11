from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID

from mailgreen.app.database import get_db
from mailgreen.app.schemas.subscription import SubscriptionOut
from mailgreen.services.subscription_service import (
    sync_subscriptions,
    unsubscribe_subscription,
    get_subscriptions,
)

router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])


class SenderCount(BaseModel):
    sender: str
    name: str
    count: int


@router.post("/sync", response_model=List[SubscriptionOut])
async def sync_subscriptions(user_id: UUID, db: Session = Depends(get_db)):
    try:
        return sync_subscriptions(db, str(user_id))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("", response_model=List[SenderCount])
async def list_subscriptions(
    user_id: UUID = Query(..., description="User UUID"),
    limit: int = Query(10, description="최대 발신자 수"),
    db: Session = Depends(get_db),
):
    try:
        return get_subscriptions(db, str(user_id), limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{sub_id}/unsubscribe")
async def unsubscribe_sub(sub_id: UUID, db: Session = Depends(get_db)):
    try:
        unsubscribe_subscription(db, str(sub_id))
        return {"detail": "Unsubscribed successfully"}
    except ValueError:
        raise HTTPException(status_code=404, detail="Subscription not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
