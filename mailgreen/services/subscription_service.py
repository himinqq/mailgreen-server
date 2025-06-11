from email.utils import parseaddr
from typing import List, Dict, Optional

from sqlalchemy.orm import Session

from mailgreen.app.models import Subscription, MailEmbedding
from sqlalchemy import func, and_
import re


def sync_subscriptions(db: Session, user_id: str, fetched: list[dict]):
    existing = {
        sub.sender: sub
        for sub in db.query(Subscription).filter_by(user_id=user_id).all()
    }

    new_senders = set()

    for item in fetched:
        sender = item["sender"]
        new_senders.add(sender)

        if sender in existing:
            sub = existing[sender]
            sub.unsubscribe_link = item["unsubscribe_link"]
        else:
            sub = Subscription(
                user_id=user_id,
                sender=sender,
                unsubscribe_link=item["unsubscribe_link"],
                is_active=True,
            )
            db.add(sub)
    try:
        db.commit()
        return {
            "success": True,
        }
    except Exception as e:
        db.rollback()
        return {
            "success": False,
            "error": str(e),
        }


def unsubscribe_subscription(db: Session, sub_id: str) -> None:
    from urllib.parse import urljoin, urlparse
    from bs4 import BeautifulSoup
    import requests

    sub = db.query(Subscription).filter_by(id=sub_id).first()
    if not sub:
        raise ValueError("Subscription not found")

    link = sub.unsubscribe_link
    host = urlparse(link).netloc
    path = urlparse(link).path

    if link.lower().startswith("mailto:"):
        from mailgreen.services.mail_service import send_mail_via_gmail_api

        m = re.match(r"mailto:([^?]+)\?subject=(.*)", link, re.IGNORECASE)
        if not m:
            raise ValueError("Invalid mailto format")
        to_addr, subject = m.groups()
        send_mail_via_gmail_api(
            user_id=str(sub.user_id), to=to_addr, subject=subject, body=""
        )
        return

    if "page.stibee.com" in host and "/unsubscribe/" in path:
        resp = requests.get(link, timeout=10)
        resp.raise_for_status()
    else:
        resp = requests.get(link, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.content, "html.parser")

        form = soup.find(
            "form", attrs={"action": re.compile("unsubscribe", re.IGNORECASE)}
        )
        if form:
            action = form["action"]
            if not action.startswith("http"):
                action = urljoin(link, action)
            data = {
                inp["name"]: inp.get("value", "")
                for inp in form.find_all("input")
                if inp.get("name")
            }
            requests.post(action, data=data, timeout=10)
        else:
            a = soup.find("a", href=re.compile("unsubscribe", re.IGNORECASE))
            if not a:
                with open("unsubscribe_debug.html", "wb") as f:
                    f.write(resp.content)
                raise RuntimeError(
                    "Unsubscribe 폼/링크를 찾을 수 없습니다. unsubscribe_debug.html을 확인하세요."
                )
            href = a["href"]
            if not href.startswith("http"):
                href = urljoin(link, href)
            requests.get(href, timeout=10)
    sub.is_active = False
    db.add(sub)
    db.commit()


def get_subscriptions(db: Session, user_id: str, limit: int) -> List[dict]:
    rows = (
        db.query(
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
        .group_by(Subscription.sender)
        .order_by(func.count(MailEmbedding.id).desc())
        .limit(limit)
        .all()
    )

    result: List[Dict[str, any]] = []
    for r in rows:
        name, _ = parseaddr(r.sender or "")
        sender_name = name if name else "(Unknown)"
        result.append({"sender": r.sender, "name": sender_name, "count": r.count})
    return result
