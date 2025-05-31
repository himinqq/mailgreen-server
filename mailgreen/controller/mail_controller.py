import uuid
from datetime import datetime, timezone
from googleapiclient.discovery import build
from typing import List
from uuid import UUID

from dateutil.relativedelta import relativedelta
from fastapi import Depends, APIRouter, Query, HTTPException, Body
from googleapiclient.errors import HttpError
from pydantic import BaseModel
from sqlalchemy.orm import Session

from mailgreen.app.database import get_db
from mailgreen.services.mail_service import get_credentials
from mailgreen.tasks.mail_analysis import run_analysis
from mailgreen.app.models import AnalysisTask, MailEmbedding

router = APIRouter(prefix="/mail", tags=["mail"])


@router.post("/analyze")
def analyze_mail(user_id: UUID, db: Session = Depends(get_db)):
    last = (
        db.query(AnalysisTask)
        .filter(AnalysisTask.user_id == user_id, AnalysisTask.history_id != None)
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

    run_analysis.delay(
        user_id=str(user_id),
        task_id=task_id,
        start_history_id=start_history,
    )
    return {"message": "분석을 시작했습니다.", "start_history_id": start_history}


@router.get("/progress")
async def get_mail_progress(
    user_id: str = Query(..., description="User UUID"), db: Session = Depends(get_db)
):
    task = (
        db.query(AnalysisTask)
        .filter(AnalysisTask.user_id == user_id)
        .order_by(AnalysisTask.started_at.desc())
        .first()
    )
    if not task:
        return {"in_progress": False, "progress_pct": 0}

    if task.status in ("done", "failed"):
        in_progress = False
    else:
        in_progress = True

    response = {
        "in_progress": in_progress,
        "progress_pct": task.progress_pct or 0,
        "status": task.status,
    }

    if task.status == "failed":
        response["error_msg"] = task.error_msg

    return response


@router.get("/sender/top")
async def get_top_senders(
    user_id: str = Query(..., description="User UUID"),
    limit: int = Query(..., description="최대 발신자 수"),
    db: Session = Depends(get_db),
):
    from sqlalchemy import func
    from mailgreen.app.models import MailEmbedding
    from email.utils import parseaddr

    # 발신자별 메일 수 집계
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


@router.get("/sender")
async def get_sender_details(
    user_id: str = Query(..., description="User UUID"),
    sender: str | None = Query(None, description="발신자 이메일 or 이름"),
    start_date: str | None = Query(None, description="조회 시작일 (YYYY-MM-DD)"),
    end_date: str | None = Query(None, description="조회 종료일 (YYYY-MM-DD)"),
    is_read: bool | None = Query(None, description="읽음 여부 필터 (true/false)"),
    older_than_months: int | None = Query(
        None, description="지정 개월 이전 메일만 조회 (예: 1 → 1개월 이전 메일)"
    ),
    min_size_mb: float | None = Query(
        None, description="필터 기준 메일 크기 (MB 단위, 예: 0.1, 0.5, 1)"
    ),
    db: Session = Depends(get_db),
):
    # 기본 sender/UUID 필터
    query = db.query(MailEmbedding).filter(
        MailEmbedding.user_id == user_id,
    )

    # sender가 있는 경우에만 필터 추가
    if sender:
        query = query.filter(MailEmbedding.sender.ilike(f"%{sender}%"))

    # 날짜 범위 필터
    if start_date:
        try:
            dt_start = datetime.fromisoformat(start_date)
        except ValueError:
            raise HTTPException(400, "start_date 형식 오류 (YYYY-MM-DD)")
        query = query.filter(MailEmbedding.received_at >= dt_start)

    if end_date:
        try:
            dt_end = datetime.fromisoformat(end_date)
        except ValueError:
            raise HTTPException(400, "end_date 형식 오류 (YYYY-MM-DD)")
        query = query.filter(MailEmbedding.received_at <= dt_end)

    # Is Read: 읽음 여부 필터
    if is_read is not None:
        query = query.filter(MailEmbedding.is_read == is_read)

    # Old Mail: 지정 개월 이전 메일만
    if older_than_months is not None:
        cutoff = datetime.now(timezone.utc) - relativedelta(months=older_than_months)
        query = query.filter(MailEmbedding.received_at <= cutoff)

    # Large Mail: 지정 MB 이상 크기만 필터링
    if min_size_mb is not None:
        # 사용자 입력은 MB 단위 (소수 가능), 저장은 바이트 단위
        try:
            bytes_threshold = int(
                float(min_size_mb) * 1024 * 1024
            )  # ex. 0.1MB → 104857 bytes
        except ValueError:
            raise HTTPException(status_code=400, detail="min_size_mb must be a number")

        query = query.filter(MailEmbedding.size_bytes >= bytes_threshold)

    # 정렬 및 결과 반환
    mails = query.order_by(MailEmbedding.received_at.desc()).all()

    return [
        {
            "id": m.gmail_msg_id,
            "subject": m.subject,
            "snippet": m.snippet,
            "received_at": m.received_at.isoformat(),
            "is_read": m.is_read,
        }
        for m in mails
    ]


class DeleteMailsRequest(BaseModel):
    message_ids: List[str]
    confirm: bool = False  # false면 삭제하지 않고 추정만


@router.delete("/trash")
async def trash_mails(
    user_id: str = Query(..., description="User UUID"),
    payload: DeleteMailsRequest = Body(
        ..., description="삭제할 메일 ID 목록과 확인 여부"
    ),
    db: Session = Depends(get_db),
):
    creds = get_credentials(user_id)
    service = build("gmail", "v1", credentials=creds)

    # 탄소량 (메일 하나당 4g 절감)
    CO2_PER_EMAIL_G = 4.0

    count = len(payload.message_ids)
    estimated_saved = round(count * CO2_PER_EMAIL_G, 2)

    deleted_ids = []
    errors = []

    # confirm=False
    if not payload.confirm:
        for gmail_msg_id in payload.message_ids:
            deleted_ids.append(f"{gmail_msg_id} (dry-run)")
        return {
            "requested_count": count,
            "deleted": False,
            "estimated_carbon_saved_g": estimated_saved,
            "deleted_ids": deleted_ids,
            "errors": [],
        }

    # confirm=True인 경우: 실제 삭제 수행
    for gmail_msg_id in payload.message_ids:
        try:
            # Gmail API 호출: 메일을 휴지통으로 이동
            service.users().messages().trash(userId="me", id=gmail_msg_id).execute()
            deleted_ids.append(gmail_msg_id)
        except HttpError as e:
            # Gmail API 호출 실패
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
            # 다음 ID 처리로 넘어감
            continue

        # DB 업데이트: MailEmbedding 레코드에 is_deleted=True, deleted_at=현재 시각
        record = (
            db.query(MailEmbedding)
            .filter(MailEmbedding.gmail_msg_id == gmail_msg_id)
            .first()
        )
        if record:
            record.is_deleted = True
            record.deleted_at = datetime.utcnow()
        else:
            # DB에 해당 레코드가 없으면
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
        raise HTTPException(status_code=500, detail=f"DB 업데이트 실패: {str(db_err)}")

    return {
        "requested_count": count,
        "deleted": True,
        "estimated_carbon_saved_g": estimated_saved,
        "deleted_ids": deleted_ids,
        "errors": errors,
    }
