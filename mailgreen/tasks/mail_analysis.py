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
from typing import Optional, List

celery_app = Celery(
    "mail_analysis",
    broker="redis://localhost:6379/0",
    result_backend="redis://localhost:6379/1",
)


@celery_app.task(bind=True)
def run_analysis(
    self, user_id: str, task_id: str, start_history_id: Optional[str] = None
):
    db: Session = SessionLocal()
    task: AnalysisTask = db.query(AnalysisTask).get(task_id)
    orig_history = None

    try:
        if not task:
            raise RuntimeError(f"Task {task_id} not found")
        orig_history = task.history_id

        creds = get_credentials(user_id)
        service = build("gmail", "v1", credentials=creds)

        if start_history_id is None:
            mails = initial_load(service)
        else:
            history_id = start_history_id or task.history_id
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
        total_steps = 4
        step = 1

        self.update_state(
            state="PROGRESS",
            meta={
                "step": "fetch_metadata",
                "progress_pct": int(step / total_steps * 100),
            },
        )
        step += 1

        # 배치 임베딩
        texts = [f"{m['subject']} {m['snippet']}"[:1024] for m in mails]
        vectors: List[List[float]] = get_embedding(texts)

        self.update_state(
            state="PROGRESS",
            meta={"step": "embedding", "progress_pct": int(step / total_steps * 100)},
        )
        step += 1

        # bulk_insert 준비
        CHUNK_SIZE = 500  # 트랜잭션 오버헤드와 메모리 사용량 균형을 위해 조정 가능
        records = []
        for mail, vec in zip(mails, vectors):
            records.append(
                {
                    "user_id": user_id,
                    "gmail_msg_id": mail["id"],
                    "sender": mail["from"],
                    "subject": mail["subject"],
                    "snippet": mail["snippet"],
                    "size_bytes": mail["size"],
                    "is_read": mail["isRead"],
                    "is_starred": mail["isStarred"],
                    "labels": mail["labels"],
                    "received_at": datetime.fromisoformat(mail["timestamp"]),
                    "vector": vec,
                    "processed_at": datetime.now(timezone.utc),
                }
            )
        for i in range(0, len(records), CHUNK_SIZE):
            chunk = records[i : i + CHUNK_SIZE]
            db.bulk_insert_mappings(MailEmbedding, chunk)
            pct = int((step - 1 + (i + len(chunk)) / total) / total_steps * 100)
            self.update_state(
                state="PROGRESS",
                meta={"step": "db_insert", "progress_pct": pct},
            )
        db.commit()
        step += 1

        self.update_state(
            state="PROGRESS",
            meta={"step": "classify", "progress_pct": 100},
        )

        #  Task 완료 처리
        new_history = service.users().getProfile(userId="me").execute().get("historyId")
        task.history_id = new_history
        task.status = "done"
        task.progress_pct = 100
        task.finished_at = datetime.now(timezone.utc)
        db.commit()

    #  Task 실패 처리
    except Exception as e:
        if task:
            task.history_id = orig_history
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
