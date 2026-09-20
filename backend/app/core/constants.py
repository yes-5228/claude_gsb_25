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

# 全部可配置的检查项目库（配置班次组合时只能从中选择）
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

# 各班次默认检查项组合（首次初始化班次配置 v1 时使用）
DEFAULT_SHIFT_CHECK_ITEMS: dict[str, list[str]] = {
    # 早班开班全面保洁，8 项全查
    Shift.MORNING: list(INSPECTION_CHECK_ITEMS),
    # 中班以日间维护为主，墙面门窗卫生、工具与标识摆放并入早班检查
    Shift.MIDDLE: [
        "地面与台阶清洁",
        "便池蹲位清洁",
        "洗手台与镜面",
        "通风除臭",
        "耗材补充",
        "垃圾清运",
    ],
    # 晚班以闭园清洁、耗材复位为主，洗手台镜面、工具标识并入次日早班检查
    Shift.NIGHT: [
        "地面与台阶清洁",
        "便池蹲位清洁",
        "通风除臭",
        "耗材补充",
        "垃圾清运",
        "墙面门窗卫生",
    ],
}

# 跨班次比较均分使用的【固定可比项目】。
# 依据：不同班次检查项数量与构成不同，直接用各自百分制均分比较不公平；
# 只有所有班次都必查的基础保洁项才具备横向可比性，因此取三班默认组合的
# 公共基础项作为固定折算口径。该集合是系统级常量，不随班次配置调整而变化，
# 保证同一批数据无论何时计算都只会得到同一个跨班次均分。
INSPECTION_COMPARABLE_ITEMS: list[str] = [
    "地面与台阶清洁",
    "便池蹲位清洁",
    "垃圾清运",
]

# 折算规则的固定文字依据，随统计接口一并返回给前端展示
INSPECTION_COMPARABLE_RULE = (
    "跨班次均分按固定可比项目折算：可比项目取所有班次必查的基础保洁项"
    "（地面与台阶清洁、便池蹲位清洁、垃圾清运，共 3 项，满分 30 分）；"
    "每条记录的可比得分 = 该 3 项得分之和 ÷ 30 × 100，"
    "组内均分 = 纳入记录可比得分的算术平均值。"
    "可比项目为系统固定口径，不随班次检查项配置调整而变化；"
    "未覆盖全部可比项目的历史记录不参与折算并单独剔除计数。"
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
