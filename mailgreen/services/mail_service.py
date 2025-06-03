import os
import logging
from datetime import datetime, timezone
from typing import List, Optional
import time
import random

from googleapiclient.errors import HttpError
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
            expiry=cred.expiry,
        )
        # 만료되었으면 리프레시
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            # DB에 갱신된 토큰/만료시간 저장
            cred.access_token = creds.token
            cred.expiry = creds.expiry.replace(tzinfo=timezone.utc)
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


def _parse_message(resp: dict) -> dict:
    headers = resp.get("payload", {}).get("headers", [])
    header_map = {h["name"]: h["value"] for h in headers}

    label_ids = resp.get("labelIds", [])
    return {
        "id": resp["id"],
        "snippet": resp.get("snippet", ""),
        "subject": header_map.get("Subject", ""),
        "from": header_map.get("From", ""),
        "timestamp": datetime.fromtimestamp(
            int(resp["internalDate"]) / 1000, timezone.utc
        ).isoformat(),
        "size": resp.get("sizeEstimate", 0),
        "labels": label_ids,
        "isRead": "UNREAD" not in label_ids,
        "isStarred": "STARRED" in label_ids,
    }


def _execute_with_backoff(fn, max_retries: int = 5):

    # 429 혹은 rateLimitExceeded가 대기 후 재시도
    for attempt in range(max_retries):
        try:
            return fn()
        except HttpError as e:
            status = getattr(e.resp, "status", None)
            if status == 429 or "rateLimitExceeded" in str(e):
                sleep_sec = (2**attempt) + random.uniform(0, 1)
                logger.warning(
                    f"rateLimitExceeded (status={status}), retry {attempt + 1}/{max_retries} "
                    f"after {sleep_sec:.2f}s"
                )
                time.sleep(sleep_sec)
            else:
                raise
    raise RuntimeError(f"Max retries ({max_retries}) reached")


def batch_fetch_metadata(
    service, msg_ids: list[str], batch_size: int = 50, max_retries: int = 5
) -> list[dict]:
    mails: list[dict] = []

    def _collect(request_id, resp, err):
        if err:
            logger.warning(f"Batch fetch error for {request_id}: {err}")
            return
        mails.append(_parse_message(resp))

    def _run_batch(batch_req):
        _execute_with_backoff(batch_req.execute, max_retries)

    batch = service.new_batch_http_request(callback=_collect)

    for idx, mid in enumerate(msg_ids, start=1):
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

        if idx % batch_size == 0:
            _run_batch(batch)
            batch = service.new_batch_http_request(callback=_collect)

    remainder = len(msg_ids) % batch_size
    if remainder:
        _run_batch(batch)

    fetched_ids = {m["id"] for m in mails}
    missing = [mid for mid in msg_ids if mid not in fetched_ids]
    if missing:
        logger.warning(
            f"Fetched {len(fetched_ids)} items, expected {len(msg_ids)}. "
            f"Retrying {len(missing)} missing IDs individually."
        )
        for mid in missing:

            def _get_single():
                return (
                    service.users()
                    .messages()
                    .get(
                        userId="me",
                        id=mid,
                        format="metadata",
                        metadataHeaders=["Subject", "From", "Date"],
                    )
                    .execute()
                )

            try:
                resp = _execute_with_backoff(_get_single, max_retries)
                mails.append(_parse_message(resp))
            except HttpError as e:
                logger.error(f"ID={mid} fetch failed even after retries: {e}")

    return mails


def initial_load(service) -> list[dict]:
    ids = list_all_message_ids(service)
    return batch_fetch_metadata(service, ids)
