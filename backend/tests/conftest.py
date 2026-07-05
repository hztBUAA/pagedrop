import os
import tempfile

# Configure an isolated SQLite database BEFORE importing any app module,
# so the engine binds to the test database.
_tmp_db = os.path.join(tempfile.gettempdir(), "pagedrop_test.db")
if os.path.exists(_tmp_db):
    os.remove(_tmp_db)
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp_db}"
os.environ["JWT_SECRET"] = "test-jwt-secret"
os.environ["TOKEN_PEPPER"] = "test-token-pepper"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import app.models  # noqa: E402,F401
from app.core.database import Base, engine  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _create_schema():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(autouse=True)
def _reset_ratelimit():
    from app.core import ratelimit

    ratelimit.reset()
    yield


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c
