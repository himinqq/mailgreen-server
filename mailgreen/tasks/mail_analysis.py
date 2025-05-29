from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())

from celery import Celery
from sqlalchemy.orm import Session
from mailgreen.app.database import SessionLocal
from mailgreen.app.models import MailEmbedding, AnalysisTask
from mailgreen.services.mail_service import fetch_messages
from mailgreen.services.embed_service import get_embedding
from datetime import datetime, timezone
from typing import Optional


# Celery 애플리케이션 인스턴스
celery_app = Celery("mail_analysis", broker="redis://localhost:6379/0")


@celery_app.task(bind=True)
def run_analysis(self, user_id: str, task_id: str, limit: Optional[int] = None):
    db: Session = SessionLocal()
    task = None
    try:
        task = db.query(AnalysisTask).get(task_id)
        if not task:
            raise RuntimeError(f"Task {task_id} not found")

        mails = fetch_messages(user_id, max_results=limit or 100)
        total = len(mails) or 1

        for idx, mail in enumerate(mails, start=1):
            vector = get_embedding(
                mail.get("subject", "") + " " + mail.get("snippet", "")
            )
            emb = MailEmbedding(
                user_id=user_id,
                gmail_msg_id=mail["id"],
                sender=mail.get("from"),
                subject=mail.get("subject"),
                snippet=mail.get("snippet"),
                labels=mail.get("labels"),
                size_bytes=mail.get("size"),
                is_read=mail.get("isRead"),
                is_starred=mail.get("isStarred", False),
                received_at=datetime.fromisoformat(mail.get("timestamp")),
                vector=vector,
                processed_at=datetime.now(timezone.utc),
            )
            db.add(emb)

            # 진행률 업데이트
            pct = int(idx / total * 100)

            if pct % 5 == 0:
                task.progress_pct = pct
                try:
                    db.commit()
                except Exception:
                    db.rollback()
                    raise

        # 완료 처리
        task.status = "done"
        task.progress_pct = 100
        task.finished_at = datetime.now(timezone.utc)

        try:
            db.commit()
        except Exception:
            db.rollback()
            raise

    except Exception as e:
        # 실패 시 상태 기록
        if task:
            task.status = "failed"
            task.error_msg = str(e)
            try:
                db.commit()
            except:
                db.rollback()
        raise

    finally:
        db.close()
