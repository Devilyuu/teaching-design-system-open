import os
import tempfile
from pathlib import Path

import pytest
from cryptography.fernet import Fernet


TEST_DATABASE_PATH = Path(tempfile.gettempdir()) / f"teaching_design_test_{os.getpid()}.db"
# Point this at a throwaway PostgreSQL to run the whole suite against the
# database production is meant to move to. Left unset, the suite uses SQLite as
# it always has.
EXTERNAL_DATABASE_URL = os.getenv("TEST_DATABASE_URL", "")

os.environ["DATABASE_URL"] = EXTERNAL_DATABASE_URL or f"sqlite:///{TEST_DATABASE_PATH.as_posix()}"
os.environ["MODEL_CONFIG_ENCRYPTION_KEY"] = Fernet.generate_key().decode("ascii")
# The seeded admin password is drawn at random when unset, so the suite names
# the one it logs in with rather than depending on a default in the source.
os.environ["INITIAL_ADMIN_PASSWORD"] = "Admin@2026!"


@pytest.fixture(scope="session", autouse=True)
def cleanup_test_database():
    if EXTERNAL_DATABASE_URL:
        # A run against a server starts from the tables the models declare now,
        # not from whatever the last run left behind.
        from sqlmodel import SQLModel

        from app.db import engine

        SQLModel.metadata.drop_all(engine)

    yield

    from app.db import engine

    engine.dispose()
    TEST_DATABASE_PATH.unlink(missing_ok=True)
