from datetime import datetime
from typing import List
from urllib.error import HTTPError

from googleapiclient.errors import HttpError
from sqlalchemy.orm import Session

from mailgreen.app.models import MailEmbedding

CO2_PER_EMAIL_G = 4.0  # 메일 하나당 절감 탄소량(g)


def trash_mails(
    db: Session,
    service,
    message_ids: List[str],
    confirm: bool = False,
) -> dict:
    count = len(message_ids)
    estimated_saved = round(count * CO2_PER_EMAIL_G, 2)
    deleted_ids = []
    errors = []

    if not confirm:
        for gmail_msg_id in message_ids:
            deleted_ids.append(f"{gmail_msg_id} (dry-run)")
        return {
            "requested_count": count,
            "deleted": False,
            "estimated_carbon_saved_g": estimated_saved,
            "deleted_ids": deleted_ids,
            "errors": [],
        }

    for gmail_msg_id in message_ids:
        try:
            service.users().messages().trash(userId="me", id=gmail_msg_id).execute()
            deleted_ids.append(gmail_msg_id)
        except HttpError as e:
            error_detail = None
            try:
                error_detail = e.error_details or e.content.decode()
            except:
                pass
            errors.append(
                {
                    "msg_id": gmail_msg_id,
                    "error": f"Gmail API 에러: {str(e)}",
                    "details": error_detail,
                }
            )
            continue

        record = (
            db.query(MailEmbedding)
            .filter(MailEmbedding.gmail_msg_id == gmail_msg_id)
            .first()
        )
        if record:
            record.is_deleted = True
            record.deleted_at = datetime.utcnow()
        else:
            errors.append(
                {
                    "msg_id": gmail_msg_id,
                    "error": "DB에서 해당 Gmail 메시지 ID를 찾을 수 없습니다.",
                }
            )

    try:
        db.commit()
    except Exception as db_err:
        db.rollback()
        raise HTTPError(status_code=500, detail=f"DB 업데이트 실패: {str(db_err)}")

    return {
        "requested_count": count,
        "deleted": True,
        "estimated_carbon_saved_g": estimated_saved,
        "deleted_ids": deleted_ids,
        "errors": errors,
    }
