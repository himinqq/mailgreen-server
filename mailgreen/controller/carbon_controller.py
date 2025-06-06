from typing import Dict
from uuid import UUID
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Query

from mailgreen.services.carbon_service import get_carbon_stats_service

router = APIRouter(prefix="/carbon", tags=["carbon"])

@router.get("")
def get_carbon_stats(user_id: str = Query(..., description="User UUID")):
    now = datetime.now(timezone.utc)
    start_of_week = now - timedelta(days=now.weekday())
    return get_carbon_stats_service(user_id)
