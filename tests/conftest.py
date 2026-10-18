import sys
import os

# Make sure Python can find database.py, main.py, auth.py, models.py —
# these live in the project ROOT, one folder above this tests/ directory.
# Without this, pytest only looks inside tests/ and fails with
# "ModuleNotFoundError: No module named 'database'".
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database import Base
from main import app, get_db

# ===== ISOLATED TEST DATABASE =====
# We use a SEPARATE SQLite database for tests, not your real PostgreSQL one.
# This means running tests will NEVER touch or corrupt your actual project data.
SQLALCHEMY_TEST_DATABASE_URL = "sqlite:///./test.db"

engine = create_engine(
    SQLALCHEMY_TEST_DATABASE_URL, connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function", autouse=True)
def setup_database():
    """Creates fresh tables before each test, and drops them after.
    This means every single test starts with a completely empty database —
    no leftover data from a previous test can affect this one."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


def override_get_db():
    """Replaces your real get_db() dependency with one pointing at the
    test database above, only for the duration of the test run."""
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
def reset_rate_limiter():
    """Your /register and /login routes are rate-limited (3/min and 5/min).
    Without this, running many tests back-to-back would trip that limit
    and cause unrelated tests to fail with 429 errors. This resets the
    limiter's internal counter before every test."""
    app.state.limiter.reset()
    yield


@pytest.fixture
def client():
    """A ready-to-use FastAPI test client, wired to the test database above."""
    return TestClient(app)