"""数据库引擎、会话与初始化。"""

import os
from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings


def _connect_args(url: str) -> dict:
    if url.startswith("sqlite"):
        return {"check_same_thread": False}
    return {}


def _prepare_sqlite_dir(url: str) -> None:
    if not url.startswith("sqlite:///"):
        return
    path = url.replace("sqlite:///", "", 1)
    if path.startswith(":memory:"):
        return
    directory = Path(path).parent
    if str(directory) not in ("", "."):
        os.makedirs(directory, exist_ok=True)


_prepare_sqlite_dir(settings.database_url)

engine = create_engine(
    settings.database_url,
    echo=settings.sql_echo,
    future=True,
    pool_pre_ping=True,
    connect_args=_connect_args(settings.database_url),
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


class Base(DeclarativeBase):
    """所有 ORM 模型的公共基类。"""


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from app import models  # noqa: F401  确保模型完成注册

    Base.metadata.create_all(bind=engine)
    _ensure_inspection_snapshot_columns()


def _ensure_inspection_snapshot_columns() -> None:
    """为旧版数据库补齐班次组合快照列（SQLite/PostgreSQL 通用的轻量迁移）。"""

    inspector = inspect(engine)
    if "inspections" not in inspector.get_table_names():
        return
    existing = {column["name"] for column in inspector.get_columns("inspections")}
    is_sqlite = engine.dialect.name == "sqlite"
    json_type = "TEXT" if is_sqlite else "JSON"
    missing_sql = {
        "check_items": f"ALTER TABLE inspections ADD COLUMN check_items {json_type}",
        "check_config_version": "ALTER TABLE inspections ADD COLUMN check_config_version INTEGER DEFAULT 1",
    }
    with engine.begin() as conn:
        for name, sql in missing_sql.items():
            if name not in existing:
                conn.execute(text(sql))


def backfill_legacy_inspection_snapshots(session: Session) -> int:
    """把没有组合快照的旧巡查按其实际打分明细回填（视为 v1 组合），返回回填条数。"""

    from app.models import Inspection

    rows = list(session.scalars(select(Inspection)))
    changed = 0
    for row in rows:
        if not row.check_items and row.items:
            row.check_items = [str(item.get("name")) for item in row.items if item.get("name")]
            row.check_config_version = row.check_config_version or 1
            changed += 1
    if changed:
        session.commit()
    return changed
