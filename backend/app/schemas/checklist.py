"""班次检查项组合相关数据结构。"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ChecklistVersionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    shift: str
    version: int
    items: list[str]
    effective_from: datetime


class ChecklistUpdate(BaseModel):
    items: list[str] = Field(min_length=1, description="检查项名称列表，须全部来自检查项池")
