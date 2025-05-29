import os
from datetime import datetime, timezone
from typing import List, Dict

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from sqlalchemy.orm import Session

from mailgreen.app.database import SessionLocal
from mailgreen.app.models import UserCredentials

GMAIL_LIST_URL = "https://gmail.googleapis.com/gmail/v1/users/me/messages"
GMAIL_MSG_URL = "https://gmail.googleapis.com/gmail/v1/users/me/messages/{msg_id}"


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


def fetch_messages(user_id: str, max_results: int = 10) -> List[Dict]:
    creds = get_credentials(user_id)
    service = build("gmail", "v1", credentials=creds)

    resp = (
        service.users().messages().list(userId="me", maxResults=max_results).execute()
    )
    msgs = resp.get("messages", [])
    output = []

    for m in msgs:
        msg_id = m["id"]

        meta = (
            service.users()
            .messages()
            .get(
                userId="me",
                id=msg_id,
                format="metadata",
                metadataHeaders=["Subject", "From", "Date"],
            )
            .execute()
        )

        snippet = meta.get("snippet", "")
        hdrs = {
            h["name"]: h["value"] for h in meta.get("payload", {}).get("headers", [])
        }
        subject = hdrs.get("Subject", "(No Subject)")
        sender = hdrs.get("From", "(No Sender)")
        size = meta.get("sizeEstimate", 0)

        internal_ms = int(meta.get("internalDate", 0))
        timestamp = datetime.fromtimestamp(internal_ms / 1000, timezone.utc).isoformat()

        labels = meta.get("labelIds", [])
        is_read = "UNREAD" not in labels

        output.append(
            {
                "id": msg_id,
                "snippet": snippet,
                "subject": subject,
                "from": sender,
                "timestamp": timestamp,
                "size": size,
                "isRead": is_read,
            }
        )

    return output
