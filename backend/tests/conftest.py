import atexit
import os
import tempfile
from pathlib import Path


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


def pytest_sessionfinish(session, exitstatus):
    remove_test_database()
