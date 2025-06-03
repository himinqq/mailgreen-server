from typing import Dict
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from mailgreen.app.database import get_db
from mailgreen.services.mail_service import start_analysis_task, get_analysis_progress

router = APIRouter(prefix="/mail", tags=["mail"])


@router.post("/analyze")
def analyze_mail(user_id: UUID, db: Session = Depends(get_db)) -> Dict[str, str]:
    start_history_id = start_analysis_task(db, str(user_id))
    return {"message": "분석을 시작했습니다.", "start_history_id": start_history_id}


@router.get("/progress")
async def get_mail_progress(
    user_id: str = Query(..., description="User UUID"), db: Session = Depends(get_db)
):
    return get_analysis_progress(db, user_id)
