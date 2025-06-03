from typing import List
from sqlalchemy.orm import Session
from sqlalchemy import func
from fastapi import HTTPException

from mailgreen.app.models import MailEmbedding, MajorTopic
from mailgreen.services.mail_service import filter_mails


def get_top_keywords(db: Session, user_id: str, limit: int) -> List[dict]:
    rows = (
        db.query(
            MajorTopic.id.label("category"),
            MajorTopic.description.label("description"),
            func.count(MailEmbedding.id).label("count"),
        )
        .join(MailEmbedding, MailEmbedding.category == MajorTopic.id)
        .filter(
            MailEmbedding.user_id == user_id,
            MailEmbedding.is_deleted == False,
            MailEmbedding.category.isnot(None),
        )
        .group_by(MajorTopic.id, MajorTopic.description)
        .order_by(func.count(MailEmbedding.id).desc())
        .limit(limit)
        .all()
    )
    return [
        {"topic_id": r.category, "description": r.description, "count": r.count}
        for r in rows
    ]


def get_keyword_details(
    db: Session,
    user_id: str,
    topic_id: int,
    start_date: str | None = None,
    end_date: str | None = None,
    is_read: bool | None = None,
    older_than_months: int | None = None,
    min_size_mb: float | None = None,
) -> List[MailEmbedding]:

    exists = db.query(MajorTopic.id).filter(MajorTopic.id == topic_id).first()
    if not exists:
        raise HTTPException(status_code=404, detail="존재하지 않는 topic_id입니다.")

    query = db.query(MailEmbedding).filter(
        MailEmbedding.user_id == user_id,
        MailEmbedding.is_deleted == False,
        MailEmbedding.category == topic_id,
    )

    query = filter_mails(
        query,
        start_date=start_date,
        end_date=end_date,
        is_read=is_read,
        older_than_months=older_than_months,
        min_size_mb=min_size_mb,
    )

    return query.order_by(MailEmbedding.received_at.desc()).all()
