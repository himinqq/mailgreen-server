from typing import Dict, Any

from fastapi import APIRouter, Depends, Query, Body
from sqlalchemy.orm import Session
from googleapiclient.discovery import build

from mailgreen.app.database import get_db
from mailgreen.app.schemas.mail import DeleteMailsRequest
from mailgreen.services.auth_service import get_credentials
from mailgreen.services.mail_service import trash_mails

router = APIRouter(prefix="/mail", tags=["trash"])


@router.delete("/trash", response_model=Dict[str, Any])
async def delete_mails(
    user_id: str = Query(..., description="User UUID"),
    payload: DeleteMailsRequest = Body(
        ..., description="삭제할 메일 ID 목록과 확인 여부"
    ),
    db: Session = Depends(get_db),
):
    creds = get_credentials(user_id)
    service = build("gmail", "v1", credentials=creds)
    return trash_mails(db, service, payload.message_ids, payload.confirm)
