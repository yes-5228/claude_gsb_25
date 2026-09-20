"""ORM 模型集合。"""

from app.models.inspection import Inspection
from app.models.issue import Issue, RectificationRecord
from app.models.restroom import Restroom
from app.models.shift_config import ShiftCheckConfig

__all__ = ["Restroom", "Inspection", "Issue", "RectificationRecord", "ShiftCheckConfig"]
