import atexit
import os
import tempfile
from pathlib import Path
import pytest


# Keep integration tests away from the developer's local database. The app reads
# settings during import, so this must be configured before test modules import it.
test_database = Path(tempfile.gettempdir()) / f"retunori-test-{os.getpid()}.db"
os.environ["DATABASE_URL"] = f"sqlite:///{test_database.as_posix()}"


def remove_test_database():
    try:
        from app.db import engine

        engine.dispose()
    except ImportError:
        pass
    for path in (test_database, Path(f"{test_database}-shm"), Path(f"{test_database}-wal")):
        try:
            path.unlink()
        except FileNotFoundError:
            pass


@atexit.register
def remove_test_database_at_exit():
    remove_test_database()


@pytest.fixture(autouse=True)
def mock_daraja(monkeypatch):
    """Keep tests deterministic; the real Daraja sandbox is tested separately."""
    from app.core.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "daraja_callback_secret", "")
    monkeypatch.setattr(settings, "daraja_consumer_key", "")
    monkeypatch.setattr(settings, "daraja_callback_url", "")
    monkeypatch.setattr(
        "app.main.initiate_stk",
        lambda *, account_reference, **kwargs: {"ResponseCode": "0", "CheckoutRequestID": account_reference},
    )


def pytest_sessionfinish(session, exitstatus):
    remove_test_database()
