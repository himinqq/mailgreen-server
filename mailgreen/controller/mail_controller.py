from typing import Dict
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from celery.result import AsyncResult
from mailgreen.tasks.mail_analysis import celery_app
from mailgreen.app.database import get_db
from mailgreen.services.mail_service import start_analysis_task, get_analysis_progress

router = APIRouter(prefix="/mail", tags=["mail"])


@router.post("/analyze")
def analyze_mail(user_id: UUID, db: Session = Depends(get_db)) -> Dict[str, str]:
    start_history_id = start_analysis_task(db, str(user_id))
    return {"message": "분석을 시작했습니다.", "start_history_id": start_history_id}


@router.get("/progress/{task_id}")
def progress(task_id: str):
    result = AsyncResult(task_id, app=celery_app)
    return {"state": result.state, "meta": result.info or {}}


@router.get("", summary="사용자별 분석 진행률")
def get_mail_progress(
    user_id: UUID = Query(..., description="User UUID"),
    db: Session = Depends(get_db),
):
    return get_analysis_progress(db, str(user_id))
