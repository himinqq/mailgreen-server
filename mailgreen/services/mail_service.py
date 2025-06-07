import logging
import time
import random

from datetime import datetime, timezone, timedelta
from typing import List, Optional
from urllib.error import HTTPError

from googleapiclient.errors import HttpError
from sqlalchemy.orm import Session, Query

from mailgreen.app.models import MailEmbedding, AnalysisTask
from dateutil.relativedelta import relativedelta

logger = logging.getLogger(__name__)


def filter_mails(
    query: Query,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    is_read: Optional[bool] = None,
    older_than_months: Optional[int] = None,
    min_size_mb: Optional[float] = None,
) -> Query:
    if start_date:
        try:
            dt_start = datetime.fromisoformat(start_date)
        except ValueError:
            raise HTTPError(status_code=400, detail="start_date 형식 오류 (YYYY-MM-DD)")
        query = query.filter(MailEmbedding.received_at >= dt_start)

    if end_date:
        try:
            dt_end = datetime.fromisoformat(end_date)
        except ValueError:
            raise HTTPError(status_code=400, detail="end_date 형식 오류 (YYYY-MM-DD)")
        query = query.filter(MailEmbedding.received_at <= dt_end)

    if is_read is not None:
        query = query.filter(MailEmbedding.is_read == is_read)

    if older_than_months is not None:
        cutoff = datetime.now(timezone.utc) - relativedelta(months=older_than_months)
        query = query.filter(MailEmbedding.received_at <= cutoff)

    if min_size_mb is not None:
        try:
            bytes_threshold = int(float(min_size_mb) * 1024 * 1024)
        except ValueError:
            raise HTTPError(status_code=400, detail="min_size_mb must be a number")
        query = query.filter(MailEmbedding.size_bytes >= bytes_threshold)

    return query


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


CO2_PER_EMAIL_G = 4.0  # 메일 하나당 절감 탄소량(g)


def trash_mails(
    db: Session,
    service,
    message_ids: List[str],
    confirm: bool = False,
) -> dict:
    count = len(message_ids)
    estimated_saved = round(count * CO2_PER_EMAIL_G, 2)
    deleted_ids = []
    errors = []

    if not confirm:
        for gmail_msg_id in message_ids:
            deleted_ids.append(f"{gmail_msg_id} (dry-run)")
        return {
            "requested_count": count,
            "deleted": False,
            "estimated_carbon_saved_g": estimated_saved,
            "deleted_ids": deleted_ids,
            "errors": [],
        }

    for gmail_msg_id in message_ids:
        try:
            service.users().messages().trash(userId="me", id=gmail_msg_id).execute()
            deleted_ids.append(gmail_msg_id)
        except HttpError as e:
            error_detail = None
            try:
                error_detail = e.error_details or e.content.decode()
            except:
                pass
            errors.append(
                {
                    "msg_id": gmail_msg_id,
                    "error": f"Gmail API 에러: {str(e)}",
                    "details": error_detail,
                }
            )
            continue

        record = (
            db.query(MailEmbedding)
            .filter(MailEmbedding.gmail_msg_id == gmail_msg_id)
            .first()
        )
        if record:
            record.is_deleted = True
            record.deleted_at = datetime.utcnow()
        else:
            errors.append(
                {
                    "msg_id": gmail_msg_id,
                    "error": "DB에서 해당 Gmail 메시지 ID를 찾을 수 없습니다.",
                }
            )

    try:
        db.commit()
    except Exception as db_err:
        db.rollback()
        raise HTTPError(status_code=500, detail=f"DB 업데이트 실패: {str(db_err)}")

    return {
        "requested_count": count,
        "deleted": True,
        "estimated_carbon_saved_g": estimated_saved,
        "deleted_ids": deleted_ids,
        "errors": errors,
    }


def start_analysis_task(db: Session, user_id: str) -> str:
    import uuid
    from datetime import datetime, timezone
    from mailgreen.tasks.mail_analysis import run_analysis

    # 이전에 실행된 Task 중 history_id가 있는 가장 최근 것 가져오기
    last = (
        db.query(AnalysisTask)
        .filter(AnalysisTask.user_id == user_id, AnalysisTask.history_id.isnot(None))
        .order_by(AnalysisTask.started_at.desc())
        .first()
    )
    start_history = last.history_id if last else None

    task_id = str(uuid.uuid4())
    task = AnalysisTask(
        id=task_id,
        user_id=user_id,
        task_type="email-analysis",
        status="pending",
        progress_pct=0,
        started_at=datetime.utcnow(),
        history_id=start_history,
    )
    db.add(task)
    db.commit()

    # Celery 비동기 작업 호출
    run_analysis.delay(
        user_id=user_id,
        task_id=task_id,
        start_history_id=start_history,
    )

    return start_history or ""


def get_analysis_progress(db: Session, user_id: str) -> dict:
    task = (
        db.query(AnalysisTask)
        .filter(AnalysisTask.user_id == user_id)
        .order_by(AnalysisTask.started_at.desc())
        .first()
    )
    if not task:
        return {"in_progress": False, "progress_pct": 0}

    in_progress = task.status not in ("done", "failed")
    response = {
        "in_progress": in_progress,
        "progress_pct": task.progress_pct or 0,
        "status": task.status,
    }
    if task.status == "failed":
        response["error_msg"] = task.error_msg

    return response


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
    service, msg_ids: List[str], batch_size: int = 50, max_retries: int = 5
) -> List[dict]:
    mails: List[dict] = []

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


def initial_load(service) -> List[dict]:
    ids = list_all_message_ids(service)
    return batch_fetch_metadata(service, ids)