from mailgreen.services.assign_topic_service import batch_assign_category
from mailgreen.services.auth_service import get_credentials

from celery import Celery
from sqlalchemy.orm import Session
from mailgreen.app.database import SessionLocal
from mailgreen.app.models import MailEmbedding, AnalysisTask
from mailgreen.services.mail_service import (
    batch_fetch_metadata,
    initial_load,
    logger,
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

    orig_history = None
    processed_count = 0
    total = 1

    try:
        task: AnalysisTask = db.query(AnalysisTask).get(task_id)
        if not task:
            raise RuntimeError(f"Task {task_id} not found")

        orig_history = task.history_id

        history_id = start_history_id or task.history_id

        creds = get_credentials(user_id)
        service = build("gmail", "v1", credentials=creds)

        if history_id is None:
            mails = initial_load(service)
        else:
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

        for idx, mail in enumerate(mails, start=1):
            processed_count = idx
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

            pct = int(idx / total * 100)
            if pct % 5 == 0:
                task.progress_pct = pct
                db.commit()

        new_history = service.users().getProfile(userId="me").execute().get("historyId")
        task.history_id = new_history
        task.status = "done"
        task.progress_pct = 100
        task.finished_at = datetime.now(timezone.utc)
        db.commit()

    except Exception as e:
        if task:
            task.history_id = orig_history
            if processed_count:
                task.progress_pct = int(processed_count / total * 100)
            else:
                task.progress_pct = 0

            task.status = "failed"
            task.error_msg = str(e)
            task.finished_at = datetime.now(timezone.utc)
            db.commit()

        logger.error(f"[run_analysis] 예외 발생: {e}", exc_info=True)
    finally:
        try:
            batch_assign_category()
        except Exception as e2:
            logger.error(
                f"[run_analysis] batch_assign_category 중 예외 발생: {e2}",
                exc_info=True,
            )
        db.close()
