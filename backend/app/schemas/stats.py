"""统计看板数据结构。"""

from pydantic import BaseModel, Field

from app.schemas.inspection import InspectionOut
from app.schemas.issue import IssueOut


class NameValue(BaseModel):
    name: str
    value: float


class OverviewStats(BaseModel):
    restroom_total: int = 0
    restroom_open: int = 0
    restroom_maintenance: int = 0
    inspection_total: int = 0
    inspection_today: int = 0
    inspection_week: int = 0
    avg_score_week: float = 0.0
    issue_total: int = 0
    issue_open: int = 0
    issue_overdue: int = 0
    issue_done_this_month: int = 0
    rectification_rate: float = Field(default=0.0, description="整改完成率（百分比）")


class TrendPoint(BaseModel):
    date: str
    inspections: int = 0
    issues: int = 0
    avg_score: float = 0.0


class CategoryStat(BaseModel):
    category: str
    total: int = 0
    open: int = 0
    closed: int = 0


class RestroomRankItem(BaseModel):
    restroom_id: int
    code: str
    name: str
    district: str
    inspection_count: int = 0
    avg_score: float = 0.0
    open_issues: int = 0


class DistrictStat(BaseModel):
    district: str
    restroom_count: int = 0
    issue_open: int = 0
    avg_score: float = 0.0


class DashboardStats(BaseModel):
    """看板一次拉取所需的全部指标。"""

    overview: OverviewStats
    issue_by_status: list[NameValue] = Field(default_factory=list)
    issue_by_category: list[CategoryStat] = Field(default_factory=list)
    issue_by_severity: list[NameValue] = Field(default_factory=list)
    inspection_trend: list[TrendPoint] = Field(default_factory=list)
    districts: list[DistrictStat] = Field(default_factory=list)
    top_restrooms: list[RestroomRankItem] = Field(default_factory=list)
    recent_issues: list[IssueOut] = Field(default_factory=list)
    recent_inspections: list[InspectionOut] = Field(default_factory=list)


class ShiftScoreRow(BaseModel):
    """单个班次的均分对比行：原始均分 + 按可比项目折算的均分。"""

    shift: str
    inspection_count: int = 0
    checklist_item_count: int = Field(default=0, description="该班次现行组合的检查项数")
    avg_score: float = Field(default=0.0, description="原始均分（按各记录自身组合算分）")
    comparable_count: int = Field(default=0, description="参与可比折算的记录数")
    comparable_avg_score: float = Field(default=0.0, description="可比均分（仅按可比项目折算）")


class ShiftComparison(BaseModel):
    """跨班次均分对比：可比项目集合固定，折算规则随结果一并返回。"""

    comparable_items: list[str] = Field(
        default_factory=list, description="可比项目：各班次现行组合的交集"
    )
    rule_note: str = Field(description="折算规则说明")
    shifts: list[ShiftScoreRow] = Field(default_factory=list)
