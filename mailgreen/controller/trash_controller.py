from typing import Dict, Any

from fastapi import APIRouter, Depends, Query, Body, HTTPException, status
from sqlalchemy.orm import Session
from googleapiclient.discovery import build
from urllib.error import HTTPError

from mailgreen.app.database import get_db
from mailgreen.app.schemas.mail import DeleteMailsRequest
from mailgreen.services.auth_service import get_credentials
from mailgreen.services.trash_service import trash_mails

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
    try:
        result = trash_mails(
            db=db,
            service=service,
            message_ids=payload.message_ids,
            confirm=payload.confirm,
            delete_protected_sender=payload.delete_protected_sender,
        )
    except HTTPError as he:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(he)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"알 수 없는 오류 발생: {e}",
        )

    return result
