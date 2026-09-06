"""Which database the app talks to is configuration, not a code branch.

The declaration promises PostgreSQL; SQLite is what a single-teacher install
runs. Both have to come out of DATABASE_URL alone.
"""

from sqlalchemy import inspect
from sqlmodel import SQLModel, create_engine

from app.db import ADDED_COLUMNS, engine_options, engine_url, ensure_added_columns, is_sqlite


def test_a_plain_postgres_url_reaches_the_driver_that_is_installed():
    """The extra installs psycopg 3, and a bare URL asks SQLAlchemy for psycopg2."""
    assert engine_url("postgresql://teacher:secret@db:5432/teaching") == (
        "postgresql+psycopg://teacher:secret@db:5432/teaching"
    )


def test_a_url_that_names_its_driver_is_left_alone():
    for url in (
        "postgresql+psycopg://db/teaching",
        "postgresql+psycopg2://db/teaching",
        "sqlite:///./teaching_design.db",
    ):
        assert engine_url(url) == url


def test_sqlites_own_thread_guard_is_not_passed_to_a_server():
    """check_same_thread is a SQLite argument; psycopg rejects what it does not know."""
    assert engine_options("sqlite:///./teaching_design.db") == {
        "connect_args": {"check_same_thread": False}
    }
    assert engine_options("postgresql://db/teaching") == {"pool_pre_ping": True}
    assert is_sqlite("postgresql://db/teaching") is False


def test_every_column_added_after_shipping_is_spelled_for_both_dialects():
    """Start-up adds these; a dialect missing a type would fail at start-up."""
    for table, columns in ADDED_COLUMNS.items():
        assert table.islower(), table
        for column in columns:
            assert column.sqlite_type and column.postgres_type, (table, column.name)


def test_a_database_missing_a_late_column_gets_it_back(tmp_path):
    """This is the whole migration story here, so it has to actually run."""
    import app.models  # noqa: F401  -- registers the tables on SQLModel.metadata

    older = create_engine(f"sqlite:///{(tmp_path / 'older.db').as_posix()}")
    SQLModel.metadata.create_all(older)
    with older.begin() as connection:
        connection.exec_driver_sql("ALTER TABLE outlinerow DROP COLUMN project_name")
    assert "project_name" not in {c["name"] for c in inspect(older).get_columns("outlinerow")}

    ensure_added_columns(older)

    assert "project_name" in {c["name"] for c in inspect(older).get_columns("outlinerow")}
    older.dispose()


def test_the_user_table_gets_its_late_column_despite_being_a_reserved_word(tmp_path):
    """`user` is reserved in PostgreSQL, so the DDL must quote the table name."""
    import app.models  # noqa: F401

    older = create_engine(f"sqlite:///{(tmp_path / 'older-user.db').as_posix()}")
    SQLModel.metadata.create_all(older)
    with older.begin() as connection:
        connection.exec_driver_sql('ALTER TABLE "user" DROP COLUMN must_change_password')
    assert "must_change_password" not in {c["name"] for c in inspect(older).get_columns("user")}

    ensure_added_columns(older)

    assert "must_change_password" in {c["name"] for c in inspect(older).get_columns("user")}
    older.dispose()
