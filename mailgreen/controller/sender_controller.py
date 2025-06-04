from typing import List, Dict, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from mailgreen.app.database import get_db
from mailgreen.app.schemas.mail import MailOut
from mailgreen.services.mail_service import get_top_senders, get_sender_details, get_sender_details_count

router = APIRouter(prefix="/sender", tags=["sender"])


@router.get("/top", response_model=List[Dict])
async def top_senders(
    user_id: str = Query(..., description="User UUID"),
    limit: int = Query(..., description="최대 발신자 수"),
    db: Session = Depends(get_db),
):
    return get_top_senders(db, user_id, limit)


@router.get("", response_model=List[MailOut])
async def sender_details(
    user_id: str = Query(..., description="User UUID"),
    sender: Optional[str] = Query(None, description="발신자 이메일 or 이름"),
    start_date: Optional[str] = Query(None, description="조회 시작일 (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="조회 종료일 (YYYY-MM-DD)"),
    is_read: Optional[bool] = Query(None, description="읽음 여부 필터 (true/false)"),
    older_than_months: Optional[int] = Query(
        None, description="지정 개월 이전 메일만 조회"
    ),
    min_size_mb: Optional[float] = Query(
        None, description="필터 기준 메일 크기 (MB 단위)"
    ),
    db: Session = Depends(get_db),
):
    mails = get_sender_details(
        db,
        user_id,
        sender=sender,
        start_date=start_date,
        end_date=end_date,
        is_read=is_read,
        older_than_months=older_than_months,
        min_size_mb=min_size_mb,
    )
    return [
        MailOut(
            id=m.gmail_msg_id,
            subject=m.subject,
            snippet=m.snippet,
            received_at=m.received_at.isoformat(),
            is_read=m.is_read,
        )
        for m in mails
    ]

@router.get("/counts")
async def get_sender_counts(
    user_id: str = Query(..., description="User UUID"),
     sender: Optional[str] = Query(None, description="발신자 이메일 or 이름"),
    start_date: Optional[str] = Query(None, description="조회 시작일 (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="조회 종료일 (YYYY-MM-DD)"),
    is_read: Optional[bool] = Query(None, description="읽음 여부 필터 (true/false)"),
    older_than_months: Optional[int] = Query(
        None, description="지정 개월 이전 메일만 조회"
    ),
    min_size_mb: Optional[float] = Query(
        None, description="필터 기준 메일 크기 (MB 단위)"
    ),
    db: Session = Depends(get_db),
): 
    
    return get_sender_details_count(
        db,
        user_id,
        sender,
        start_date,
        end_date,
        is_read,
        older_than_months,
        min_size_mb
    )
