from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from uuid import UUID

from mailgreen.app.database import get_db
from mailgreen.app.models import MailEmbedding
from mailgreen.services.star_lable_service import (
    gmail_add_star_label,
    GmailServiceError,
    add_star_to_embedding_labels,
    EmbeddingUpdateError,
    gmail_remove_star_label,
    remove_star_from_embedding_labels,
    remove_protected_sender,
    add_protected_sender,
    ProtectedSenderError,
)

router = APIRouter(prefix="/mail", tags=["mail"])


@router.post("/{mail_id}/star", status_code=status.HTTP_200_OK)
def star_mail_controller(mail_id: str, user_id: UUID, db: Session = Depends(get_db)):

    mail_row = (
        db.query(MailEmbedding)
        .filter(MailEmbedding.user_id == user_id, MailEmbedding.gmail_msg_id == mail_id)
        .first()
    )
    if not mail_row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="해당 메일을 찾을 수 없습니다.",
        )

    try:
        gmail_add_star_label(user_id=user_id, mail_id=mail_id)
    except GmailServiceError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Gmail 별표 추가 실패: {e}",
        )

    try:
        add_star_to_embedding_labels(user_id=user_id, mail_id=mail_id, db=db)
    except EmbeddingUpdateError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"임베딩 테이블 업데이트 중 오류: {e}",
        )

    sender_value = mail_row.sender
    if sender_value:
        try:
            add_protected_sender(user_id=user_id, sender_value=sender_value, db=db)
        except ProtectedSenderError as e:
            raise HTTPException(status_code=e.status_code, detail=e.detail)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"보호 발신자 등록 중 예기치 못한 오류: {e}",
            )

    return {
        "status": "success",
        "message": "메일에 별표가 성공적으로 추가되었습니다. 발신자는 보호 테이블에 등록되었습니다.",
    }


@router.delete("/{mail_id}/star", status_code=status.HTTP_200_OK)
def unstar_mail_controller(mail_id: str, user_id: UUID, db: Session = Depends(get_db)):
    mail_row = (
        db.query(MailEmbedding)
        .filter(MailEmbedding.user_id == user_id, MailEmbedding.gmail_msg_id == mail_id)
        .first()
    )
    if not mail_row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="해당 메일을 찾을 수 없습니다.",
        )

    try:
        gmail_remove_star_label(user_id=user_id, mail_id=mail_id)
    except GmailServiceError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Gmail 별표 해제 실패: {e}",
        )

    try:
        remove_star_from_embedding_labels(user_id=user_id, mail_id=mail_id, db=db)
    except EmbeddingUpdateError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"임베딩 테이블 업데이트 중 오류 (언스타): {e}",
        )

    try:
        remove_protected_sender(user_id=user_id, mail_id=mail_id, db=db)
    except ProtectedSenderError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"보호 발신자 삭제 중 예기치 못한 오류: {e}",
        )

    return {
        "status": "success",
        "message": "메일의 별표가 해제되었고, 보호 발신자 등록이 해제되었습니다.",
    }
