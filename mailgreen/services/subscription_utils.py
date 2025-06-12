import re
import time
from typing import List, Dict, Optional
from googleapiclient.discovery import build, logger
from googleapiclient.errors import HttpError
from mailgreen.services.auth_service import get_credentials

# <a>태그의 href 속성에서 unsubscribe 링크를 추출하기 위한 정규식
UNSUB_LINK_RE = re.compile(r'href=["\']([^"\']*unsubscribe[^"\']*)["\']', re.IGNORECASE)


def extract_subscriptions(
    user_id: str, max_pages: int = 10
) -> List[Dict[str, Optional[str]]]:
    creds = get_credentials(user_id)
    service = build("gmail", "v1", credentials=creds)

    subscriptions: Dict[str, Dict[str, Optional[str]]] = {}
    page_token: Optional[str] = None
    page_count = 0

    try:
        while page_count < max_pages:
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
            msgs = resp.get("messages", [])
            if not msgs:
                break

            for m in msgs:
                msg_id = m.get("id")
                # 1) 헤더에서 List-Unsubscribe 추출
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
                    h["name"].lower(): h["value"]
                    for h in meta.get("payload", {}).get("headers", [])
                }
                from_addr = headers.get("from")
                unsub_header = headers.get("list-unsubscribe")
                unsub_post = headers.get("list-unsubscribe-post", "").lower()

                if not unsub_header or unsub_post != "list-unsubscribe=one-click":
                    continue
                if "mailto:" in unsub_header.lower():
                    continue
                # 링크 분리 및 우선순위 필터링
                all_urls = re.findall(r"https?://[^\s,;<>]+", unsub_header)
                http_urls = [
                    u for u in all_urls if "/unsubscribe/" in u and "/api/" not in u
                ]
                if not http_urls:
                    http_urls = all_urls
                if not from_addr or not http_urls:
                    continue
                sender_key = from_addr.strip().lower()
                if sender_key not in subscriptions:
                    subscriptions[sender_key] = {
                        "sender": from_addr,
                        "unsubscribe_http": http_urls[0] if http_urls else None,
                    }
                else:
                    entry = subscriptions[sender_key]
                    if not entry["unsubscribe_http"] and http_urls:
                        entry["unsubscribe_http"] = http_urls[0]

            page_token = resp.get("nextPageToken")
            if not page_token:
                break
            page_count += 1
            time.sleep(0.2)
    except HttpError as e:
        logger.error(f"구독 추출 중 예외 발생: {e}")

    return list(subscriptions.values())


def parse_unsubscribe_value(raw: str) -> Optional[str]:
    if not raw:
        return None
    parts = re.split(r"[,;]\s*", raw)
    cleaned = []
    for p in parts:
        u = p.strip()
        if u.startswith("<") and u.endswith(">"):
            u = u[1:-1]
        cleaned.append(u)
    for u in cleaned:
        if u.lower().startswith("http"):
            return u
    return cleaned[0] if cleaned else None
