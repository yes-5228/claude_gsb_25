"""班次检查项组合：版本管理与跨班次可比项目。"""

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.constants import (
    DEFAULT_SHIFT_CHECKLISTS,
    INSPECTION_CHECK_ITEMS,
    Shift,
)
from app.core.exceptions import DomainError
from app.models import ChecklistVersion


def ensure_default_checklists(db: Session) -> None:
    """为没有任何版本的班次写入默认组合（v1）；已有版本的班次保持不动。"""
    for shift in Shift:
        exists = db.scalar(
            select(func.count())
            .select_from(ChecklistVersion)
            .where(ChecklistVersion.shift == shift.value)
        )
        if exists:
            continue
        db.add(
            ChecklistVersion(
                shift=shift.value,
                version=1,
                items=list(DEFAULT_SHIFT_CHECKLISTS[shift]),
                effective_from=datetime.now(),
            )
        )
    db.commit()


def current_version(db: Session, shift: str) -> ChecklistVersion:
    """取班次当前生效的组合版本；尚未配置时先补默认版本。"""
    version = db.scalar(
        select(ChecklistVersion)
        .where(ChecklistVersion.shift == shift)
        .order_by(ChecklistVersion.version.desc())
        .limit(1)
    )
    if version is None:
        ensure_default_checklists(db)
        version = db.scalar(
            select(ChecklistVersion)
            .where(ChecklistVersion.shift == shift)
            .order_by(ChecklistVersion.version.desc())
            .limit(1)
        )
    if version is None:
        raise DomainError(f"班次 {shift} 未配置检查项组合")
    return version


def list_current(db: Session) -> list[ChecklistVersion]:
    """各班次当前生效的组合，按班次固定顺序返回。"""
    ensure_default_checklists(db)
    return [current_version(db, shift.value) for shift in Shift]


def list_versions(db: Session, shift: str) -> list[ChecklistVersion]:
    """某班次的全部组合版本，新的在前。"""
    _ensure_known_shift(shift)
    return list(
        db.scalars(
            select(ChecklistVersion)
            .where(ChecklistVersion.shift == shift)
            .order_by(ChecklistVersion.version.desc())
        )
    )


def update_checklist(db: Session, shift: str, items: list[str]) -> ChecklistVersion:
    """调整组合：追加新版本，只对该时刻之后录入的巡查生效；无变化时不产生新版本。"""
    _ensure_known_shift(shift)
    cleaned = _validate_items(items)
    current = current_version(db, shift)
    if cleaned == current.items:
        return current
    version = ChecklistVersion(
        shift=shift,
        version=current.version + 1,
        items=cleaned,
        effective_from=datetime.now(),
    )
    db.add(version)
    db.commit()
    db.refresh(version)
    return version


def comparable_items(db: Session) -> list[str]:
    """可比项目：各班次现行组合的交集，按检查项池的顺序输出，保证结果稳定唯一。"""
    currents = list_current(db)
    if not currents:
        return []
    common = set(currents[0].items)
    for version in currents[1:]:
        common &= set(version.items)
    return [name for name in INSPECTION_CHECK_ITEMS if name in common]


def _ensure_known_shift(shift: str) -> None:
    if shift not in {item.value for item in Shift}:
        raise DomainError(f"未知班次：{shift}")


def _validate_items(items: list[str]) -> list[str]:
    """组合必须非空、无重复，且全部来自检查项池。"""
    if not items:
        raise DomainError("检查项组合不能为空")
    pool = set(INSPECTION_CHECK_ITEMS)
    cleaned: list[str] = []
    seen: set[str] = set()
    for raw in items:
        name = str(raw).strip()
        if not name:
            raise DomainError("检查项名称不能为空")
        if name not in pool:
            raise DomainError(f"检查项「{name}」不在可选检查项池中")
        if name in seen:
            raise DomainError(f"检查项「{name}」重复")
        seen.add(name)
        cleaned.append(name)
    return cleaned
