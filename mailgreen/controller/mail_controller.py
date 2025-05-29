import uuid
from datetime import datetime, timezone
from uuid import UUID

from dateutil.relativedelta import relativedelta
from fastapi import Depends, APIRouter, Query, HTTPException
from sqlalchemy.orm import Session

from mailgreen.app.database import get_db
from mailgreen.tasks.mail_analysis import run_analysis
from mailgreen.app.models import AnalysisTask, MailEmbedding

router = APIRouter(prefix="/mail", tags=["mail"])


@router.post("/analyze")
def analyze_mail(user_id: UUID, db: Session = Depends(get_db)):
    task_id = str(uuid.uuid4())

    task = AnalysisTask(
        id=task_id,
        user_id=user_id,
        task_type="email-analysis",
        status="pending",
        progress_pct=0,
        started_at=datetime.utcnow(),
    )
    db.add(task)
    db.commit()
    run_analysis.delay(user_id=user_id, task_id=task_id, limit=50)
    return {"message": "분석을 시작했습니다."}


@router.get("/progress")
async def get_mail_progress(
    user_id: str = Query(..., description="User UUID"), db: Session = Depends(get_db)
):
    # 해당 사용자 가장 최근 태스크 조회
    task = (
        db.query(AnalysisTask)
        .filter(AnalysisTask.user_id == user_id)
        .order_by(AnalysisTask.started_at.desc())
        .first()
    )
    if not task:
        # 태스크가 없으면 진행 중 아님
        return {"in_progress": False, "progress_pct": 0}

    in_progress = task.status != "done"
    return {"in_progress": in_progress, "progress_pct": task.progress_pct or 0}


@router.get("/sender/top")
async def get_top_senders(
    user_id: str = Query(..., description="User UUID"),
    limit: int = Query(3, description="최대 발신자 수"),
    db: Session = Depends(get_db),
):
    from sqlalchemy import func
    from mailgreen.app.models import MailEmbedding
    from email.utils import parseaddr

    # 발신자별 메일 수 집계
    rows = (
        db.query(
            MailEmbedding.sender.label("sender"),
            func.count(MailEmbedding.id).label("count"),
        )
        .filter(MailEmbedding.user_id == user_id)
        .group_by(MailEmbedding.sender)
        .order_by(func.count(MailEmbedding.id).desc())
        .limit(limit)
        .all()
    )
    result = []
    for r in rows:
        name, _ = parseaddr(r.sender or "")
        sender_name = name if name else "(Unknown)"
        result.append({"sender": r.sender, "name": sender_name, "count": r.count})
    return result


@router.get("/sender")
async def get_sender_details(
    user_id: str = Query(..., description="User UUID"),
    sender: str = Query(..., description="발신자 이메일 or 이름"),
    start_date: str | None = Query(None, description="조회 시작일 (YYYY-MM-DD)"),
    end_date: str | None = Query(None, description="조회 종료일 (YYYY-MM-DD)"),
    is_read: bool | None = Query(None, description="읽음 여부 필터 (true/false)"),
    older_than_months: int | None = Query(
        None, description="지정 개월 이전 메일만 조회 (예: 1 → 1개월 이전 메일)"
    ),
    min_size_mb: float | None = Query(
        None, description="필터 기준 메일 크기 (MB 단위, 예: 0.1, 0.5, 1)"
    ),
    db: Session = Depends(get_db),
):
    # 기본 sender/UUID 필터
    query = db.query(MailEmbedding).filter(
        MailEmbedding.user_id == user_id,
        MailEmbedding.sender.ilike(f"%{sender}%"),
    )

    # 날짜 범위 필터
    if start_date:
        try:
            dt_start = datetime.fromisoformat(start_date)
        except ValueError:
            raise HTTPException(400, "start_date 형식 오류 (YYYY-MM-DD)")
        query = query.filter(MailEmbedding.received_at >= dt_start)

    if end_date:
        try:
            dt_end = datetime.fromisoformat(end_date)
        except ValueError:
            raise HTTPException(400, "end_date 형식 오류 (YYYY-MM-DD)")
        query = query.filter(MailEmbedding.received_at <= dt_end)

    # Is Read: 읽음 여부 필터
    if is_read is not None:
        query = query.filter(MailEmbedding.is_read == is_read)

    # Old Mail: 지정 개월 이전 메일만
    if older_than_months is not None:
        cutoff = datetime.now(timezone.utc) - relativedelta(months=older_than_months)
        query = query.filter(MailEmbedding.received_at <= cutoff)

    # Large Mail: 지정 MB 이상 크기만 필터링
    if min_size_mb is not None:
        # 사용자 입력은 MB 단위 (소수 가능), 저장은 바이트 단위
        try:
            bytes_threshold = int(
                float(min_size_mb) * 1024 * 1024
            )  # ex. 0.1MB → 104857 bytes
        except ValueError:
            raise HTTPException(status_code=400, detail="min_size_mb must be a number")

        query = query.filter(MailEmbedding.size_bytes >= bytes_threshold)

    # 정렬 및 결과 반환
    mails = query.order_by(MailEmbedding.received_at.desc()).all()

    return [
        {
            "id": m.gmail_msg_id,
            "subject": m.subject,
            "snippet": m.snippet,
            "received_at": m.received_at.isoformat(),
            "is_read": m.is_read,
        }
        for m in mails
    ]
