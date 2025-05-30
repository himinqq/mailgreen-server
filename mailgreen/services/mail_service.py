import os
import logging
from datetime import datetime, timezone
from typing import List, Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from sqlalchemy.orm import Session

from mailgreen.app.database import SessionLocal
from mailgreen.app.models import UserCredentials

logger = logging.getLogger(__name__)


def get_credentials(user_id: str) -> Credentials:
    db: Session = SessionLocal()
    try:
        cred = (
            db.query(UserCredentials).filter(UserCredentials.user_id == user_id).first()
        )
        if not cred:
            raise RuntimeError(f"No credentials for user {user_id}")

        creds = Credentials(
            token=cred.access_token,
            refresh_token=cred.refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=os.getenv("GOOGLE_CLIENT_ID"),
            client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
            scopes=cred.scopes,  # 기존 스코프도 로드
            expiry=cred.expiry,
        )
        # 만료되었으면 리프레시
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            # DB에 갱신된 토큰/만료시간 저장
            cred.access_token = creds.token
            cred.expiry = creds.expiry.replace(tzinfo=timezone.utc)
            cred.scopes = creds.scopes  # ← 새 스코프 반영
            db.commit()
        return creds
    finally:
        db.close()


def list_all_message_ids(service) -> List[str]:
    ids: List[str] = []
    page_token: Optional[str] = None
    while True:
        resp = (
            service.users()
            .messages()
            .list(
                userId="me",
                maxResults=500,
                pageToken=page_token,
                fields="nextPageToken,messages(id)",
            )
            .execute()
        )
        ids.extend(m["id"] for m in resp.get("messages", []))
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
    return ids


def batch_fetch_metadata(
    service, msg_ids: list[str], batch_size: int = 100
) -> list[dict]:
    mails: list[dict] = []

    def _collect(request_id, resp, err):
        if err:
            logger.warning(f"Batch fetch error for {request_id}: {err}")
            return
        mails.append(
            {
                "id": resp["id"],
                "snippet": resp.get("snippet", ""),
                "subject": next(
                    h["value"]
                    for h in resp["payload"]["headers"]
                    if h["name"] == "Subject"
                ),
                "from": next(
                    h["value"]
                    for h in resp["payload"]["headers"]
                    if h["name"] == "From"
                ),
                "timestamp": datetime.fromtimestamp(
                    int(resp["internalDate"]) / 1000, timezone.utc
                ).isoformat(),
                "size": resp.get("sizeEstimate", 0),
                "isRead": "UNREAD" not in resp.get("labelIds", []),
            }
        )

    batch = service.new_batch_http_request(callback=_collect)
    for i, mid in enumerate(msg_ids, start=1):
        req = (
            service.users()
            .messages()
            .get(
                userId="me",
                id=mid,
                format="metadata",
                metadataHeaders=["Subject", "From", "Date"],
            )
        )
        batch.add(req, request_id=mid)
        if i % batch_size == 0:
            batch.execute()
            batch = service.new_batch_http_request(callback=_collect)

    batch.execute()

    if len(mails) < len(msg_ids):
        logger.warning(f"Fetched {len(mails)} metadata but expected {len(msg_ids)}")

    return mails


def initial_load(service) -> list[dict]:
    ids = list_all_message_ids(service)
    return batch_fetch_metadata(service, ids)
