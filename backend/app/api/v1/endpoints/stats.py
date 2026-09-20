"""统计看板接口。"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.stats import DashboardStats, OverviewStats, ShiftComparison
from app.services import stats_service

router = APIRouter(prefix="/stats", tags=["统计看板"])


@router.get("/overview", response_model=OverviewStats, summary="核心指标")
def get_overview(db: Annotated[Session, Depends(get_db)]) -> OverviewStats:
    return stats_service.overview(db)


@router.get("/shift-comparison", response_model=ShiftComparison, summary="跨班次均分对比")
def get_shift_comparison(db: Annotated[Session, Depends(get_db)]) -> ShiftComparison:
    return stats_service.shift_comparison(db)


@router.get("/dashboard", response_model=DashboardStats, summary="看板聚合数据")
def get_dashboard(
    db: Annotated[Session, Depends(get_db)],
    trend_days: Annotated[int, Query(ge=3, le=60, description="趋势天数")] = 14,
) -> DashboardStats:
    return stats_service.dashboard(db, trend_days=trend_days)
