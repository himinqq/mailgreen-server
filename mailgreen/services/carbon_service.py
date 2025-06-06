import logging
from datetime import datetime, timedelta, timezone
from collections import defaultdict
from mailgreen.app.database import SessionLocal
from mailgreen.app.models import MailEmbedding

logger = logging.getLogger(__name__)

def estimate_email_energy_saved(size_in_kb):
    # 크기 기준 탄소 배출량 추정 (보수적으로 설정)
    if size_in_kb < 100:
        co2 = 1.0  # 텍스트 (1g)
    elif size_in_kb < 1024: 
        co2 = 4.0  # HTML or 마케팅 메일 (4g)
    elif size_in_kb < 5120:
        co2 = 15.0  # 일반 첨부 (15g)
    else:
        co2 = 75.0  # 대형 첨부 (75g)
    return co2 * 0.0025  # kWh로 환산


def get_carbon_stats_service(user_id: str):
    db = SessionLocal()
    try:
        now = datetime.utcnow()
        # 1. 삭제된 메일 전체 조회
        deleted_mails = db.query(MailEmbedding).filter(
            MailEmbedding.user_id == user_id,
            MailEmbedding.is_deleted == True,
            MailEmbedding.deleted_at.isnot(None)
        ).all()

        # 2. 누적 절감량/전력량/개수
        total_carbon = 0.0
        total_energy = 0.0
        for mail in deleted_mails:
            size_kb = (mail.size_bytes or 0) / 1024
            total_energy += estimate_email_energy_saved(size_kb)
            # 탄소량은 위의 co2 값(estimate_email_energy_saved에서 kWh로 환산 전 값) 합산
            if size_kb < 100:
                co2 = 1.0
            elif size_kb < 1024:
                co2 = 4.0
            elif size_kb < 5120:
                co2 = 15.0
            else:
                co2 = 75.0
            total_carbon += co2
        total_count = len(deleted_mails)

        # 3. 이번주 절감량/전력량/개수
        start_of_week = now - timedelta(days=now.weekday())
        week_carbon = 0.0
        week_energy = 0.0
        week_count = 0
        for mail in deleted_mails:
            if mail.deleted_at:
                mail_deleted_at = mail.deleted_at
                if mail_deleted_at.tzinfo is None or mail_deleted_at.tzinfo.utcoffset(mail_deleted_at) is None:
                    mail_deleted_at = mail_deleted_at.replace(tzinfo=timezone.utc)
                if start_of_week.tzinfo is None or start_of_week.tzinfo.utcoffset(start_of_week) is None:
                    start_of_week = start_of_week.replace(tzinfo=timezone.utc)
                if mail_deleted_at >= start_of_week:
                    size_kb = (mail.size_bytes or 0) / 1024
                    week_energy += estimate_email_energy_saved(size_kb)
                    if size_kb < 100:
                        co2 = 1.0
                    elif size_kb < 1024:
                        co2 = 4.0
                    elif size_kb < 5120:
                        co2 = 15.0
                    else:
                        co2 = 75.0
                    week_carbon += co2
                    week_count += 1

        # 4. 연속 절감 주 계산 (삭제된 주차별로 그룹핑)
        week_set = set()
        for mail in deleted_mails:
            if mail.deleted_at:
                mail_deleted_at = mail.deleted_at
                if mail_deleted_at.tzinfo is None or mail_deleted_at.tzinfo.utcoffset(mail_deleted_at) is None:
                    mail_deleted_at = mail_deleted_at.replace(tzinfo=timezone.utc)
                year, week_num, _ = mail_deleted_at.isocalendar()
                week_set.add((year, week_num))
        if not week_set:
            streak = 0
        else:
            week_list = sorted(week_set, reverse=True)
            streak = 1
            prev_year, prev_week = week_list[0]
            for y, w in week_list[1:]:
                # ISO week: 연도/주차가 1씩 차이나면 연속
                if (prev_year == y and prev_week == w + 1) or (prev_year == y + 1 and prev_week == 1 and w == 52):
                    streak += 1
                    prev_year, prev_week = y, w
                else:
                    break

        return {
            "week_carbon_saved_g": round(week_carbon, 2),
            "total_carbon_saved_g": round(total_carbon, 2),
            "week_energy_saved_kwh": round(week_energy, 4),
            "total_energy_saved_kwh": round(total_energy, 4),
            "week_deleted_count": week_count,
            "total_deleted_count": total_count,
            "consecutive_weeks": streak,
        }
    finally:
        db.close()
