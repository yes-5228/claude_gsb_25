"""班次检查项组合配置相关数据结构。"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ShiftCheckConfigUpdate(BaseModel):
    """调整某班次的检查项组合，调整后版本号 +1，仅对之后提交的巡查生效。"""

    check_items: list[str] = Field(min_length=1, description="新的检查项名称组合")
    updated_by: str | None = Field(default=None, max_length=60, description="操作人")
    remark: str | None = Field(default=None, max_length=500, description="调整说明")


class ShiftCheckConfigOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    shift: str
    version: int
    check_items: list[str]
    comparable_covered: bool = Field(
        default=True, description="该组合是否覆盖跨班次折算用的全部固定可比项"
    )
    updated_at: datetime
    updated_by: str | None = None
    remark: str | None = None
