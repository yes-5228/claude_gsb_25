"""保洁巡查记录业务逻辑。"""

from datetime import date, datetime, time

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.exceptions import DomainError, NotFoundError
from app.models import Inspection, Restroom
from app.schemas.inspection import InspectionCreate, InspectionOut, InspectionUpdate
from app.services import restroom_service, scoring, shift_config_service

SORTABLE_FIELDS = {
    "inspect_time": Inspection.inspect_time,
    "score": Inspection.score,
    "inspector": Inspection.inspector,
    "created_at": Inspection.created_at,
}


def _shift_value(shift) -> str:
    return shift.value if hasattr(shift, "value") else shift


def _normalize_items(items: list) -> list[dict]:
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
            raise DomainError(f"检查项{name}重复提交")
        seen.add(name)
        normalized.append(
            {"name": name, "score": float(data.get("score", 0)), "remark": data.get("remark")}
        )
    return normalized


def _items_for_shift(items: list, shift: str, expected: list[str]) -> list[dict]:
    """校验打分明细与该班次当前生效组合完全一致，并按组合顺序返回。

    同一条巡查不允许只提交组合的一部分，也不允许混入组合之外的项目，
    从提交入口保证一条记录整体绑定同一版组合，不会一半新一半旧。
    """
    normalized = _normalize_items(items)
    by_name = {item["name"]: item for item in normalized}
    names = set(by_name)
    expected_set = set(expected)
    missing = [name for name in expected if name not in names]
    extra = [name for name in names if name not in expected_set]
    if missing or extra:
        problems = []
        if missing:
            problems.append(f"缺少{'、'.join(missing)}")
        if extra:
            problems.append(f"多报{'、'.join(sorted(extra))}")
        raise DomainError(
            f"提交的检查项与{shift}当前检查项组合不一致：{'；'.join(problems)}。"
            "请按该班次当前组合整套提交。"
        )
    return [by_name[name] for name in expected]


def get_inspection(db: Session, inspection_id: int) -> Inspection:
    inspection = db.get(Inspection, inspection_id)
    if inspection is None:
        raise NotFoundError(f"巡查记录 {inspection_id} 不存在")
    return inspection


def to_out(inspection: Inspection) -> InspectionOut:
    data = InspectionOut.model_validate(inspection)
    data.issue_count = len(inspection.issues)
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
    shift = _shift_value(payload.shift)
    expected, version = shift_config_service.current_items(db, shift)
    items = _items_for_shift(payload.items, shift, expected)
    score, grade, result = scoring.evaluate(items)
    inspection = Inspection(
        restroom_id=payload.restroom_id,
        inspector=payload.inspector,
        shift=shift,
        inspect_time=payload.inspect_time or datetime.now(),
        items=items,
        check_items=list(expected),
        check_config_version=version,
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

    new_shift = inspection.shift
    if data.get("shift") is not None and payload.shift is not None:
        new_shift = _shift_value(payload.shift)

    # 调整分数或班次都必须按目标班次当前组合整套重提，禁止只改组合中的一部分，
    # 也禁止改了班次却沿用旧组合——一条记录只能整体绑定一版组合。
    if data.get("items") is not None:
        expected, version = shift_config_service.current_items(db, new_shift)
        items = _items_for_shift(payload.items or [], new_shift, expected)
        score, grade, result = scoring.evaluate(items)
        inspection.items = items
        inspection.shift = new_shift
        inspection.check_items = list(expected)
        inspection.check_config_version = version
        inspection.score = score
        inspection.grade = grade
        inspection.result = result
    elif new_shift != inspection.shift:
        raise DomainError(
            f"调整班次为{new_shift}后，检查项组合随之变化，"
            f"请按{new_shift}当前组合整套重新提交检查项打分明细"
        )

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
