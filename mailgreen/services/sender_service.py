from typing import List, Optional
from sqlalchemy.orm import Session, Query

from mailgreen.app.models import MailEmbedding
from mailgreen.services.mail_service import filter_mails


def get_top_senders(db: Session, user_id: str, limit: int) -> List[dict]:
    from sqlalchemy import func
    from email.utils import parseaddr

    rows = (
        db.query(
            MailEmbedding.sender.label("sender"),
            func.count(MailEmbedding.id).label("count"),
        )
        .filter(MailEmbedding.user_id == user_id)
        .group_by(MailEmbedding.sender)
        .order_by(func.count(MailEmbedding.id).desc())
        .limit(limit)
        .all()
    )

    result = []
    for r in rows:
        name, _ = parseaddr(r.sender or "")
        sender_name = name if name else "(Unknown)"
        result.append({"sender": r.sender, "name": sender_name, "count": r.count})
    return result


def get_sender_details(
    db: Session,
    user_id: str,
    sender: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    is_read: Optional[bool] = None,
    older_than_months: Optional[int] = None,
    min_size_mb: Optional[float] = None,
) -> List[MailEmbedding]:
    query = db.query(MailEmbedding).filter(MailEmbedding.user_id == user_id)

    if sender:
        query = query.filter(MailEmbedding.sender.ilike(f"%{sender}%"))

    query = filter_mails(
        query,
        start_date=start_date,
        end_date=end_date,
        is_read=is_read,
        older_than_months=older_than_months,
        min_size_mb=min_size_mb,
    )

    return query.order_by(MailEmbedding.received_at.desc()).all()


def get_sender_details_count(
    db: Session,
    user_id: str,
    sender: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    is_read: Optional[bool] = None,
    older_than_months: Optional[int] = None,
    min_size_mb: Optional[float] = None,
) -> List[dict]:
    from sqlalchemy import func
    from email.utils import parseaddr

    query = db.query(
        MailEmbedding.sender.label("sender"),
        func.count(MailEmbedding.id).label("count"),
    ).filter(MailEmbedding.user_id == user_id)

    if sender:
        query = query.filter(MailEmbedding.sender.ilike(f"%{sender}%"))

    query = filter_mails(
        query,
        start_date=start_date,
        end_date=end_date,
        is_read=is_read,
        older_than_months=older_than_months,
        min_size_mb=min_size_mb,
    )

    rows = (
        query.group_by(MailEmbedding.sender)
        .order_by(func.count(MailEmbedding.id).desc())
        .all()
    )

    result = []
    for r in rows:
        name, _ = parseaddr(r.sender or "")
        sender_name = name if name else "(Unknown)"
        result.append({"sender": r.sender, "name": sender_name, "count": r.count})

    return result
