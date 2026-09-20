"""班次检查项组合配置接口。"""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.shift_config import ShiftCheckConfigOut, ShiftCheckConfigUpdate
from app.services import shift_config_service

router = APIRouter(prefix="/shift-check-configs", tags=["班次检查项配置"])


@router.get("", response_model=list[ShiftCheckConfigOut], summary="各班次当前检查项组合")
def list_configs(db: Annotated[Session, Depends(get_db)]) -> list[ShiftCheckConfigOut]:
    return shift_config_service.list_configs(db)


@router.get("/{shift}", response_model=ShiftCheckConfigOut, summary="指定班次当前组合")
def get_config(shift: str, db: Annotated[Session, Depends(get_db)]) -> ShiftCheckConfigOut:
    return shift_config_service.get_config(db, shift)


@router.put(
    "/{shift}", response_model=ShiftCheckConfigOut, summary="调整班次检查项组合（仅对之后生效）"
)
def update_config(
    shift: str,
    payload: ShiftCheckConfigUpdate,
    db: Annotated[Session, Depends(get_db)],
) -> ShiftCheckConfigOut:
    return shift_config_service.update_config(db, shift, payload)
