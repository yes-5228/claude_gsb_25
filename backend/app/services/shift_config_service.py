"""班次检查项组合配置业务逻辑。

组合按版本管理：调整只写新版本（version +1），不改动任何已提交巡查；
巡查在提交时绑定当时的组合快照，因此历史记录始终按提交当时的组合展示与算分。
"""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.constants import (
    DEFAULT_SHIFT_CHECK_ITEMS,
    INSPECTION_CHECK_ITEMS,
    INSPECTION_COMPARABLE_ITEMS,
    Shift,
)
from app.core.exceptions import DomainError, NotFoundError
from app.models import ShiftCheckConfig
from app.schemas.shift_config import ShiftCheckConfigOut, ShiftCheckConfigUpdate

SHIFT_VALUES = [shift.value for shift in Shift]
_CHECK_ITEM_POOL = set(INSPECTION_CHECK_ITEMS)
_COMPARABLE_SET = set(INSPECTION_COMPARABLE_ITEMS)


def ensure_defaults(db: Session) -> None:
    """库中缺少班次配置时按默认组合初始化（v1），已存在则保持不变。"""

    changed = False
    for shift in Shift:
        exists = db.get(ShiftCheckConfig, shift.value)
        if exists is None:
            db.add(
                ShiftCheckConfig(
                    shift=shift.value,
                    version=1,
                    check_items=list(DEFAULT_SHIFT_CHECK_ITEMS[shift]),
                    updated_at=datetime.now(),
                    remark="系统默认组合",
                )
            )
            changed = True
    if changed:
        db.commit()


def _to_out(config: ShiftCheckConfig) -> ShiftCheckConfigOut:
    out = ShiftCheckConfigOut.model_validate(config)
    out.comparable_covered = _COMPARABLE_SET.issubset(set(config.check_items))
    return out


def list_configs(db: Session) -> list[ShiftCheckConfigOut]:
    ensure_defaults(db)
    rows = list(db.scalars(select(ShiftCheckConfig)))
    rows.sort(key=lambda row: SHIFT_VALUES.index(row.shift) if row.shift in SHIFT_VALUES else 99)
    return [_to_out(row) for row in rows]


def get_config_model(db: Session, shift: str) -> ShiftCheckConfig:
    ensure_defaults(db)
    config = db.get(ShiftCheckConfig, shift)
    if config is None:
        raise NotFoundError(f"班次 {shift} 不存在")
    return config


def get_config(db: Session, shift: str) -> ShiftCheckConfigOut:
    return _to_out(get_config_model(db, shift))


def current_items(db: Session, shift: str) -> tuple[list[str], int]:
    """返回该班次当前生效的（检查项组合, 版本号）。"""

    config = get_config_model(db, shift)
    return list(config.check_items), config.version


def validate_check_items(check_items: list[str]) -> list[str]:
    """校验组合：非空、不重复、必须取自检查项库，返回去重保序后的组合。"""

    names = [str(name).strip() for name in check_items]
    if not names or any(not name for name in names):
        raise DomainError("班次检查项不能为空")
    unknown = [name for name in names if name not in _CHECK_ITEM_POOL]
    if unknown:
        raise DomainError(f"检查项{'、'.join(unknown)}不在检查项库中")
    if len(set(names)) != len(names):
        raise DomainError("班次检查项不能重复")
    return names


def update_config(
    db: Session, shift: str, payload: ShiftCheckConfigUpdate
) -> ShiftCheckConfigOut:
    if shift not in SHIFT_VALUES:
        raise NotFoundError(f"班次 {shift} 不存在")
    items = validate_check_items(payload.check_items)
    config = get_config_model(db, shift)
    if items == list(config.check_items):
        raise DomainError("新组合与当前生效组合一致，无需调整")
    config.check_items = items
    config.version += 1
    config.updated_at = datetime.now()
    config.updated_by = payload.updated_by
    config.remark = payload.remark
    db.commit()
    db.refresh(config)
    return _to_out(config)
