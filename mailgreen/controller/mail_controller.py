import uuid
from datetime import datetime
from uuid import UUID

from fastapi import Depends, APIRouter, Query
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
    start_date: str = Query(None, description="조회 시작일 (YYYY-MM-DD)"),
    end_date: str = Query(None, description="조회 종료일 (YYYY-MM-DD)"),
    is_read: bool = Query(None, description="읽음 여부 필터 (true/false)"),
    db: Session = Depends(get_db),
):
    query = db.query(MailEmbedding)
    query = query.filter(
        MailEmbedding.user_id == user_id, MailEmbedding.sender.ilike(f"%{sender}%")
    )
    if start_date:
        dt = datetime.fromisoformat(start_date)
        query = query.filter(MailEmbedding.received_at >= dt)
    if end_date:
        dt = datetime.fromisoformat(end_date)
        query = query.filter(MailEmbedding.received_at <= dt)
    if is_read is not None:
        query = query.filter(MailEmbedding.is_read == is_read)

    mails = query.order_by(MailEmbedding.received_at.desc()).all()
    # 필요한 필드만 반환
    result = []
    for m in mails:
        result.append(
            {
                "id": str(m.gmail_msg_id),
                "subject": m.subject,
                "snippet": m.snippet,
                "received_at": m.received_at.isoformat(),
                "is_read": m.is_read,
            }
        )
    return result
