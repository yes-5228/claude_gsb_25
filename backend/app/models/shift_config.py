"""班次检查项组合配置。

每个班次一行，保存当前生效的检查项组合与版本号。组合调整时 version 递增、
updated_at 刷新，只对调整之后提交的巡查生效；历史巡查通过自身保存的组合快照
还原当时口径，不回改、不重算。
"""

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy import JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ShiftCheckConfig(Base):
    """单个班次当前生效的检查项组合。"""

    __tablename__ = "shift_check_configs"

    shift: Mapped[str] = mapped_column(String(20), primary_key=True, comment="班次")
    version: Mapped[int] = mapped_column(Integer, default=1, comment="组合版本号，每次调整 +1")
    check_items: Mapped[list[str]] = mapped_column(
        JSON, default=list, comment="该班次生效中的检查项名称组合（有序）"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, onupdate=datetime.now, comment="最近调整时间"
    )
    updated_by: Mapped[str | None] = mapped_column(
        String(60), nullable=True, comment="最近调整操作人"
    )
    remark: Mapped[str | None] = mapped_column(Text, nullable=True, comment="调整说明")
