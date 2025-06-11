from typing import List

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from mailgreen.app.database import get_db
from mailgreen.app.schemas.keyword import TopKeywordOut
from mailgreen.app.schemas.mail import MailOut
from mailgreen.services.keyword_service import (
    get_top_keywords,
    get_keyword_details,
    get_keyword_details_count,
)

router = APIRouter(prefix="/keyword", tags=["keyword"])


@router.get("/top", response_model=List[TopKeywordOut])
async def top_keywords(
    user_id: str = Query(..., description="User UUID"),
    limit: int = Query(3, description="최대 대주제 수"),
    db: Session = Depends(get_db),
):
    raw = get_top_keywords(db, user_id, limit)
    return [TopKeywordOut(**r) for r in raw]


@router.get("", response_model=List[MailOut])
async def keyword_details(
    user_id: str = Query(..., description="User UUID"),
    topic_id: int = Query(..., description="조회할 대주제 ID (MajorTopic.id)"),
    start_date: str | None = Query(None, description="조회 시작일 (YYYY-MM-DD)"),
    end_date: str | None = Query(None, description="조회 종료일 (YYYY-MM-DD)"),
    is_read: bool | None = Query(None, description="읽음 여부 필터 (true/false)"),
    older_than_months: int | None = Query(
        None, description="지정 개월 이전 메일만 조회"
    ),
    min_size_mb: float | None = Query(
        None, description="필터 기준 메일 크기 (MB 단위)"
    ),
    db: Session = Depends(get_db),
):
    mails = get_keyword_details(
        db,
        user_id,
        topic_id=topic_id,
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
            starred=("STARRED" in (m.labels or [])),
        )
        for m in mails
    ]


@router.get("/counts")
async def keyword_sender_counts(
    user_id: str = Query(..., description="User UUID"),
    topic_id: int | None = Query(None, description="조회할 대주제 ID (MajorTopic.id)"),
    start_date: str | None = Query(None, description="조회 시작일 (YYYY-MM-DD)"),
    end_date: str | None = Query(None, description="조회 종료일 (YYYY-MM-DD)"),
    is_read: bool | None = Query(None, description="읽음 여부 필터 (true/false)"),
    older_than_months: int | None = Query(
        None, description="지정 개월 이전 메일만 조회"
    ),
    min_size_mb: float | None = Query(
        None, description="필터 기준 메일 크기 (MB 단위)"
    ),
    db: Session = Depends(get_db),
):
    result = get_keyword_details_count(
        db,
        user_id,
        topic_id=topic_id,
        start_date=start_date,
        end_date=end_date,
        is_read=is_read,
        older_than_months=older_than_months,
        min_size_mb=min_size_mb,
    )
    return result
