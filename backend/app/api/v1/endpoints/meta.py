"""字典接口：供前端下拉选项使用。"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.constants import (
    INSPECTION_CHECK_ITEMS,
    INSPECTION_ITEM_MAX_SCORE,
    ISSUE_TRANSITIONS,
    IssueCategory,
    IssueSeverity,
    IssueStatus,
    RestroomGrade,
    RestroomStatus,
    Shift,
)
from app.core.database import get_db
from app.schemas.checklist import ChecklistUpdate, ChecklistVersionOut
from app.services import checklist_service, inspection_service

router = APIRouter(prefix="/meta", tags=["字典"])


class RestroomOption(BaseModel):
    id: int
    code: str
    name: str
    district: str


class Dictionaries(BaseModel):
    restroom_status: list[str]
    restroom_grade: list[str]
    shift: list[str]
    issue_category: list[str]
    issue_severity: list[str]
    issue_status: list[str]
    inspection_check_items: list[str]
    shift_checklists: dict[str, list[str]]
    inspection_item_max_score: int
    issue_transitions: dict[str, list[str]]


@router.get("/dictionaries", response_model=Dictionaries, summary="枚举字典")
def get_dictionaries(db: Annotated[Session, Depends(get_db)]) -> Dictionaries:
    currents = checklist_service.list_current(db)
    return Dictionaries(
        restroom_status=[item.value for item in RestroomStatus],
        restroom_grade=[item.value for item in RestroomGrade],
        shift=[item.value for item in Shift],
        issue_category=[item.value for item in IssueCategory],
        issue_severity=[item.value for item in IssueSeverity],
        issue_status=[item.value for item in IssueStatus],
        inspection_check_items=list(INSPECTION_CHECK_ITEMS),
        shift_checklists={item.shift: item.items for item in currents},
        inspection_item_max_score=INSPECTION_ITEM_MAX_SCORE,
        issue_transitions={key: list(value) for key, value in ISSUE_TRANSITIONS.items()},
    )


@router.get("/checklists", response_model=list[ChecklistVersionOut], summary="各班次当前检查项组合")
def get_checklists(db: Annotated[Session, Depends(get_db)]) -> list[ChecklistVersionOut]:
    return [
        ChecklistVersionOut.model_validate(item) for item in checklist_service.list_current(db)
    ]


@router.get(
    "/checklists/history",
    response_model=list[ChecklistVersionOut],
    summary="班次组合历史版本",
)
def get_checklist_history(
    db: Annotated[Session, Depends(get_db)],
    shift: Annotated[str, Query(description="班次")],
) -> list[ChecklistVersionOut]:
    return [
        ChecklistVersionOut.model_validate(item)
        for item in checklist_service.list_versions(db, shift)
    ]


@router.put(
    "/checklists/{shift}",
    response_model=ChecklistVersionOut,
    summary="调整班次检查项组合（只对之后的录入生效）",
)
def update_checklist(
    shift: str, payload: ChecklistUpdate, db: Annotated[Session, Depends(get_db)]
) -> ChecklistVersionOut:
    version = checklist_service.update_checklist(db, shift, payload.items)
    return ChecklistVersionOut.model_validate(version)


@router.get("/restroom-options", response_model=list[RestroomOption], summary="公厕下拉选项")
def get_restroom_options(
    db: Annotated[Session, Depends(get_db)], keyword: str | None = None
) -> list[RestroomOption]:
    rows = inspection_service.restroom_options(db, keyword=keyword)
    return [
        RestroomOption(id=row.id, code=row.code, name=row.name, district=row.district)
        for row in rows
    ]
