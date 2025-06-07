from uuid import UUID
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from mailgreen.app.models import MailEmbedding, UserProtectedSender
from mailgreen.services.auth_service import get_credentials


class GmailServiceError(Exception):
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


class EmbeddingUpdateError(Exception):
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


class ProtectedSenderError(Exception):
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


def gmail_add_star_label(user_id: UUID, mail_id: str) -> None:
    try:
        creds = get_credentials(user_id)
    except Exception as e:
        raise GmailServiceError(
            status_code=401, detail=f"Gmail 인증 정보 조회 실패: {e}"
        )

    try:
        service = build("gmail", "v1", credentials=creds)
    except Exception as e:
        raise GmailServiceError(status_code=500, detail=f"Gmail 서비스 빌드 실패: {e}")

    try:
        service.users().messages().modify(
            userId="me", id=mail_id, body={"addLabelIds": ["STARRED"]}
        ).execute()
    except HttpError as e:
        detail = e.error_details if hasattr(e, "error_details") else str(e)
        status_code = e.status_code or 500
        raise GmailServiceError(
            status_code=status_code, detail=f"Gmail API 오류: {detail}"
        )


def gmail_remove_star_label(user_id: UUID, mail_id: str) -> None:
    try:
        creds = get_credentials(user_id)
    except Exception as e:
        raise GmailServiceError(
            status_code=401, detail=f"Gmail 인증 정보 조회 실패: {e}"
        )

    try:
        service = build("gmail", "v1", credentials=creds)
    except Exception as e:
        raise GmailServiceError(status_code=500, detail=f"Gmail 서비스 빌드 실패: {e}")

    try:
        service.users().messages().modify(
            userId="me", id=mail_id, body={"removeLabelIds": ["STARRED"]}
        ).execute()
    except HttpError as e:
        detail = e.error_details if hasattr(e, "error_details") else str(e)
        status_code = e.status_code or 500
        raise GmailServiceError(
            status_code=status_code, detail=f"Gmail API 오류: {detail}"
        )


def add_star_to_embedding_labels(user_id: UUID, mail_id: str, db: Session) -> None:
    mail_row = (
        db.query(MailEmbedding)
        .filter(MailEmbedding.user_id == user_id, MailEmbedding.gmail_msg_id == mail_id)
        .first()
    )
    if not mail_row:
        raise EmbeddingUpdateError(
            status_code=404, detail="임베딩 테이블에 해당 메일이 없습니다."
        )

    current_labels = mail_row.labels or []
    if "STARRED" not in current_labels:
        mail_row.labels = current_labels + ["STARRED"]
        try:
            db.add(mail_row)
            db.commit()
        except Exception as e:
            db.rollback()
            raise EmbeddingUpdateError(
                status_code=500, detail=f"임베딩 labels 업데이트 실패: {e}"
            )


def remove_star_from_embedding_labels(user_id: UUID, mail_id: str, db: Session) -> None:
    mail_row = (
        db.query(MailEmbedding)
        .filter(MailEmbedding.user_id == user_id, MailEmbedding.gmail_msg_id == mail_id)
        .first()
    )
    if not mail_row:
        raise EmbeddingUpdateError(
            status_code=404, detail="임베딩 테이블에 해당 메일이 없습니다."
        )

    current_labels = mail_row.labels or []
    if "STARRED" in current_labels:
        mail_row.labels = [lbl for lbl in current_labels if lbl != "STARRED"]
        try:
            db.add(mail_row)
            db.commit()
        except Exception as e:
            db.rollback()
            raise EmbeddingUpdateError(
                status_code=500, detail=f"임베딩 labels 업데이트 실패 (언스타): {e}"
            )


def add_protected_sender(user_id: UUID, sender_value: str, db: Session) -> None:
    entry = UserProtectedSender(user_id=user_id, sender_email=sender_value)
    try:
        db.add(entry)
        db.commit()
    except IntegrityError:
        db.rollback()  # 이미 등록된 경우 무시
    except Exception as e:
        db.rollback()
        raise ProtectedSenderError(
            status_code=500, detail=f"보호 발신자 등록 실패: {e}"
        )


def remove_protected_sender(user_id: UUID, mail_id: str, db: Session) -> None:
    mail_row = (
        db.query(MailEmbedding)
        .filter(MailEmbedding.user_id == user_id, MailEmbedding.gmail_msg_id == mail_id)
        .first()
    )
    if not mail_row or not mail_row.sender:
        return

    sender_value = mail_row.sender

    protected_entry = (
        db.query(UserProtectedSender)
        .filter(
            UserProtectedSender.user_id == user_id,
            UserProtectedSender.sender_email == sender_value,
        )
        .first()
    )
    if not protected_entry:
        return

    try:
        db.delete(protected_entry)
        db.commit()
    except Exception as e:
        db.rollback()
        raise ProtectedSenderError(
            status_code=500, detail=f"보호 발신자 삭제 실패: {e}"
        )
