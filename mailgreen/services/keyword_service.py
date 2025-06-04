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


def get_keyword_details_count(
    db: Session,
    user_id: str,
    topic_id: int | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    is_read: bool | None = None,
    older_than_months: int | None = None,
    min_size_mb: float | None = None,
) -> List[dict]:
    from sqlalchemy.orm import aliased
    from email.utils import parseaddr
    # 기본 쿼리 구성
    base_query = db.query(MailEmbedding).filter(
        MailEmbedding.user_id == user_id,
        MailEmbedding.is_deleted == False,
        MailEmbedding.category.isnot(None),
    )

    if topic_id is not None:
        base_query = base_query.filter(MailEmbedding.category == topic_id)

    base_query = filter_mails(
        base_query,
        start_date=start_date,
        end_date=end_date,
        is_read=is_read,
        older_than_months=older_than_months,
        min_size_mb=min_size_mb,
    )

    # 카테고리 + sender 별 count
    sender_counts = (
        base_query.with_entities(
            MailEmbedding.category.label("category"),
            MailEmbedding.sender.label("sender"),
            func.count(MailEmbedding.id).label("sender_count")
        )
        .group_by(MailEmbedding.category, MailEmbedding.sender)
        .subquery()
    )

    # top sender 추출 (self left outer join with no greater count)
    s1 = aliased(sender_counts)
    s2 = aliased(sender_counts)

    top_senders = (
        db.query(s1.c.category, s1.c.sender)
        .outerjoin(
            s2,
            (s1.c.category == s2.c.category) &
            (s1.c.sender_count < s2.c.sender_count)
        )
        .filter(s2.c.category == None)
        .subquery()
    )

    # 카테고리별 전체 개수
    result_rows = (
        base_query
        .join(MajorTopic, MailEmbedding.category == MajorTopic.id)
        .with_entities(
            MajorTopic.id.label("category"),
            MajorTopic.description.label("description"),
            func.count(MailEmbedding.id).label("count")
        )
        .group_by(MajorTopic.id, MajorTopic.description)
        .subquery()
    )

    # 최종 조인
    final = (
        db.query(
            result_rows.c.category,
            result_rows.c.description,
            result_rows.c.count,
            top_senders.c.sender.label("top_sender")
        )
        .outerjoin(top_senders, result_rows.c.category == top_senders.c.category)
        .order_by(result_rows.c.count.desc())
        .all()
    )

    result = []
    for row in final:
        name, email = parseaddr(row.top_sender or "")
        result.append({
            "topic_id": row.category,
            "description": row.description,
            "count": row.count,
            "top_sender_name": name if name else None,
            "top_sender_addr": email if email else None,
        })
    return result