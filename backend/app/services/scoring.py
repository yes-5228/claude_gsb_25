"""巡查评分规则。

单条记录按其提交时绑定的检查项组合快照算分（总得分 ÷ 满分 × 100），
跨班次比较时再按系统固定的可比项目折算，见 comparable_score / comparable_average。
"""

from app.core.constants import (
    GRADE_EXCELLENT,
    GRADE_FAIL,
    GRADE_GOOD,
    GRADE_PASS,
    INSPECTION_COMPARABLE_ITEMS,
    INSPECTION_ITEM_MAX_SCORE,
    INSPECTION_ITEM_PROBLEM_THRESHOLD,
    InspectionResult,
)

_COMPARABLE_SET = set(INSPECTION_COMPARABLE_ITEMS)
_COMPARABLE_FULL = len(INSPECTION_COMPARABLE_ITEMS) * INSPECTION_ITEM_MAX_SCORE


def calc_score(items: list[dict]) -> float:
    """按检查项平均得分换算成百分制（以本条记录自身的组合满分为分母）。"""
    if not items:
        return 0.0
    total = sum(float(item["score"]) for item in items)
    full = len(items) * INSPECTION_ITEM_MAX_SCORE
    return round(total / full * 100, 1)


def score_to_grade(score: float) -> str:
    if score >= 90:
        return GRADE_EXCELLENT
    if score >= 80:
        return GRADE_GOOD
    if score >= 70:
        return GRADE_PASS
    return GRADE_FAIL


def is_abnormal(items: list[dict]) -> bool:
    """存在低于合格线的检查项即判定为发现问题。"""
    return any(float(item["score"]) < INSPECTION_ITEM_PROBLEM_THRESHOLD for item in items)


def build_result(items: list[dict], score: float) -> str:
    if is_abnormal(items) or score_to_grade(score) == GRADE_FAIL:
        return InspectionResult.ABNORMAL.value
    return InspectionResult.NORMAL.value


def evaluate(items: list[dict]) -> tuple[float, str, str]:
    """返回 (得分, 等级, 巡查结论)。"""
    score = calc_score(items)
    return score, score_to_grade(score), build_result(items, score)


def problem_items(items: list[dict]) -> list[dict]:
    return [item for item in items if float(item["score"]) < INSPECTION_ITEM_PROBLEM_THRESHOLD]


def covers_comparable(items: list[dict]) -> bool:
    """该记录的检查项是否覆盖全部固定可比项目。"""
    return _COMPARABLE_SET.issubset({item["name"] for item in items})


def comparable_score(items: list[dict]) -> float | None:
    """按固定可比项目折算的百分制得分。

    可比项目取所有班次必查的基础保洁项（系统常量，不随配置调整变化）：
    可比得分 = 可比项得分之和 ÷ 可比项满分 × 100。
    记录未覆盖全部可比项时返回 None，表示该记录不参与跨班次折算。
    """
    if not covers_comparable(items):
        return None
    score_by_name = {item["name"]: float(item["score"]) for item in items}
    total = sum(score_by_name[name] for name in INSPECTION_COMPARABLE_ITEMS)
    return round(total / _COMPARABLE_FULL * 100, 1)


def comparable_average(rows: list[list[dict]]) -> tuple[float, int]:
    """对一批巡查的打分明细计算跨班次可比均分。

    返回 (均分, 未覆盖可比项目而被剔除的记录数)。
    均分只对纳入记录的可比得分做算术平均；同一批数据口径固定，结果唯一。
    """
    included: list[float] = []
    excluded = 0
    for items in rows:
        score = comparable_score(items)
        if score is None:
            excluded += 1
        else:
            included.append(score)
    if not included:
        return 0.0, excluded
    return round(sum(included) / len(included), 1), excluded
