from datetime import datetime
from typing import List, Tuple, Dict
from urllib.error import HTTPError

from googleapiclient.errors import HttpError
from sqlalchemy.orm import Session

from mailgreen.app.models import MailEmbedding, UserProtectedSender

CO2_PER_EMAIL_G = 4.0  # 메일 하나당 절감 탄소량(g)


def _find_protected(
    db: Session, message_ids: List[str]
) -> Tuple[List[str], Dict[str, str]]:
    protected_ids: List[str] = []
    id_to_sender: Dict[str, str] = {}

    for mid in message_ids:
        mail = db.query(MailEmbedding).filter(MailEmbedding.gmail_msg_id == mid).first()
        if not mail or not mail.sender:
            continue

        is_protected = (
            db.query(UserProtectedSender)
            .filter(
                UserProtectedSender.user_id == mail.user_id,
                UserProtectedSender.sender_email == mail.sender,
            )
            .first()
            is not None
        )
        if is_protected:
            protected_ids.append(mid)
            id_to_sender[mid] = mail.sender

    return protected_ids, id_to_sender


def trash_mails(
    db: Session,
    service,
    message_ids: List[str],
    confirm: bool = False,
    delete_protected_sender: bool = False,
) -> dict:
    estimated_saved = round(len(message_ids) * CO2_PER_EMAIL_G, 2)

    # 보호된 메시지 검사
    protected_ids, id_to_sender = _find_protected(db, message_ids)
    has_protected = bool(protected_ids)

    # 삭제 전 확인 (confirm=False 거나 보호된 삭제메일 있는 경우)
    if not confirm or (has_protected and not delete_protected_sender):
        return {
            "deleted": False,
            "estimated_carbon_saved_g": estimated_saved,
            "deleted_ids": (
                [f"{mid}" for mid in message_ids] if not has_protected else []
            ),
            "protected_ids": protected_ids,
            "protected_senders": [id_to_sender[mid] for mid in protected_ids],
            "errors": [],
        }

    # 실제 삭제 처리 (confirm=true)
    deleted_ids = []
    errors = []
    for mid in message_ids:
        try:
            service.users().messages().trash(userId="me", id=mid).execute()
            deleted_ids.append(mid)
        except HttpError as e:
            detail = None
            try:
                detail = e.error_details or e.content.decode()
            except Exception:
                pass
            errors.append(
                {
                    "msg_id": mid,
                    "error": f"Gmail API 에러: {e}",
                    "details": detail,
                }
            )
            continue

        # DB 상태 업데이트
        mail = db.query(MailEmbedding).filter(MailEmbedding.gmail_msg_id == mid).first()
        if mail:
            mail.is_deleted = True
            mail.deleted_at = datetime.utcnow()
        else:
            errors.append(
                {
                    "msg_id": mid,
                    "error": "DB에서 해당 Gmail 메시지 ID를 찾을 수 없습니다.",
                }
            )

    # 4) 커밋
    try:
        db.commit()
    except Exception as db_err:
        db.rollback()
        raise HTTPError(status_code=500, detail=f"DB 업데이트 실패: {db_err}")

    return {
        "deleted": True,
        "estimated_carbon_saved_g": estimated_saved,
        "deleted_ids": deleted_ids,
        "protected_ids": protected_ids,
        "protected_senders": [id_to_sender[mid] for mid in protected_ids],
        "errors": errors,
    }
