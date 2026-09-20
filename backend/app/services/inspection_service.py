"""保洁巡查记录业务逻辑。"""

from datetime import date, datetime, time

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.exceptions import DomainError, NotFoundError
from app.models import Inspection, Restroom
from app.schemas.inspection import InspectionCreate, InspectionOut, InspectionUpdate
from app.services import checklist_service, restroom_service, scoring

SORTABLE_FIELDS = {
    "inspect_time": Inspection.inspect_time,
    "score": Inspection.score,
    "inspector": Inspection.inspector,
    "created_at": Inspection.created_at,
}


def _normalize_items(items: list, expected_names: list[str] | None = None) -> list[dict]:
    """校验并展开打分明细。

    指定 expected_names（班次组合）时，提交的项必须与组合完全一致：
    缺项、含组合外项目都会拒绝，并按组合顺序展开，
    保证同一条巡查整体按同一个组合版本展开，不混用新旧组合。
    """
    if not items:
        raise DomainError("巡查检查项不能为空")
    normalized: list[dict] = []
    seen: set[str] = set()
    for item in items:
        data = item.model_dump() if hasattr(item, "model_dump") else dict(item)
        name = str(data.get("name", "")).strip()
        if not name:
            raise DomainError("检查项名称不能为空")
        if name in seen:
            raise DomainError(f"检查项 {name} 重复提交")
        seen.add(name)
        normalized.append(
            {"name": name, "score": float(data.get("score", 0)), "remark": data.get("remark")}
        )
    if expected_names is not None:
        expected = list(dict.fromkeys(expected_names))
        allowed = set(expected)
        missing = [name for name in expected if name not in seen]
        extra = [name for name in seen if name not in allowed]
        if missing or extra:
            parts = []
            if missing:
                parts.append("缺少：" + "、".join(missing))
            if extra:
                parts.append("非本组合：" + "、".join(extra))
            raise DomainError("检查项须与班次当前组合完全一致（" + "；".join(parts) + "）")
        order = {name: index for index, name in enumerate(expected)}
        normalized.sort(key=lambda entry: order[entry["name"]])
    return normalized


def get_inspection(db: Session, inspection_id: int) -> Inspection:
    inspection = db.get(Inspection, inspection_id)
    if inspection is None:
        raise NotFoundError(f"巡查记录 {inspection_id} 不存在")
    return inspection


def to_out(inspection: Inspection) -> InspectionOut:
    data = InspectionOut.model_validate(inspection)
    data.issue_count = len(inspection.issues)
    data.checklist_version = inspection.checklist.version if inspection.checklist else None
    return data


def list_inspections(
    db: Session,
    *,
    restroom_id: int | None = None,
    district: str | None = None,
    inspector: str | None = None,
    shift: str | None = None,
    result: str | None = None,
    keyword: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    page: int = 1,
    page_size: int = 10,
    sort_by: str = "inspect_time",
    order: str = "desc",
) -> tuple[list[Inspection], int]:
    stmt = select(Inspection)
    if district:
        stmt = stmt.join(Restroom, Restroom.id == Inspection.restroom_id).where(
            Restroom.district == district
        )
    if restroom_id:
        stmt = stmt.where(Inspection.restroom_id == restroom_id)
    if inspector:
        stmt = stmt.where(Inspection.inspector.like(f"%{inspector.strip()}%"))
    if shift:
        stmt = stmt.where(Inspection.shift == shift)
    if result:
        stmt = stmt.where(Inspection.result == result)
    if date_from:
        stmt = stmt.where(Inspection.inspect_time >= datetime.combine(date_from, time.min))
    if date_to:
        stmt = stmt.where(Inspection.inspect_time <= datetime.combine(date_to, time.max))
    if keyword:
        like = f"%{keyword.strip()}%"
        stmt = stmt.where(
            or_(
                Inspection.inspector.like(like),
                Inspection.remark.like(like),
                Inspection.restroom_id.in_(select(Restroom.id).where(Restroom.name.like(like))),
            )
        )

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    column = SORTABLE_FIELDS.get(sort_by, Inspection.inspect_time)
    stmt = stmt.order_by(column.desc() if order == "desc" else column.asc(), Inspection.id.desc())
    rows = list(db.scalars(stmt.offset((page - 1) * page_size).limit(page_size)))
    return rows, total


def create_inspection(db: Session, payload: InspectionCreate) -> Inspection:
    restroom_service.get_restroom(db, payload.restroom_id)
    shift = payload.shift.value if hasattr(payload.shift, "value") else payload.shift
    # 以提交时刻班次的当前组合为准展开，并绑定该组合版本作为快照锚点
    checklist = checklist_service.current_version(db, shift)
    items = _normalize_items(payload.items, checklist.items)
    score, grade, result = scoring.evaluate(items)
    inspection = Inspection(
        restroom_id=payload.restroom_id,
        inspector=payload.inspector,
        shift=shift,
        checklist_version_id=checklist.id,
        inspect_time=payload.inspect_time or datetime.now(),
        items=items,
        score=score,
        grade=grade,
        result=result,
        remark=payload.remark,
    )
    db.add(inspection)
    db.commit()
    db.refresh(inspection)
    restroom_service.touch(db, payload.restroom_id)
    return inspection


def update_inspection(db: Session, inspection_id: int, payload: InspectionUpdate) -> Inspection:
    inspection = get_inspection(db, inspection_id)
    data = payload.model_dump(exclude_unset=True)
    new_shift = None
    if data.get("shift") is not None and payload.shift is not None:
        new_shift = payload.shift.value if hasattr(payload.shift, "value") else payload.shift
    shift_changed = new_shift is not None and new_shift != inspection.shift
    if data.get("items") is not None:
        checklist = None
        if shift_changed:
            # 换班次即换组合：按新班次当前组合校验展开，并重新绑定版本
            checklist = checklist_service.current_version(db, new_shift)
            expected = checklist.items
        elif inspection.checklist is not None:
            # 项集合必须仍属于提交时绑定的组合版本，不能混入新组合的项目
            expected = inspection.checklist.items
        else:
            # 组合功能上线前的历史记录：项集合维持自身快照，只允许改分数
            expected = [item["name"] for item in inspection.items]
        items = _normalize_items(payload.items or [], expected)
        score, grade, result = scoring.evaluate(items)
        inspection.items = items
        inspection.score = score
        inspection.grade = grade
        inspection.result = result
        if checklist is not None:
            inspection.checklist_version_id = checklist.id
    elif shift_changed:
        raise DomainError("调整班次需同时按新班次当前的检查项组合重新提交各项打分")
    if shift_changed:
        inspection.shift = new_shift
    if data.get("inspector") is not None:
        inspection.inspector = payload.inspector or inspection.inspector
    if data.get("inspect_time") is not None and payload.inspect_time is not None:
        inspection.inspect_time = payload.inspect_time
    if "remark" in data:
        inspection.remark = payload.remark
    db.commit()
    db.refresh(inspection)
    return inspection


def delete_inspection(db: Session, inspection_id: int) -> None:
    inspection = get_inspection(db, inspection_id)
    db.delete(inspection)
    db.commit()


def restroom_options(db: Session, keyword: str | None = None, limit: int = 50) -> list[Restroom]:
    stmt = select(Restroom).order_by(Restroom.code)
    if keyword:
        like = f"%{keyword.strip()}%"
        stmt = stmt.where(or_(Restroom.name.like(like), Restroom.code.like(like)))
    return list(db.scalars(stmt.limit(limit)))
