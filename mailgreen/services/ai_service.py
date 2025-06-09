import os
import httpx
from datetime import datetime
import time
import json

from mailgreen.app.config import Config as AppConfig

from mailgreen.function_specs import FUNCTION_SPECS
from mailgreen.services.mail_service import mark_important, read_mail, delete_mail, search_mail, unsubscribe_mail
from mailgreen.services.auth_service import get_credentials
import logging

CLAUDE_API_KEY = AppConfig.CLAUDE_API_KEY
CLAUDE_API_URL = AppConfig.CLAUDE_API_URL

SYSTEM_PROMPT = (
    "너는 이메일 비서야. 사용자가 삭제/별표/읽음/구독해제 등 파괴적 명령을 내리면, "
    "반드시 먼저 preview function(대상 메일 목록만 반환)을 실행하고, "
    "사용자가 '네, 삭제해줘' 등 확정 의사를 명확히 밝히면 그때만 실제 function을 실행해야 해. "
    "preview 없이 바로 파괴적 function을 실행하면 안 된다. "
    "또한 사용자가 '저걸', '그거', '방금', '위에 것', '이것', '이 메일', '저 메일' 등 지시어를 쓰면, "
    "백엔드가 자동으로 직전 검색/미리보기 메일 id 리스트를 arguments.ids에 넣어주니, 반드시 function-call을 실행해야 해. "
    "텍스트로 되묻지 말고, function-call을 바로 실행해."
)

# 사용자별 마지막 미리보기/검색 메일 id 리스트를 메모리에 저장
USER_LAST_MAIL_IDS = {}

import re

def contains_reference_word(prompt: str) -> bool:
    # '저걸', '그 메일', '방금', '위에 것' 등 지시어가 포함되어 있는지 단순 체크
    keywords = ["저걸", "그 메일", "방금", "위에 것", "이것", "이 메일", "저 메일"]
    return any(k in prompt for k in keywords)

async def call_claude_with_functions(prompt: str):
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            CLAUDE_API_URL,
            headers={
                "x-api-key": CLAUDE_API_KEY,
                "content-type": "application/json",
                "anthropic-version": "2023-06-01"
            },
            json={
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 512,
                "system": SYSTEM_PROMPT,
                "messages": [
                    {"role": "user", "content": prompt}
                ],
                "tools": FUNCTION_SPECS
            }
        )
        return response.json()

def extract_tool_use(ai_response):
    content = ai_response.get("content", [])
    for item in content:
        if item.get("type") == "tool_use":
            return {
                "name": item.get("name"),
                "arguments": item.get("input", {})
            }
    return None

async def process_ai_request(user_id: str, prompt: str, db):
    start_time = time.time()
    logging.info(f"[AI] 요청 수신: user_id={user_id}, prompt={prompt}")
    t0 = time.time()
    logging.info(f"[AI] Claude 요청: {prompt}")
    ai_response = await call_claude_with_functions(prompt)
    t1 = time.time()
    logging.info(f"[AI] Claude 응답 (소요: {t1-t0:.2f}s): {json.dumps(ai_response, ensure_ascii=False)[:1000]}")
    # Claude function call 파싱 (content 리스트에서 tool_use 추출)
    tool_use = extract_tool_use(ai_response)
    t2 = time.time()
    logging.info(f"[AI] function-call 파싱 (소요: {t2-t1:.2f}s): {tool_use}")

    # --- context mapping: 지시어가 오면 마지막 메일 id 리스트를 arguments에 자동 포함 ---
    arguments = None
    function_name = None
    if tool_use:
        function_name = tool_use["name"]
        arguments = tool_use["arguments"]
    else:
        arguments = {}

    if contains_reference_word(prompt):
        last_ids = USER_LAST_MAIL_IDS.get(user_id)
        if last_ids:
            arguments["ids"] = last_ids
            logging.info(f"[AI] 지시어 감지: arguments에 ids 자동 포함 → {last_ids}")

    # function-call이 없고, 지시어+ids가 있으면 백엔드에서 강제 실행
    if not tool_use and arguments.get("ids"):
        # Claude가 function-call을 생성하지 않았지만, ids가 있으면 mark_important/read_mail/delete_mail 등 추정
        # 프롬프트에서 의도를 간단히 추론 (간단한 if-elif)
        if "별표" in prompt or "중요" in prompt:
            function_name = "mark_important"
        elif "읽음" in prompt or "읽어" in prompt:
            function_name = "read_mail"
        elif "삭제" in prompt or "지워" in prompt:
            function_name = "delete_mail"
        elif "구독해제" in prompt or "수신거부" in prompt:
            function_name = "unsubscribe_mail"
        else:
            # 명확하지 않으면 에러 반환
            logging.error(f"[AI] 지시어+ids는 있으나 function_name 추정 불가: prompt={prompt}")
            return {
                "error": "지시어로부터 실행할 function을 추정할 수 없습니다.",
                "ai_response": ai_response,
                "prompt": prompt,
                "user_id": user_id
            }
        logging.info(f"[AI] function-call 미생성 → 백엔드에서 강제 실행: {function_name}, arguments: {arguments}")

    if not function_name:
        logging.error(f"[AI function-call 실패] user_id={user_id}, prompt={prompt}, ai_response={ai_response}")
        return {
            "error": "AI가 적절한 function을 선택하지 못했습니다.",
            "ai_response": ai_response,
            "prompt": prompt,
            "user_id": user_id
        }

    creds = get_credentials(user_id)
    t3 = time.time()
    logging.info(f"[AI] credentials 조회 및 파라미터 준비 완료 (소요: {t3-t2:.2f}s)")

    gmail_api_start = time.time()
    if function_name == "mark_important":
        logging.info(f"[AI] mark_important 실행 시작")
        result = mark_important(db, user_id, arguments)
    elif function_name == "read_mail":
        logging.info(f"[AI] read_mail 실행 시작")
        result = read_mail(db, user_id, arguments)
    elif function_name == "delete_mail":
        logging.info(f"[AI] delete_mail 실행 시작")
        result = delete_mail(db, user_id, arguments)
    elif function_name == "search_mail":
        logging.info(f"[AI] search_mail 실행 시작")
        result = search_mail(db, user_id, arguments)
        # 검색 결과 id 리스트 저장
        USER_LAST_MAIL_IDS[user_id] = [m["id"] for m in result]
        logging.info(f"[AI] USER_LAST_MAIL_IDS 저장: {USER_LAST_MAIL_IDS[user_id]}")
    elif function_name == "unsubscribe_mail":
        logging.info(f"[AI] unsubscribe_mail 실행 시작")
        result = unsubscribe_mail(db, user_id, arguments)
    elif function_name == "preview_action":
        logging.info(f"[AI] preview_action 실행 시작")
        result = preview_action(db, user_id, arguments.get("action"), arguments)
        if result and "candidates" in result:
            USER_LAST_MAIL_IDS[user_id] = [m["id"] for m in result["candidates"]]
            logging.info(f"[AI] USER_LAST_MAIL_IDS 저장: {USER_LAST_MAIL_IDS[user_id]}")
    else:
        result = {"error": "지원하지 않는 function"}
    gmail_api_end = time.time()
    logging.info(f"[AI] {function_name} 실행 완료 (Gmail API 소요: {gmail_api_end-gmail_api_start:.2f}s), 결과: {str(result)[:1000]}")
    t4 = time.time()
    total = t4 - start_time
    logging.info(f"[AI] process_ai_request 전체 완료 (총 소요: {total:.2f}s), 최종 반환: {str(result)[:1000]}")
    return {"result": result, "ai_response": ai_response}

def preview_action(db, user_id, action, filter_):
    # action: 'delete', 'mark_important', 'read', 'unsubscribe'
    # filter_: sender, subject, start_date, end_date, has_pdf 등
    if action == "delete":
        mails = _filter_mail_embeddings(db, user_id, filter_)
    elif action == "mark_important":
        mails = _filter_mail_embeddings(db, user_id, filter_)
    elif action == "read":
        mails = _filter_mail_embeddings(db, user_id, filter_)
    elif action == "unsubscribe":
        mails = _filter_mail_embeddings(db, user_id, filter_)
    elif action == "search":
        # 조회는 바로 실행
        return search_mail(db, user_id, filter_)
    else:
        return {"error": "지원하지 않는 action"}
    # 공통: 미리보기는 실제 액션 없이 대상 메일 목록만 반환
    candidates = [{
        "id": m.gmail_msg_id,
        "subject": m.subject if m.subject is not None else None,
        "sender": m.sender if m.sender is not None else None,
        "snippet": getattr(m, "snippet", None),
        "received_at": m.received_at.isoformat() if m.received_at else None,
        "is_read": m.is_read if m.is_read is not None else None,
        "is_starred": m.is_starred if m.is_starred is not None else None
    } for m in mails]
    return {"action": action, "candidates": candidates, "count": len(candidates)}

def confirm_action(db, user_id, action, message_ids):
    # message_ids: 실제로 액션을 적용할 메일 ID 목록
    # action: 'delete', 'mark_important', 'read', 'unsubscribe'
    filter_ = {"ids": message_ids}
    if action == "delete":
        return delete_mail_by_ids(db, user_id, message_ids)
    elif action == "mark_important":
        return mark_important_by_ids(db, user_id, message_ids)
    elif action == "read":
        return read_mail_by_ids(db, user_id, message_ids)
    elif action == "unsubscribe":
        return unsubscribe_mail_by_ids(db, user_id, message_ids)
    else:
        return {"error": "지원하지 않는 action"}

# 아래는 각 액션별로 message_ids 기반으로 실제 실행하는 함수들

def delete_mail_by_ids(db, user_id, message_ids):
    creds = get_credentials(user_id)
    service = build("gmail", "v1", credentials=creds)
    user_id_gmail = "me"
    deleted = []
    for mid in message_ids:
        mail = db.query(MailEmbedding).filter(MailEmbedding.user_id == user_id, MailEmbedding.gmail_msg_id == mid).first()
        if not mail:
            continue
        try:
            service.users().messages().trash(userId=user_id_gmail, id=mid).execute()
            mail.is_deleted = True
            mail.deleted_at = datetime.utcnow()
            deleted.append(mid)
        except Exception as e:
            continue
    db.commit()
    return {"deleted": deleted, "count": len(deleted)}

def mark_important_by_ids(db, user_id, message_ids):
    creds = get_credentials(user_id)
    service = build("gmail", "v1", credentials=creds)
    user_id_gmail = "me"
    starred = []
    starred_mails = []
    for mid in message_ids:
        mail = db.query(MailEmbedding).filter(MailEmbedding.user_id == user_id, MailEmbedding.gmail_msg_id == mid).first()
        if not mail:
            continue
        try:
            service.users().messages().modify(
                userId=user_id_gmail,
                id=mid,
                body={"addLabelIds": ["STARRED"]}
            ).execute()
            mail.is_starred = True
            starred.append(mid)
            starred_mails.append({
                "id": mail.gmail_msg_id,
                "subject": mail.subject if mail.subject is not None else None,
                "sender": mail.sender if mail.sender is not None else None,
                "snippet": getattr(mail, "snippet", None),
                "received_at": mail.received_at.isoformat() if mail.received_at else None,
                "is_read": mail.is_read if mail.is_read is not None else None,
                "is_starred": mail.is_starred if mail.is_starred is not None else None
            })
        except Exception as e:
            continue
    db.commit()
    return {"starred": starred, "count": len(starred), "starred_mails": starred_mails}

def read_mail_by_ids(db, user_id, message_ids):
    creds = get_credentials(user_id)
    service = build("gmail", "v1", credentials=creds)
    user_id_gmail = "me"
    read = []
    for mid in message_ids:
        mail = db.query(MailEmbedding).filter(MailEmbedding.user_id == user_id, MailEmbedding.gmail_msg_id == mid).first()
        if not mail:
            continue
        try:
            service.users().messages().modify(
                userId=user_id_gmail,
                id=mid,
                body={"removeLabelIds": ["UNREAD"]}
            ).execute()
            mail.is_read = True
            read.append(mid)
        except Exception as e:
            continue
    db.commit()
    return {"read": read, "count": len(read)}

def unsubscribe_mail_by_ids(db, user_id, message_ids):
    creds = get_credentials(user_id)
    service = build("gmail", "v1", credentials=creds)
    user_id_gmail = "me"
    unsubscribed = []
    failed = []
    for mid in message_ids:
        mail = db.query(MailEmbedding).filter(MailEmbedding.user_id == user_id, MailEmbedding.gmail_msg_id == mid).first()
        if not mail:
            continue
        try:
            msg = service.users().messages().get(userId=user_id_gmail, id=mid, format="metadata", metadataHeaders=["List-Unsubscribe"]).execute()
            headers = msg.get("payload", {}).get("headers", [])
            unsub_header = None
            for h in headers:
                if h["name"].lower() == "list-unsubscribe":
                    unsub_header = h["value"]
                    break
            if unsub_header:
                import re, requests
                urls = re.findall(r'<(.*?)>', unsub_header)
                for url in urls:
                    if url.startswith("mailto:"):
                        continue
                    elif url.startswith("http"):
                        try:
                            resp = requests.get(url, timeout=10)
                            if resp.status_code < 400:
                                unsubscribed.append({
                                    "id": mail.gmail_msg_id,
                                    "subject": mail.subject if mail.subject is not None else None,
                                    "sender": mail.sender if mail.sender is not None else None,
                                    "snippet": getattr(mail, "snippet", None),
                                    "received_at": mail.received_at.isoformat() if mail.received_at else None,
                                    "is_read": mail.is_read if mail.is_read is not None else None,
                                    "is_starred": mail.is_starred if mail.is_starred is not None else None,
                                    "unsub_url": url
                                })
                                break
                        except Exception as e:
                            failed.append({"id": mail.gmail_msg_id, "error": str(e)})
            else:
                failed.append({"id": mail.gmail_msg_id, "error": "List-Unsubscribe 헤더 없음"})
        except Exception as e:
            failed.append({"id": mail.gmail_msg_id, "error": str(e)})
    return {"unsubscribed": unsubscribed, "failed": failed, "count": len(unsubscribed)} 