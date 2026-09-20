"""班次检查项组合版本模型。"""

from datetime import datetime

from sqlalchemy import JSON, DateTime, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ChecklistVersion(Base):
    """某班次检查项组合的一个版本。

    组合调整即追加新版本（version 递增），旧版本保留，
    供历史巡查记录按提交当时的组合回溯展示与算分。
    """

    __tablename__ = "checklist_versions"
    __table_args__ = (UniqueConstraint("shift", "version", name="uq_checklist_shift_version"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    shift: Mapped[str] = mapped_column(String(20), index=True, comment="班次")
    version: Mapped[int] = mapped_column(Integer, comment="版本号，从 1 开始递增")
    items: Mapped[list[str]] = mapped_column(JSON, default=list, comment="检查项名称列表（有序）")
    effective_from: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, comment="生效时间，只对之后的录入生效"
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
