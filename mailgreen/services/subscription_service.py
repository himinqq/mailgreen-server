from email.utils import parseaddr
from typing import List, Dict

from sqlalchemy.orm import Session

from mailgreen.app.models import Subscription, MailEmbedding
from sqlalchemy import func, and_

from mailgreen.services.subscription_utils import (
    extract_subscriptions,
    parse_unsubscribe_value,
)


def unsubscribe_subscription(db: Session, sub_id: str) -> None:
    import requests

    sub = db.query(Subscription).filter_by(id=sub_id).first()
    if not sub:
        raise ValueError("Subscription not found")

    link = sub.unsubscribe_link

    try:
        # API 엔드포인트 기반 링크는 POST 요청
        if "/api/" in link:
            resp = requests.post(link, timeout=10)
        else:
            # 일반 GET 기반 Unsubscribe 링크
            resp = requests.get(link, timeout=10)
        resp.raise_for_status()
    except requests.RequestException as e:
        raise RuntimeError(f"Unsubscribe 요청 실패: {e}")

    sub.is_active = False
    db.add(sub)
    db.commit()


def sync_user_subscriptions(db, user_id: str) -> list[dict[str, str | None]]:
    subs_meta = extract_subscriptions(user_id)
    existing_senders = {
        sub.sender for sub in db.query(Subscription).filter_by(user_id=user_id).all()
    }

    new_subs = []
    for meta in subs_meta:
        sender = meta["sender"]
        link = parse_unsubscribe_value(meta["unsubscribe_http"])
        if not sender or not link:
            continue
        if sender in existing_senders:
            sub = (
                db.query(Subscription).filter_by(user_id=user_id, sender=sender).first()
            )
            sub.unsubscribe_link = link
        else:
            sub = Subscription(
                user_id=user_id, sender=sender, unsubscribe_link=link, is_active=True
            )
            db.add(sub)
            new_subs.append(sub)

    db.commit()
    return new_subs


def get_user_subscriptions(db: Session, user_id: str) -> List[dict]:
    rows = (
        db.query(
            Subscription.id.label("sub_id"),
            Subscription.sender.label("sender"),
            func.count(MailEmbedding.id).label("count"),
        )
        .join(
            MailEmbedding,
            and_(
                MailEmbedding.user_id == Subscription.user_id,
                MailEmbedding.sender == Subscription.sender,
            ),
        )
        .filter(
            Subscription.user_id == str(user_id),
            Subscription.is_active == True,
            MailEmbedding.is_deleted == False,
        )
        .group_by(Subscription.id, Subscription.sender)
        .order_by(func.count(MailEmbedding.id).desc())
        .all()
    )

    result: List[Dict[str, any]] = []
    for r in rows:
        name, _ = parseaddr(r.sender or "")
        sender_name = name if name else "(Unknown)"
        result.append(
            {
                "sub_id": r.sub_id,
                "sender": r.sender,
                "name": sender_name,
                "count": r.count,
            }
        )
    return result
