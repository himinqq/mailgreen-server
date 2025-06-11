import re
import time
import base64
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
                            metadataHeaders=["List-Unsubscribe", "From", "Subject"],
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

                # API 엔드포인트 링크 무시
                if unsub_header and "/api/" in unsub_header:
                    unsub_header = None

                # 2) 본문에서 추출 (헤더 실패 시)
                if not unsub_header and from_addr:
                    try:
                        full = (
                            service.users()
                            .messages()
                            .get(userId="me", id=msg_id, format="full")
                            .execute()
                        )
                        parts = full.get("payload", {}).get("parts", [])
                        html_data = None
                        if full["payload"].get("mimeType") == "text/html":
                            html_data = full["payload"]["body"].get("data")
                        else:
                            for part in parts:
                                if part.get("mimeType") == "text/html":
                                    html_data = part["body"].get("data")
                                    break
                        if html_data:
                            html = base64.urlsafe_b64decode(html_data).decode(
                                "utf-8", errors="ignore"
                            )
                            m2 = UNSUB_LINK_RE.search(html)
                            if m2:
                                unsub_header = m2.group(1)
                    except Exception as e:
                        logger.debug(f"[{msg_id}] 본문 파싱 실패: {e}")

                # 필수 정보 확인
                if not from_addr or not unsub_header:
                    continue

                # 링크 분리 및 우선순위 필터링
                all_urls = re.findall(r"https?://[^\s,;<>]+", unsub_header)
                # '/unsubscribe/' 포함, '/api/' 제외 우선
                http_urls = [
                    u for u in all_urls if "/unsubscribe/" in u and "/api/" not in u
                ]
                if not http_urls:
                    http_urls = all_urls
                mailtos = re.findall(r"mailto:[^\s,;<>]+", unsub_header)

                sender_key = from_addr.strip().lower()
                if sender_key not in subscriptions:
                    subscriptions[sender_key] = {
                        "sender": from_addr,
                        "unsubscribe_http": http_urls[0] if http_urls else None,
                        "unsubscribe_mailto": mailtos[0] if mailtos else None,
                    }
                else:
                    entry = subscriptions[sender_key]
                    if not entry["unsubscribe_http"] and http_urls:
                        entry["unsubscribe_http"] = http_urls[0]
                    if not entry["unsubscribe_mailto"] and mailtos:
                        entry["unsubscribe_mailto"] = mailtos[0]

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
        if u.lower().startswith("mailto:"):
            return u
    for u in cleaned:
        if u.lower().startswith("http"):
            return u
    return cleaned[0] if cleaned else None
