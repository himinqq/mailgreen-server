from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID

from mailgreen.app.database import get_db
from mailgreen.app.schemas.subscription import SubscriptionSyncResult, SubscriptionOut
from mailgreen.services.subscription_service import (
    sync_user_subscriptions,
    unsubscribe_subscription,
    get_user_subscriptions,
)

router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])


class SenderCount(BaseModel):
    sub_id: UUID
    sender: str
    name: str
    count: int


@router.get("", response_model=List[SenderCount])
async def list_subscriptions(
    user_id: UUID = Query(..., description="User UUID"), db: Session = Depends(get_db)
):
    try:
        return get_user_subscriptions(db, str(user_id))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sync", response_model=SubscriptionSyncResult)
async def sync_subscriptions(user_id: UUID, db: Session = Depends(get_db)):
    try:
        subs_list = sync_user_subscriptions(db, str(user_id))
        new_models = [SubscriptionOut.model_validate(sub) for sub in subs_list]

        return SubscriptionSyncResult(
            success=True,
            new_count=len(new_models),
            new_subscriptions=new_models,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{sub_id}/unsubscribe")
async def unsubscribe_sub(sub_id: UUID, db: Session = Depends(get_db)):
    try:
        unsubscribe_subscription(db, str(sub_id))
        return {"detail": "Unsubscribed successfully"}

    # 400 계열: 구독 없음(404) / 이미 취소(409) / 그 외(400)
    except ValueError as e:
        msg = str(e)
        if msg == "Subscription not found":
            raise HTTPException(status_code=404, detail=msg)
        if msg == "Already unsubscribed":
            raise HTTPException(
                status_code=409, detail="이미 구독이 취소된 항목입니다."
            )
        # 그 외 Stibee API의 400 에러 메시지
        raise HTTPException(status_code=400, detail=msg)

    # 외부 요청(5xx, 네트워크 에러) 실패 → 502
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))

    # 그 밖의 예기치 못한 에러 → 500
    except Exception:
        raise HTTPException(status_code=500, detail="Internal server error")
