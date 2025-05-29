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
