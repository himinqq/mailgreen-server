import re
import time
from typing import List, Dict, Optional
from googleapiclient.discovery import build, logger
from googleapiclient.errors import HttpError
from mailgreen.services.auth_service import get_credentials

STIBEE_RE = re.compile(
    r"https?://page\.stibee\.com/api/v1\.0/lists/unsubscribe/[^\s,;<>]+"
)


def extract_subscriptions(
    user_id: str, max_pages: int = 10
) -> List[Dict[str, Optional[str]]]:
    creds = get_credentials(user_id)
    service = build("gmail", "v1", credentials=creds)

    subscriptions: Dict[str, Dict[str, Optional[str]]] = {}
    page_token: Optional[str] = None
    for _ in range(max_pages):
        try:
            resp = (
                service.users()
                .messages()
                .list(
                    userId="me",
                    labelIds=["INBOX"],
                    maxResults=200,
                    pageToken=page_token,
                )
                .execute()
            )
        except HttpError as e:
            logger.error(f"Gmail list 실패: {e}")
            break

        msgs = resp.get("messages", [])
        if not msgs:
            break

        for m in msgs:
            msg_id = m["id"]
            try:
                meta = (
                    service.users()
                    .messages()
                    .get(
                        userId="me",
                        id=msg_id,
                        format="metadata",
                        metadataHeaders=[
                            "List-Unsubscribe",
                            "List-Unsubscribe-Post",
                            "From",
                        ],
                    )
                    .execute()
                )
            except HttpError as e:
                logger.warning(f"[{msg_id}] metadata fetch 실패: {e}")
                continue

            headers = {
                h["name"].lower(): h["value"] for h in meta["payload"]["headers"]
            }
            unsub_post = headers.get("list-unsubscribe-post", "").lower()
            if unsub_post != "list-unsubscribe=one-click":
                continue

            raw = headers.get("list-unsubscribe", "")
            match = STIBEE_RE.search(raw)
            if not match:
                continue

            from_addr = headers.get("from")
            if not from_addr:
                continue

            link = match.group(0)
            key = from_addr.strip().lower()
            if key not in subscriptions:
                subscriptions[key] = {
                    "sender": from_addr,
                    "unsubscribe_http": link,
                }

        page_token = resp.get("nextPageToken")
        if not page_token:
            break
        time.sleep(0.2)

    return list(subscriptions.values())


def parse_unsubscribe_value(raw: str) -> Optional[str]:
    if not raw:
        return None
    raw = raw.strip()
    if raw.startswith("<") and raw.endswith(">"):
        return raw[1:-1]
    return raw
