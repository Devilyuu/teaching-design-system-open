from collections.abc import Generator
from dataclasses import dataclass
import logging
import os
import secrets

from sqlalchemy import inspect
from sqlmodel import SQLModel, Session, create_engine, select

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./teaching_design.db")


def engine_url(url: str) -> str:
    """Let a plain postgresql:// URL work with the driver actually installed.

    SQLAlchemy reads a bare `postgresql://` as psycopg2, and the extra here
    installs psycopg 3. Without this, a connection string copied from anywhere
    else fails with a missing module rather than anything about the database.
    """
    prefix = "postgresql://"
    if url.startswith(prefix):
        return f"postgresql+psycopg://{url[len(prefix):]}"
    return url


def is_sqlite(url: str) -> bool:
    return url.startswith("sqlite")


def engine_options(url: str) -> dict:
    if is_sqlite(url):
        # SQLite's own guard. Lesson generation hands connections to a thread
        # pool, which this forbids by default.
        return {"connect_args": {"check_same_thread": False}}
    # A server closes idle connections; without this the first request after a
    # quiet night fails instead of reconnecting.
    return {"pool_pre_ping": True}


engine = create_engine(engine_url(DATABASE_URL), **engine_options(DATABASE_URL))


@dataclass(frozen=True)
class _AddedColumn:
    """A column added after the table was first shipped.

    There is no migration tool here, so start-up adds what is missing. The type
    is spelled per dialect: SQLite and PostgreSQL do not name timestamps alike.
    """

    name: str
    sqlite_type: str
    postgres_type: str
    backfill: str = ""


ADDED_COLUMNS: dict[str, tuple[_AddedColumn, ...]] = {
    "teachingtask": (
        _AddedColumn("owner_id", "INTEGER", "INTEGER"),
        _AddedColumn("major_id", "INTEGER", "INTEGER"),
    ),
    "lessonplan": (
        _AddedColumn("teaching_preparation", "TEXT NOT NULL DEFAULT ''", "TEXT NOT NULL DEFAULT ''"),
        _AddedColumn("summary", "TEXT NOT NULL DEFAULT ''", "TEXT NOT NULL DEFAULT ''"),
        _AddedColumn("generation_source", "TEXT NOT NULL DEFAULT 'manual'", "TEXT NOT NULL DEFAULT 'manual'"),
        _AddedColumn("review_status", "TEXT NOT NULL DEFAULT 'reviewed'", "TEXT NOT NULL DEFAULT 'reviewed'"),
    ),
    "sessionmaterial": (
        _AddedColumn("generation_method", "TEXT NOT NULL DEFAULT 'rule'", "TEXT NOT NULL DEFAULT 'rule'"),
    ),
    "outlinerow": (
        _AddedColumn(
            "updated_at",
            "DATETIME",
            "TIMESTAMP",
            backfill="UPDATE outlinerow SET updated_at = CURRENT_TIMESTAMP WHERE updated_at IS NULL",
        ),
        _AddedColumn("project_name", "TEXT NOT NULL DEFAULT ''", "TEXT NOT NULL DEFAULT ''"),
    ),
    "scheduleimportcandidate": (
        _AddedColumn("parse_meta_json", "TEXT NOT NULL DEFAULT ''", "TEXT NOT NULL DEFAULT ''"),
    ),
}


def init_db() -> None:
    SQLModel.metadata.create_all(engine)
    ensure_added_columns()
    _seed_default_admin()


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session


def ensure_added_columns(bind=None) -> None:
    """Bring an existing database up to the columns the models declare.

    Reads the columns through SQLAlchemy rather than PRAGMA so this runs on
    PostgreSQL too; before, a Postgres deployment silently skipped it and would
    have missed every column added after its tables were created.
    """
    bind = bind if bind is not None else engine
    inspector = inspect(bind)
    postgres = bind.dialect.name == "postgresql"
    with bind.begin() as connection:
        for table, columns in ADDED_COLUMNS.items():
            if not inspector.has_table(table):
                continue
            existing = {column["name"] for column in inspector.get_columns(table)}
            for column in columns:
                if column.name in existing:
                    continue
                definition = column.postgres_type if postgres else column.sqlite_type
                connection.exec_driver_sql(f"ALTER TABLE {table} ADD COLUMN {column.name} {definition}")
                if column.backfill:
                    connection.exec_driver_sql(column.backfill)


def _seed_default_admin() -> None:
    from app.auth import hash_password
    from app.models import TeachingTask, User

    employee_no = os.getenv("INITIAL_ADMIN_EMPLOYEE_NO", "admin")
    password = os.getenv("INITIAL_ADMIN_PASSWORD", "").strip()
    name = os.getenv("INITIAL_ADMIN_NAME", "系统管理员")
    generated = False
    if not password:
        # A password written in the source is a password every install shares,
        # and this repository is public. Draw one instead and print it once.
        password = secrets.token_urlsafe(12)
        generated = True
    with Session(engine) as session:
        existing = session.exec(select(User).where(User.employee_no == employee_no)).first()
        if existing is None:
            if generated:
                logging.getLogger(__name__).warning(
                    "已创建初始管理员：工号 %s，密码 %s —— 该密码只在此打印一次，"
                    "请立即登录后修改。要自己指定，请在 .env 中设置 INITIAL_ADMIN_PASSWORD。",
                    employee_no,
                    password,
                )
            existing = User(
                employee_no=employee_no,
                name=name,
                role="admin",
                password_hash=hash_password(password),
                is_active=True,
            )
            session.add(existing)
            session.commit()
            session.refresh(existing)

        if existing.id is not None:
            tasks_without_owner = session.exec(select(TeachingTask).where(TeachingTask.owner_id == None)).all()  # noqa: E711
            for task in tasks_without_owner:
                task.owner_id = existing.id
                session.add(task)
            session.commit()
