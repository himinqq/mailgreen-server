from mailgreen.services.assign_topic_service import batch_assign_category
from mailgreen.services.auth_service import get_credentials

from celery import Celery
from sqlalchemy.orm import Session
from mailgreen.app.database import SessionLocal
from mailgreen.app.models import MailEmbedding, AnalysisTask
from mailgreen.services.mail_service import (
    batch_fetch_metadata,
    initial_load,
)
from googleapiclient.discovery import build
from mailgreen.services.embed_service import get_embedding
from datetime import datetime, timezone
from typing import Optional

celery_app = Celery("mail_analysis", broker="redis://localhost:6379/0")


@celery_app.task(bind=True)
def run_analysis(
    self, user_id: str, task_id: str, start_history_id: Optional[str] = None
):
    db: Session = SessionLocal()
    try:
        # 1) Task 가져오기
        task: AnalysisTask = db.query(AnalysisTask).get(task_id)
        if not task:
            raise RuntimeError(f"Task {task_id} not found")

        # 2) history_id 결정 (초기엔 None)
        history_id = start_history_id or task.history_id

        # 3) Gmail API 클라이언트 준비
        creds = get_credentials(user_id)
        service = build("gmail", "v1", credentials=creds)

        # 4) 메일 목록 가져오기
        if history_id is None:
            # 초기 로드: 모든 메일
            mails = initial_load(service)
        else:
            # 변경분 로드: 새로 추가된 메일 ID만
            resp = (
                service.users()
                .history()
                .list(
                    userId="me",
                    startHistoryId=history_id,
                    historyTypes=["messageAdded"],
                )
                .execute()
            )
            ids = [
                m["message"]["id"]
                for h in resp.get("history", [])
                for m in h.get("messagesAdded", [])
            ]
            mails = batch_fetch_metadata(service, ids) if ids else []

        total = len(mails) or 1

        # 5) 각 메일 삽입 (중복 체크 없음)
        for idx, mail in enumerate(mails, start=1):
            emb = MailEmbedding(
                user_id=user_id,
                gmail_msg_id=mail["id"],
                sender=mail["from"],
                subject=mail["subject"],
                snippet=mail["snippet"],
                size_bytes=mail["size"],
                is_read=mail["isRead"],
                is_starred=mail["isStarred"],
                labels=mail["labels"],
                received_at=datetime.fromisoformat(mail["timestamp"]),
                vector=get_embedding(mail["subject"] + " " + mail["snippet"]),
                processed_at=datetime.now(timezone.utc),
            )
            db.add(emb)

            # 5% 단위로만 진행률 갱신
            pct = int(idx / total * 100)
            if pct % 5 == 0:
                task.progress_pct = pct
                db.commit()

        # 6) 다음 history_id 저장, 상태 업데이트
        new_history = service.users().getProfile(userId="me").execute().get("historyId")
        task.history_id = new_history
        task.status = "done"
        task.progress_pct = 100
        task.finished_at = datetime.now(timezone.utc)
        db.commit()

        batch_assign_category()

    except Exception as e:
        # 에러 처리
        if task:
            task.status = "failed"
            task.error_msg = str(e)
            db.commit()
        raise

    finally:
        db.close()
