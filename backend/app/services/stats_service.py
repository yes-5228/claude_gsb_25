"""统计看板业务逻辑。

凡涉及跨班次（或跨不同检查项组合版本）的均分，一律按 scoring 中的固定可比项目
折算，折算口径随 score_basis 返回，保证同一批数据只有一个均分。
"""

from datetime import date, datetime, time, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.constants import (
    INSPECTION_COMPARABLE_ITEMS,
    INSPECTION_COMPARABLE_RULE,
    OPEN_ISSUE_STATUSES,
    IssueCategory,
    IssueSeverity,
    IssueStatus,
    RestroomStatus,
)
from app.models import Inspection, Issue, Restroom
from app.schemas.stats import (
    CategoryStat,
    ComparableScoreBasis,
    DashboardStats,
    DistrictStat,
    NameValue,
    OverviewStats,
    RestroomRankItem,
    TrendPoint,
)
from app.services import inspection_service, issue_service, scoring


def _count(db: Session, model, *conditions) -> int:
    stmt = select(func.count()).select_from(model)
    if conditions:
        stmt = stmt.where(*conditions)
    return db.scalar(stmt) or 0


def _avg(rows: list[Inspection]) -> tuple[float, int]:
    """对一组巡查按固定可比项目折算均分，返回 (均分, 剔除数)。"""
    return scoring.comparable_average([list(row.items or []) for row in rows])


def score_basis(db: Session) -> ComparableScoreBasis:
    """全库统一的折算口径：纳入/剔除计数基于全部巡查。"""
    all_rows = list(db.scalars(select(Inspection)))
    _, excluded = _avg(all_rows)
    return ComparableScoreBasis(
        comparable_items=list(INSPECTION_COMPARABLE_ITEMS),
        rule=INSPECTION_COMPARABLE_RULE,
        included_count=len(all_rows) - excluded,
        excluded_count=excluded,
    )


def overview(db: Session) -> OverviewStats:
    now = datetime.now()
    today_start = datetime.combine(now.date(), time.min)
    week_start = today_start - timedelta(days=6)
    month_start = datetime.combine(date(now.year, now.month, 1), time.min)

    issue_total = _count(db, Issue)
    issue_open = _count(db, Issue, Issue.status.in_(OPEN_ISSUE_STATUSES))
    issue_overdue = _count(
        db,
        Issue,
        Issue.deadline.is_not(None),
        Issue.deadline < now,
        Issue.status.in_(OPEN_ISSUE_STATUSES),
    )
    done_count = _count(db, Issue, Issue.status == IssueStatus.DONE.value)
    closed_count = _count(db, Issue, Issue.status == IssueStatus.CLOSED.value)
    finished = done_count + closed_count

    week_rows = list(
        db.scalars(select(Inspection).where(Inspection.inspect_time >= week_start))
    )
    avg_score_week, _ = _avg(week_rows)

    return OverviewStats(
        restroom_total=_count(db, Restroom),
        restroom_open=_count(db, Restroom, Restroom.status == RestroomStatus.NORMAL.value),
        restroom_maintenance=_count(db, Restroom, Restroom.status == RestroomStatus.MAINTENANCE.value),
        inspection_total=_count(db, Inspection),
        inspection_today=_count(db, Inspection, Inspection.inspect_time >= today_start),
        inspection_week=_count(db, Inspection, Inspection.inspect_time >= week_start),
        avg_score_week=avg_score_week,
        issue_total=issue_total,
        issue_open=issue_open,
        issue_overdue=issue_overdue,
        issue_done_this_month=_count(
            db, Issue, Issue.status == IssueStatus.DONE.value, Issue.updated_at >= month_start
        ),
        rectification_rate=round(finished / issue_total * 100, 1) if issue_total else 0.0,
    )


def issue_by_status(db: Session) -> list[NameValue]:
    rows = dict(
        db.execute(select(Issue.status, func.count()).group_by(Issue.status)).all()  # type: ignore[arg-type]
    )
    ordered = list(IssueStatus)
    return [NameValue(name=status.value, value=float(rows.get(status.value, 0))) for status in ordered]


def issue_by_severity(db: Session) -> list[NameValue]:
    rows = dict(db.execute(select(Issue.severity, func.count()).group_by(Issue.severity)).all())
    return [
        NameValue(name=severity.value, value=float(rows.get(severity.value, 0)))
        for severity in IssueSeverity
    ]


def issue_by_category(db: Session) -> list[CategoryStat]:
    rows = db.execute(
        select(Issue.category, func.count()).group_by(Issue.category)
    ).all()
    totals = {category: int(count) for category, count in rows}
    open_rows = db.execute(
        select(Issue.category, func.count())
        .where(Issue.status.in_(OPEN_ISSUE_STATUSES))
        .group_by(Issue.category)
    ).all()
    opens = {category: int(count) for category, count in open_rows}
    result: list[CategoryStat] = []
    for category in IssueCategory:
        total = totals.get(category.value, 0)
        open_count = opens.get(category.value, 0)
        result.append(
            CategoryStat(
                category=category.value, total=total, open=open_count, closed=total - open_count
            )
        )
    return result


def inspection_trend(db: Session, days: int = 14) -> list[TrendPoint]:
    days = max(3, min(days, 60))
    today = datetime.now().date()
    start = today - timedelta(days=days - 1)
    start_dt = datetime.combine(start, time.min)

    inspection_rows = list(
        db.scalars(
            select(Inspection).where(Inspection.inspect_time >= start_dt)
        )
    )
    issue_rows = db.execute(
        select(Issue.report_time).where(Issue.report_time >= start_dt)
    ).all()

    buckets: dict[str, dict] = {}
    for offset in range(days):
        key = (start + timedelta(days=offset)).isoformat()
        buckets[key] = {"inspections": [], "issues": 0}
    for inspection in inspection_rows:
        key = inspection.inspect_time.date().isoformat()
        if key in buckets:
            buckets[key]["inspections"].append(inspection)
    for (report_time,) in issue_rows:
        key = report_time.date().isoformat()
        if key in buckets:
            buckets[key]["issues"] += 1

    points: list[TrendPoint] = []
    for key, bucket in buckets.items():
        day_rows: list[Inspection] = bucket["inspections"]
        avg_score, excluded = _avg(day_rows)
        points.append(
            TrendPoint(
                date=key,
                inspections=len(day_rows),
                issues=int(bucket["issues"]),
                avg_score=avg_score,
                score_excluded=excluded,
            )
        )
    return points


def district_stats(db: Session) -> list[DistrictStat]:
    restroom_rows = db.execute(
        select(Restroom.district, func.count()).group_by(Restroom.district)
    ).all()
    counts = {district: int(count) for district, count in restroom_rows}
    open_rows = db.execute(
        select(Restroom.district, func.count(Issue.id))
        .join(Issue, Issue.restroom_id == Restroom.id)
        .where(Issue.status.in_(OPEN_ISSUE_STATUSES))
        .group_by(Restroom.district)
    ).all()
    opens = {district: int(count) for district, count in open_rows}

    district_by_id = dict(db.execute(select(Restroom.id, Restroom.district)).all())
    inspections = list(db.scalars(select(Inspection)))
    by_district: dict[str, list[Inspection]] = {}
    for inspection in inspections:
        district = district_by_id.get(inspection.restroom_id)
        if district is not None:
            by_district.setdefault(district, []).append(inspection)
    scores = {district: _avg(rows)[0] for district, rows in by_district.items()}

    return sorted(
        [
            DistrictStat(
                district=district,
                restroom_count=count,
                issue_open=opens.get(district, 0),
                avg_score=round(scores.get(district, 0.0), 1),
            )
            for district, count in counts.items()
        ],
        key=lambda item: (item.issue_open, -item.avg_score),
        reverse=True,
    )


def restroom_ranking(db: Session, limit: int = 8) -> list[RestroomRankItem]:
    inspections = list(db.scalars(select(Inspection)))
    grouped: dict[int, list[Inspection]] = {}
    for inspection in inspections:
        grouped.setdefault(inspection.restroom_id, []).append(inspection)
    stats = {
        rid: {"count": len(rows), "avg": _avg(rows)[0]} for rid, rows in grouped.items()
    }
    open_rows = db.execute(
        select(Issue.restroom_id, func.count())
        .where(Issue.status.in_(OPEN_ISSUE_STATUSES))
        .group_by(Issue.restroom_id)
    ).all()
    opens = {rid: int(count) for rid, count in open_rows}

    ranking: list[RestroomRankItem] = []
    for restroom in db.scalars(select(Restroom)):
        stat = stats.get(restroom.id, {"count": 0, "avg": 0.0})
        ranking.append(
            RestroomRankItem(
                restroom_id=restroom.id,
                code=restroom.code,
                name=restroom.name,
                district=restroom.district,
                inspection_count=stat["count"],
                avg_score=stat["avg"],
                open_issues=opens.get(restroom.id, 0),
            )
        )
    ranking.sort(key=lambda item: (-item.open_issues, item.avg_score, -item.inspection_count))
    return ranking[:limit]


def dashboard(db: Session, trend_days: int = 14) -> DashboardStats:
    recent_issues, _ = issue_service.list_issues(db, page=1, page_size=5, sort_by="report_time")
    recent_inspections, _ = inspection_service.list_inspections(
        db, page=1, page_size=5, sort_by="inspect_time"
    )
    return DashboardStats(
        overview=overview(db),
        score_basis=score_basis(db),
        issue_by_status=issue_by_status(db),
        issue_by_category=issue_by_category(db),
        issue_by_severity=issue_by_severity(db),
        inspection_trend=inspection_trend(db, days=trend_days),
        districts=district_stats(db),
        top_restrooms=restroom_ranking(db),
        recent_issues=[issue_service.to_out(issue) for issue in recent_issues],
        recent_inspections=[inspection_service.to_out(item) for item in recent_inspections],
    )
