"""业务枚举与规则常量。"""

from enum import StrEnum


class RestroomStatus(StrEnum):
    NORMAL = "正常开放"
    MAINTENANCE = "维修中"
    CLOSED = "暂停使用"


class RestroomGrade(StrEnum):
    FIRST = "一类"
    SECOND = "二类"
    THIRD = "三类"


class Shift(StrEnum):
    MORNING = "早班"
    MIDDLE = "中班"
    NIGHT = "晚班"


class InspectionResult(StrEnum):
    NORMAL = "正常"
    ABNORMAL = "发现问题"


class IssueCategory(StrEnum):
    CLEANING = "保洁不到位"
    FACILITY = "设施损坏"
    ODOR = "异味扰民"
    CONSUMABLE = "耗材缺失"
    SAFETY = "安全隐患"
    OTHER = "其他"


class IssueSeverity(StrEnum):
    NORMAL = "一般"
    SERIOUS = "严重"
    URGENT = "紧急"


class IssueStatus(StrEnum):
    PENDING = "待整改"
    PROCESSING = "整改中"
    REVIEWING = "待验收"
    DONE = "已完成"
    CLOSED = "已关闭"


# 整改流转规则：当前状态 -> 允许流转到的状态
ISSUE_TRANSITIONS: dict[str, list[str]] = {
    IssueStatus.PENDING: [IssueStatus.PROCESSING, IssueStatus.CLOSED],
    IssueStatus.PROCESSING: [IssueStatus.REVIEWING, IssueStatus.CLOSED],
    IssueStatus.REVIEWING: [IssueStatus.DONE, IssueStatus.PROCESSING],
    IssueStatus.DONE: [IssueStatus.CLOSED],
    IssueStatus.CLOSED: [],
}

# 状态流转对应的动作名称，用于生成整改流水
TRANSITION_ACTIONS: dict[tuple[str, str], str] = {
    (IssueStatus.PENDING, IssueStatus.PROCESSING): "开始整改",
    (IssueStatus.PENDING, IssueStatus.CLOSED): "作废关闭",
    (IssueStatus.PROCESSING, IssueStatus.REVIEWING): "提交验收",
    (IssueStatus.PROCESSING, IssueStatus.CLOSED): "终止关闭",
    (IssueStatus.REVIEWING, IssueStatus.DONE): "验收通过",
    (IssueStatus.REVIEWING, IssueStatus.PROCESSING): "验收驳回",
    (IssueStatus.DONE, IssueStatus.CLOSED): "归档关闭",
}

# 检查项池：全部可选检查项，每项 0-10 分；班次组合只能从中选取
INSPECTION_CHECK_ITEMS: list[str] = [
    "地面与台阶清洁",
    "便池蹲位清洁",
    "洗手台与镜面",
    "通风除臭",
    "耗材补充",
    "垃圾清运",
    "工具与标识摆放",
    "墙面门窗卫生",
]

# 各班次默认检查项组合（检查项池的子集），作为 v1 版本写入：
# 早班侧重开放前的全面保洁与耗材就位；中班侧重高峰时段的保洁维持与异味控制；
# 晚班侧重收班前的垃圾清运、通风与设施安全检查。
DEFAULT_SHIFT_CHECKLISTS: dict[str, list[str]] = {
    Shift.MORNING: [
        "地面与台阶清洁",
        "便池蹲位清洁",
        "洗手台与镜面",
        "耗材补充",
        "垃圾清运",
        "工具与标识摆放",
    ],
    Shift.MIDDLE: [
        "地面与台阶清洁",
        "便池蹲位清洁",
        "洗手台与镜面",
        "通风除臭",
        "耗材补充",
        "垃圾清运",
    ],
    Shift.NIGHT: [
        "地面与台阶清洁",
        "便池蹲位清洁",
        "通风除臭",
        "垃圾清运",
        "墙面门窗卫生",
        "工具与标识摆放",
    ],
}

# 跨班次均分折算规则（固定，全系统只此一份，接口原样返回用于展示）：
# 可比项目 = 三个班次现行组合的交集，只有所有班次共同检查的项目才具备跨班次可比性；
# 集合由当前组合配置唯一确定，因此同一批数据在任意时刻只会折算出一个均分。
COMPARABLE_SCORE_RULE: str = (
    "可比项目取早班、中班、晚班现行检查项组合的交集（三个班次共同检查的项目）。"
    "跨班次比较均分时，仅取每条巡查记录中属于可比项目的打分折算百分制，再求平均；"
    "记录中不含可比项目的，不计入折算。"
    "可比项目集合由当前组合配置唯一确定，同一批数据只会折算出一个均分；"
    "组合调整后新口径对全部数据统一生效，各记录的原始得分与等级不受影响。"
)

INSPECTION_ITEM_MAX_SCORE = 10

GRADE_EXCELLENT = "优秀"
GRADE_GOOD = "良好"
GRADE_PASS = "合格"
GRADE_FAIL = "不合格"

# 仍处于整改闭环中的状态，用于统计未整改问题
OPEN_ISSUE_STATUSES: list[str] = [
    IssueStatus.PENDING,
    IssueStatus.PROCESSING,
    IssueStatus.REVIEWING,
]

# 单检查项低于该分数视为不合格项
INSPECTION_ITEM_PROBLEM_THRESHOLD = 6
